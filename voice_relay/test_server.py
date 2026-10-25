#!/usr/bin/env python3
"""验证全流程（不调真实上游，测试本地逻辑）：唤醒词、意图、笔记、对话历史。"""
import io, json, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from server import Assistant, Config, pcm_to_wav, wav_to_pcm16k
from intent import detect_intent, confirm_text

class FakeUp:
    def asr(self, _): return self.text
    def chat(self, _): return "好的，我明白了。"
    def tts(self, text): return f"[TTS:{text}]".encode()

def mk_pcm(): return b"\x00\x00" * 160  # 10ms@16k

def test_gate():
    """唤醒词门控"""
    print("=== 唤醒词门控 ===")
    class ClockMock: t=0
    cfg = Config(); cfg.wake_words = ["小夜"]; cfg.follow_up_s = 2
    ass = Assistant(cfg, None, Path("/tmp/x"), lambda: ClockMock.t)
    assert ass.gate("你好小夜，开始守夜") == "开始守夜"
    ClockMock.t = 1
    assert ass.gate("好的") == "好的", "追问窗口未过期"
    ClockMock.t = 4
    assert ass.gate("好的") is None, "追问过期"
    print("  ✓ 唤醒词与追问窗口正常")

def test_intent():
    print("\n=== 意图识别 ===")
    cases = [
        ("开始守夜", "start_night"),
        ("我梦见飞在天上", "record_dream"),
        ("昨晚梦到什么", None),
        ("结束守夜", "stop_night"),
        ("今天天气如何", None),
    ]
    for txt, exp in cases:
        res = detect_intent(txt)
        got = res["tool"] if res else None
        ok = "✓" if got == exp else f"✗ 期望{exp}"
        print(f"  {txt!r} -> {got} {ok}")

def test_notes():
    print("\n=== 梦境笔记存取 ===")
    tmp = HERE / "test_notes.jsonl"
    tmp.unlink(missing_ok=True)
    cfg = Config(); up = FakeUp()
    a = Assistant(cfg, up, tmp)
    a.save_note("dream", "飞在天上")
    a.save_note("dream", "遇见老朋友")
    notes = a.recent_notes(2)
    assert len(notes) == 2 and notes[0]["text"] == "飞在天上"
    print(f"  ✓ 保存并读取笔记: {notes}")
    tmp.unlink()

def test_audio():
    print("\n=== 音频转换（WAV ↔ PCM16K）===")
    pcm = b"\x00\x01" * 16000  # 1s@16k
    wav = pcm_to_wav(pcm, 16000)
    assert wav[:4] == b"RIFF"
    back = wav_to_pcm16k(wav)
    print(f"  ✓ 往返转换: {len(pcm)}B -> WAV:{len(wav)}B -> PCM:{len(back)}B")

def test_full_flow():
    print("\n=== 完整流程（不调外部API）===")
    cfg = Config(); cfg.wake_words = []  # 关闭门控
    up = FakeUp()
    tmp = HERE / "test_flow.jsonl"; tmp.unlink(missing_ok=True)
    a = Assistant(cfg, up, tmp)

    up.text = "开始守夜"
    res = a.process(mk_pcm())
    assert res and b"TTS" in res[0] and res[1] == "N:1"
    print(f"  ✓ 开始守夜 -> {res[1]}, 回复={res[0]!r}")

    up.text = "我梦见飞在天上"
    res = a.process(mk_pcm())
    assert res and b"TTS" in res[0]
    assert tmp.read_text().strip(), "梦境已写入笔记"
    print(f"  ✓ 梦境记录 -> 笔记已写")

    up.text = "今天天气"
    res = a.process(mk_pcm())
    assert res and b"TTS" in res[0]
    print(f"  ✓ 普通对话 -> 回复={res[0]!r}")

    tmp.unlink()

def test_user_agent():
    print("\n=== 上游请求带 User-Agent（防 Cloudflare 1010）===")
    import urllib.request, server
    seen = {}
    class R:
        def read(self): return b"{}"
        def __enter__(self): return self
        def __exit__(self, *a): return False
    orig = urllib.request.urlopen
    urllib.request.urlopen = lambda req, timeout=0: (seen.update(ua=req.get_header("User-agent")) or R())
    try:
        server._post("http://example.invalid/x", b"", {})
    finally:
        urllib.request.urlopen = orig
    assert seen["ua"] and "Python-urllib" not in seen["ua"], seen
    print(f"  ✓ UA = {seen['ua']}")

def test_tts_degrade():
    print("\n=== TTS 不可用时的降级 ===")
    cfg = Config(); cfg.wake_words = []

    class DeadTTS(FakeUp):
        def tts(self, text): raise RuntimeError("down")
    tmp = HERE / "test_deg.jsonl"; tmp.unlink(missing_ok=True)
    a = Assistant(cfg, DeadTTS(), tmp)
    a.up.text = "开始守夜"
    audio, cmd = a.process(mk_pcm())
    assert audio == b"" and cmd == "N:1"
    print("  ✓ TTS 挂了：开始守夜仍返回 N:1（空音频，板子用离线语音确认）")
    a.up.text = "今天天气"
    try:
        a.process(mk_pcm()); raise SystemExit("闲聊+TTS 挂了应当报错")
    except RuntimeError:
        print("  ✓ TTS 挂了且无指令：明确报错（返回 502），不会假装成功")
    tmp.unlink(missing_ok=True)

