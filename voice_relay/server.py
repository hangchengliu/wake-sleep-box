#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Wake 中转服务（仅用 Python 标准库，无需 pip install）。

板子  --POST /api/voice (PCM16 16kHz 单声道)-->  本服务
本服务: 识别(ASR) -> 唤醒词门控 -> 意图/对话 -> 合成(TTS)
本服务  --应答: body=PCM16 语音, 头 X-Wake-Cmd=板子要执行的指令-->  板子

所有上游接口地址、模型名都来自环境变量，代码里不猜默认值。API Key 只放 .env，不进 git。
"""
import array
import io
import json
import os
import sys
import time
import urllib.request
import uuid
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from intent import detect_intent, confirm_text

HERE = Path(__file__).resolve().parent
NOTES_FILE = HERE / "notes.jsonl"
SR = 16000
MAX_UPLOAD = 16000 * 2 * 30          # 最多 30 秒，防止误传超大数据


def load_env(path: Path):
    """极简 .env 读取：KEY=VALUE，忽略空行和 # 注释。已存在的环境变量优先。"""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


class Config:
    REQUIRED = ["OPENDEV_BASE_URL", "OPENDEV_API_KEY", "ASR_MODEL", "CHAT_MODEL", "TTS_MODEL", "TTS_VOICE"]

    def __init__(self):
        g = os.environ.get
        self.base = (g("OPENDEV_BASE_URL") or "").rstrip("/")
        self.key = g("OPENDEV_API_KEY", "")
        self.asr_model = g("ASR_MODEL", "")
        self.chat_model = g("CHAT_MODEL", "")
        self.tts_model = g("TTS_MODEL", "")
        self.tts_voice = g("TTS_VOICE", "")
        self.wake_words = [w for w in (g("WAKE_WORDS", "小夜,晓夜,小也") or "").split(",") if w.strip()]
        self.follow_up_s = int(g("FOLLOW_UP_SECONDS", "20"))
        self.port = int(g("PORT", "8787"))

    def missing(self):
        return [k for k in self.REQUIRED if not os.environ.get(k)]


# ---------------- 音频工具 ----------------
def pcm_to_wav(pcm: bytes, sr: int = SR) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes(pcm)
    return buf.getvalue()