def test_retry_covers_all_calls():
    print("\n=== 重试覆盖 ASR / 对话 / TTS，且不误重试 4xx ===")
    import urllib.error, urllib.request, server
    cfg = Config(); cfg.base = "http://example.invalid/v1"   # 需要合法 URL，Request 会校验；真正的 _post 保持不变
    plan = {"codes": [], "n": 0}
    class R:
        def __init__(s, b): s.b = b
        def read(s): return s.b
        def __enter__(s): return s
        def __exit__(s, *a): return False
    def fake_urlopen(req, timeout=0):
        plan["n"] += 1
        code = plan["codes"].pop(0) if plan["codes"] else 200
        if code != 200:
            raise urllib.error.HTTPError(req.full_url, code, "x", {}, None)
        return R(b'{"text":"ok","choices":[{"message":{"content":"hi"}}]}')
    orig_u, orig_sleep = urllib.request.urlopen, server.time.sleep
    urllib.request.urlopen, server.time.sleep = fake_urlopen, lambda s: None
    try:
        up = server.Upstream(cfg)
        plan.update(codes=[429, 429], n=0); assert up.asr(mk_pcm()) == "ok" and plan["n"] == 3
        print("  ✓ ASR 429 两次后成功")
        plan.update(codes=[503], n=0); assert up.chat([{"role": "user", "content": "x"}]) == "hi" and plan["n"] == 2
        print("  ✓ 对话 503 一次后成功")
        plan.update(codes=[401], n=0)
        try:
            up.asr(mk_pcm()); raise SystemExit("401 应抛出")
        except urllib.error.HTTPError as e:
            assert e.code == 401 and plan["n"] == 1
        print("  ✓ 401 不重试，立即抛出（密钥错误不该白白等待）")
        plan.update(codes=[429, 429, 429], n=0)
        try:
            up.asr(mk_pcm()); raise SystemExit("应抛出")
        except urllib.error.HTTPError as e:
            assert e.code == 429 and plan["n"] == 3
        print("  ✓ 持续 429 共尝试 3 次后抛出")
    finally:
        urllib.request.urlopen, server.time.sleep = orig_u, orig_sleep


def test_traditional_and_hallucination():
    print("\n=== 繁体转简体 + 幻觉过滤 ===")
    from server import normalize_text, is_hallucination
    assert normalize_text("小夜，開始守夜") == "小夜，开始守夜"
    assert normalize_text("我夢見在海裡游泳") == "我梦见在海里游泳"
    assert normalize_text("今天天氣不錯") == "今天天气不错"
    print("  ✓ 繁体指令转为简体")
    bad = ["MING PAO CANADA // MING PAO TORONTO", "", "嗯", "字幕由Amara.org社群提供", "请不吝点赞订阅",
           "Thanks for watching!", "www.example.com", "1234", "OK"]
    for s in bad:
        assert is_hallucination(normalize_text(s)), f"应过滤: {s!r}"
    print(f"  ✓ {len(bad)} 条幻觉/噪音/无中文被过滤")
    good = ["小夜，开始守夜", "我梦见在海里游泳", "早安", "今天天气不错", "音量调大一点", "晚安"]
    for s in good:
        assert not is_hallucination(normalize_text(s)), f"不应误杀: {s!r}"
    print(f"  ✓ {len(good)} 条正常指令未被误杀")


def test_wake_with_traditional():
    print("\n=== 繁体识别结果仍能唤醒并执行 ===")
    cfg = Config(); cfg.wake_words = ["小夜"]
    up = FakeUp(); tmp = HERE / "test_trad.jsonl"; tmp.unlink(missing_ok=True)
    a = Assistant(cfg, up, tmp)
    up.text = "小夜 開始守夜"
    audio, cmd = a.process(mk_pcm())
    assert cmd == "N:1"
    print("  ✓ '小夜 開始守夜' -> N:1")
    up.text = "MING PAO CANADA"
    cfg.follow_up_s = 20
    assert a.process(mk_pcm()) is None
    print("  ✓ 唤醒窗口内收到幻觉文本也被丢弃，不会当成追问")
    tmp.unlink(missing_ok=True)