def wav_to_pcm16k(data: bytes) -> bytes:
    """任意 16bit WAV -> 16kHz 单声道 PCM16（线性插值重采样）。非 WAV 抛错，不猜格式。"""
    if data[:4] != b"RIFF":
        raise ValueError("TTS 返回的不是 WAV（请在 .env 里让 TTS 返回 wav 格式）")
    with wave.open(io.BytesIO(data), "rb") as w:
        if w.getsampwidth() != 2:
            raise ValueError(f"只支持 16bit WAV，收到 {w.getsampwidth()*8}bit")
        ch, sr, raw = w.getnchannels(), w.getframerate(), w.readframes(w.getnframes())
    s = array.array("h"); s.frombytes(raw)
    if ch > 1:
        s = array.array("h", (sum(s[i:i + ch]) // ch for i in range(0, len(s) - ch + 1, ch)))
    if sr != SR and len(s) > 1:
        n_out = int(len(s) * SR / sr)
        out = array.array("h")
        for i in range(n_out):
            pos = i * (len(s) - 1) / max(1, n_out - 1)
            j = int(pos); f = pos - j
            nxt = s[min(j + 1, len(s) - 1)]
            out.append(int(s[j] * (1 - f) + nxt * f))
        s = out
    return s.tobytes()


# ---------------- 上游调用（可被测试替换） ----------------
RETRY_CODES = (429, 500, 502, 503, 504)


def _is_conn_drop(e: BaseException) -> bool:
    """对端在没回应前就断开(如 'Remote end closed connection without response')。
    这类是瞬时的、请求大概率根本没被处理，值得重试。读超时(socket.timeout)不算：
    请求可能已被上游处理，重试会白白多等一个 timeout，也可能重复计费。"""
    import http.client, socket
    if isinstance(e, socket.timeout):
        return False
    if isinstance(e, (http.client.RemoteDisconnected, http.client.IncompleteRead, ConnectionResetError, ConnectionAbortedError, BrokenPipeError)):
        return True
    if isinstance(e, urllib.error.URLError):
        r = e.reason
        return isinstance(r, (ConnectionResetError, ConnectionAbortedError, BrokenPipeError, http.client.RemoteDisconnected))
    return False


def _post(url, body, headers, timeout=30, tries=3):
    """所有上游调用共用。
    - 上游前面有 Cloudflare，会拦截 Python-urllib 默认 UA (error code 1010)，所以显式带 UA，可用 USER_AGENT 覆盖。
    - 429/5xx(上游过载)和连接被对端掐断：按 1.5s、3s 退避重试，共 tries 次。
    - 其它错误(401/403/400)和读超时：立刻抛出，不重试。
    """
    h = {"User-Agent": os.environ.get("USER_AGENT", "curl/7.88.1")}
    h.update(headers)
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, data=body, headers=h, method="POST")
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code not in RETRY_CODES:
                raise
            last, why = e, f"HTTP {e.code}"
        except Exception as e:
            if not _is_conn_drop(e):
                raise
            last, why = e, "连接被对端断开"
        if i < tries - 1:
            print(f"[Retry] {url.rsplit('/', 1)[-1]} -> {why}, 第 {i + 1} 次失败")
            time.sleep(1.5 * (i + 1))
    raise last


class Upstream:
    def __init__(self, cfg: Config):
        self.c = cfg

    def asr(self, pcm: bytes) -> str:
        boundary = uuid.uuid4().hex
        parts = []
        def field(name, value):
            parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
        field("model", self.c.asr_model)
        field("language", "zh")
        # 用简体中文示例句引导输出为简体，并给唤醒词与常用指令一点先验，减少“小夜”被听成别的字。
        field("prompt", "以下是普通话简体中文。小夜，开始守夜。小夜，早安。记录梦境，我梦见在海里游泳。")
        parts.append((f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="a.wav"\r\n'
                      f'Content-Type: audio/wav\r\n\r\n').encode() + pcm_to_wav(pcm) + b"\r\n")
        parts.append(f"--{boundary}--\r\n".encode())
        out = _post(f"{self.c.base}/audio/transcriptions", b"".join(parts), {
            "Authorization": f"Bearer {self.c.key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}"})
        return json.loads(out)["text"].strip()

    def chat(self, messages) -> str:
        out = _post(f"{self.c.base}/chat/completions",
                    json.dumps({"model": self.c.chat_model, "messages": messages,
                                "max_tokens": 160, "temperature": 0.7}).encode(),
                    {"Authorization": f"Bearer {self.c.key}", "Content-Type": "application/json"})
        return json.loads(out)["choices"][0]["message"]["content"].strip()

    # TTS 熔断: 连续失败 TTS_BREAKER_N 次后的 TTS_BREAKER_S 秒内直接跳过，不再每句话白等重试。
    # 上游音频组过载往往持续几十分钟，每次都重试三遍只会让每句话多等 4~5 秒。
    breaker_fails = 0
    breaker_until = 0.0

    def tts(self, text: str) -> bytes:
        now = time.time()
        if now < self.breaker_until:
            raise RuntimeError(f"TTS 熔断中，还剩 {int(self.breaker_until - now)} 秒")
        body = json.dumps({"model": self.c.tts_model, "voice": self.c.tts_voice,
                           "input": text, "response_format": "wav"}).encode()
        hdr = {"Authorization": f"Bearer {self.c.key}", "Content-Type": "application/json"}
        try:
            pcm = wav_to_pcm16k(_post(f"{self.c.base}/audio/speech", body, hdr))
        except Exception:
            self.breaker_fails += 1
            if self.breaker_fails >= 2:
                self.breaker_until = time.time() + 60
                self.breaker_fails = 0
                print("[Breaker] TTS 连续失败，60 秒内直接降级")
            raise
        self.breaker_fails = 0
        return pcm


# ---------------- 业务流程 ----------------
# ---------------- ASR 文本清洗 ----------------
# Whisper 对中文偶尔输出繁体。这里只映射「指令、唤醒词、梦境」里会用到的常见字，
# 不是完整的繁简转换(沙箱和现场都不该为此装第三方库)。
_T2S = str.maketrans({
    "氣": "气", "們": "们", "這": "这", "個": "个", "來": "来", "時": "时", "點": "点", "開": "开",
    "關": "关", "夢": "梦", "見": "见", "記": "记", "錄": "录", "報": "报", "寢": "寝", "睏": "困",
    "覺": "觉", "歲": "岁", "結": "结", "東": "东", "動": "动", "說": "说", "話": "话", "麼": "么",
    "為": "为", "還": "还", "會": "会", "對": "对", "沒": "没", "請": "请", "謝": "谢", "給": "给",
    "從": "从", "應": "应", "當": "当", "將": "将", "讓": "让", "與": "与", "裡": "里", "裏": "里",
    "後": "后", "發": "发", "現": "现", "實": "实", "場": "场", "聽": "听", "調": "调", "雲": "云",
    "聲": "声", "燈": "灯", "遠": "远", "運": "运", "過": "过", "測": "测", "試": "试", "監": "监",
    "護": "护", "幫": "帮", "紀": "纪", "總": "总", "題": "题", "問": "问", "錯": "错", "認": "认",
    "識": "识", "語": "语", "讀": "读", "學": "学", "車": "车", "門": "门", "間": "间", "長": "长",
    "頭": "头", "嗎": "吗", "鐘": "钟", "鬧": "闹", "響": "响", "電": "电", "腦": "脑",
})


def normalize_text(s: str) -> str:
    return (s or "").translate(_T2S).strip()


# Whisper 在静音/纯噪音/正弦波上常凭空“听出”片尾字幕、频道名等。命中这些就当作没人说话。
_HALLUC = ("字幕", "订阅", "订閱", "点赞", "谢谢观看", "謝謝觀看", "请不吝", "明镜", "明鏡", "amara", "subtitles",
           "thanks for watching", "ming pao", "mingpao", "www.", "http", "©")


def is_hallucination(text: str) -> bool:
    t = text.strip().lower()
    if len(t) < 2:
        return True                                   # 空串、单字(“嗯”“啊”)不处理
    if any(k in t for k in _HALLUC):
        return True
    cjk = sum(1 for ch in t if "一" <= ch <= "鿿")
    return cjk == 0                                   # 一个汉字都没有：本项目只服务中文指令


class Assistant:
    def __init__(self, cfg: Config, up, notes_file: Path = NOTES_FILE, clock=time.time):
        self.cfg, self.up, self.notes_file, self.clock = cfg, up, notes_file, clock
        self.history = []
        self.awake_until = 0.0

    # 梦境/笔记：追加写文件，重启不丢
    def save_note(self, kind, content):
        rec = {"t": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.clock())), "kind": kind, "text": content}
        with open(self.notes_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def recent_notes(self, n=5):
        if not self.notes_file.exists():
            return []
        lines = self.notes_file.read_text(encoding="utf-8").splitlines()[-n:]
        return [json.loads(x) for x in lines if x.strip()]

    def gate(self, text, t_arrive=None):
        """唤醒词门控。返回去掉唤醒词后的文本；未唤醒返回 None。
        t_arrive: 这句话“到达服务端”的时刻。判断追问窗口用它，而不是处理完的时刻——
        上游重试、识别排队的耗时不该算进用户的追问窗口。"""
        now = t_arrive if t_arrive is not None else self.clock()
        if not self.cfg.wake_words:
            return text
        for w in self.cfg.wake_words:
            if w in text:
                self.awake_until = now + self.cfg.follow_up_s     # 先临时按到达时刻计，回复完成后会再延长
                rest = text.split(w, 1)[1].lstrip("，,。 ")
                return rest or "我在"
        if now < self.awake_until:
            self.awake_until = now + self.cfg.follow_up_s
            return text
        return None

    def handle_text(self, text):
        """返回 (回复文本, 板子指令或空串)。"""
        intent = detect_intent(text)
        if intent and intent["tool"] == "record_dream":
            self.save_note("dream", intent["args"].get("content", text))
        if intent and intent["tool"] in ("start_night", "stop_night", "record_dream"):
            return confirm_text(intent), intent_to_cmd(intent)
        if intent:                                   # 查询类交给对话模型，带上近期笔记
            pass
        sys_prompt = "你是 Wake 守夜助手，只用一两句简短口语中文回答。"
        notes = self.recent_notes()
        if notes:
            sys_prompt += " 用户最近记录的梦境/笔记：" + "；".join(f"{x['t']} {x['text']}" for x in notes)
        self.history.append({"role": "user", "content": text})
        self.history = self.history[-12:]
        reply = self.up.chat([{"role": "system", "content": sys_prompt}] + self.history)
        self.history.append({"role": "assistant", "content": reply})
        return reply, ""

    def process(self, pcm: bytes):
        """返回 None(未唤醒/无内容/疑似幻觉) 或 (回复PCM, 指令)。"""
        t_arrive = self.clock()                      # 追问窗口按“话到达”的时刻算，不含上游重试耗时
        t0 = time.time()
        raw = self.up.asr(pcm)
        t_asr = time.time() - t0
        text = normalize_text(raw)
        print(f"[ASR] {raw!r}" + (f" -> {text!r}" if text != raw else "") + f"  ({t_asr:.1f}s)")
        if is_hallucination(text):
            print("[Filter] 疑似静音/噪音幻觉，丢弃")
            return None
        text = self.gate(text, t_arrive)
        if text is None:
            print("[Gate] 未听到唤醒词，丢弃")
            return None
        reply, cmd = self.handle_text(text)
        print(f"[Reply] {reply!r} cmd={cmd!r}")
        t1 = time.time()
        try:
            audio = self.up.tts(reply)
        except Exception as e:
            # TTS 不可用时降级: 只要有板子指令，仍然返回指令(空音频)，板子用自带离线语音(如"晚安，开始守夜")确认。
            print(f"[TTS 失败] {type(e).__name__}: {e}")
            audio = b""
        print(f"[Time] ASR {t_asr:.1f}s + TTS {time.time() - t1:.1f}s = 共 {time.time() - t0:.1f}s")
        if not audio and not cmd:
            raise RuntimeError("语音合成不可用，且这句话没有可执行的指令")
        # 回复发出后，用户还要听完再说下一句，所以追问窗口从“回复完成”这一刻重新起算。
        if self.cfg.wake_words and self.awake_until > 0:
            self.awake_until = max(self.awake_until, self.clock() + self.cfg.follow_up_s)
        return audio, cmd


def intent_to_cmd(intent):
    return {"start_night": "N:1", "stop_night": "N:2"}.get(intent["tool"], "")


# ---------------- HTTP ----------------
def make_handler(assistant: Assistant, cfg: Config):
    class H(BaseHTTPRequestHandler):
        def log_message(self, fmt, *a):
            pass

        def _send(self, code, body=b"", ctype="application/octet-stream", extra=None):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/api/health":
                self._send(200, json.dumps({"ok": True, "missing_env": cfg.missing()}).encode(), "application/json")
            else:
                self._send(404)

        def do_POST(self):
            if self.path != "/api/voice":
                return self._send(404)
            n = int(self.headers.get("Content-Length", 0))
            if n < 3200 or n > MAX_UPLOAD:                    # <0.1s 或 >30s 都不处理
                return self._send(400, b'{"error":"bad audio length"}', "application/json")
            try:
                res = assistant.process(self.rfile.read(n))
            except Exception as e:
                print(f"[ERROR] {type(e).__name__}: {e}")
                return self._send(502, json.dumps({"error": str(e)}).encode(), "application/json")
            if res is None:
                return self._send(204)                        # 板子收到 204 = 没唤醒，静默
            pcm, cmd = res
            self._send(200, pcm, extra={"X-Wake-Cmd": cmd})
    return H


def main():
    load_env(HERE / ".env")
    cfg = Config()
    miss = cfg.missing()
    if miss:
        sys.exit("缺少环境变量: " + ", ".join(miss) + "\n请复制 .env.example 为 .env 并按 Opendev 文档填写。")
    srv = ThreadingHTTPServer(("0.0.0.0", cfg.port), make_handler(Assistant(cfg, Upstream(cfg)), cfg))
    print(f"Wake 中转服务 http://0.0.0.0:{cfg.port}  唤醒词={cfg.wake_words or '关闭'}")
    srv.serve_forever()


if __name__ == "__main__":
    main()