def test_followup_survives_slow_upstream():
    print("\n=== 上游很慢时，追问窗口不被重试耗时吃掉（复现上一轮记梦失败）===")
    class Clock: t = 1000.0
    cfg = Config(); cfg.wake_words = ["小夜"]; cfg.follow_up_s = 20
    up = FakeUp(); tmp = HERE / "test_slow.jsonl"; tmp.unlink(missing_ok=True)
    a = Assistant(cfg, up, tmp, lambda: Clock.t)

    # 第 1 句: 唤醒词。上游慢——这句处理完时钟已经走了 12 秒。
    up.text = "小夜，开始守夜"
    orig_asr = up.asr
    def slow_asr(pcm): Clock.t += 6; return orig_asr(pcm)
    def slow_tts(txt): Clock.t += 6; return b"x"
    up.asr, up.tts = slow_asr, slow_tts
    audio, cmd = a.process(mk_pcm())
    assert cmd == "N:1"
    # 第 2 句: 用户听完回复后 9 秒说话，并且这句 ASR 又很慢(6 秒)。
    Clock.t += 9
    up.text = "我梦见在海里游泳"
    res = a.process(mk_pcm())
    assert res is not None, "追问窗口被上游耗时吃掉了"
    assert tmp.exists() and "海里游泳" in tmp.read_text(encoding="utf-8")
    print("  ✓ 第 2 句在回复后 9 秒到达，即使 ASR 自己耗时 6 秒，仍被接受并写入梦境")
    # 第 3 句: 用户沉默 25 秒后再说，应该被拒绝
    Clock.t += 25
    up.text = "今天天气不错"
    assert a.process(mk_pcm()) is None
    print("  ✓ 沉默 25 秒后的话仍被拒绝（窗口确实会过期）")
    tmp.unlink(missing_ok=True)


def test_connection_drop_retry():
    print("\n=== 连接被对端掐断会重试，读超时不重试 ===")
    import http.client, socket, urllib.error, urllib.request, server
    calls = {"n": 0, "plan": []}
    class R:
        def read(s): return b"ok"
        def __enter__(s): return s
        def __exit__(s, *a): return False
    def fake_urlopen(req, timeout=0):
        calls["n"] += 1
        err = calls["plan"].pop(0) if calls["plan"] else None
        if err: raise err
        return R()
    orig_u, orig_s = urllib.request.urlopen, server.time.sleep
    urllib.request.urlopen, server.time.sleep = fake_urlopen, lambda s: None
    try:
        calls.update(n=0, plan=[http.client.RemoteDisconnected("Remote end closed connection without response")])
        assert server._post("http://x.invalid/a", b"", {}) == b"ok" and calls["n"] == 2
        print("  ✓ 'Remote end closed connection' 重试一次后成功")
        calls.update(n=0, plan=[urllib.error.URLError(ConnectionResetError())])
        assert server._post("http://x.invalid/a", b"", {}) == b"ok" and calls["n"] == 2
        print("  ✓ URLError(ConnectionReset) 同样重试")
        calls.update(n=0, plan=[socket.timeout("timed out")])
        try:
            server._post("http://x.invalid/a", b"", {}); raise SystemExit("读超时应抛出")
        except socket.timeout:
            assert calls["n"] == 1
        print("  ✓ 读超时不重试（请求可能已被处理，重试会白等并可能重复计费）")
        calls.update(n=0, plan=[ValueError("别的错误")])
        try:
            server._post("http://x.invalid/a", b"", {}); raise SystemExit("应抛出")
        except ValueError:
            assert calls["n"] == 1
        print("  ✓ 无关的异常原样抛出，不被吞掉")
    finally:
        urllib.request.urlopen, server.time.sleep = orig_u, orig_s


def test_tts_breaker():
    print("\n=== TTS 熔断：连续失败后短时间内不再白等重试 ===")
    import urllib.error, server
    cfg = Config(); cfg.base = "http://x.invalid"
    n = {"c": 0}
    def always_fail(url, body, headers, timeout=30, tries=3):
        n["c"] += 1; raise urllib.error.HTTPError(url, 429, "x", {}, None)
    orig = server._post; server._post = always_fail
    try:
        up = server.Upstream(cfg); up.breaker_fails = 0; up.breaker_until = 0.0
        for _ in range(2):
            try: up.tts("你好")
            except urllib.error.HTTPError: pass
        assert n["c"] == 2 and up.breaker_until > time.time()
        print("  ✓ 连续 2 次失败后熔断 60 秒")
        before = n["c"]
        try: up.tts("你好"); raise SystemExit("熔断中应抛出")
        except RuntimeError as e: assert "熔断" in str(e)
        assert n["c"] == before
        print("  ✓ 熔断期间完全不发请求，立刻失败")
        up.breaker_until = 0.0
        server._post = lambda *a, **k: pcm_to_wav(b"\x01\x00" * 1600)
        assert up.tts("你好") and up.breaker_fails == 0
        print("  ✓ 熔断期过后恢复，成功一次即清零计数")
    finally:
        server._post = orig


if __name__ == "__main__":
    test_gate()
    test_intent()
    test_notes()
    test_audio()
    test_full_flow()
    test_user_agent()
    test_tts_degrade()
    test_retry_covers_all_calls()
    test_traditional_and_hallucination()
    test_wake_with_traditional()
    test_followup_survives_slow_upstream()
    test_connection_drop_retry()
    test_tts_breaker()
    print("\n=== 本地测试全部通过 ===\n下一步: 把 .env.example 复制为 .env 并填入真实 API Key，然后 python3 server.py")
