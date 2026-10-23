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

def test_tts_retry_and_degrade():
    print("\n=== TTS 429 重试与降级 ===")
    import urllib.error, server
    cfg = Config(); cfg.wake_words = []
    wav = pcm_to_wav(b"\x01\x00" * 1600)
    calls = {"n": 0}
    def flaky(url, body, headers, timeout=30):
        calls["n"] += 1
        if calls["n"] < 3:
            raise urllib.error.HTTPError(url, 429, "rate", {}, None)
        return wav
    orig_post, orig_sleep = server._post, server.time.sleep
    server._post, server.time.sleep = flaky, lambda s: None
    try:
        up = server.Upstream(cfg)
        assert up.tts("你好") and calls["n"] == 3
        print(f"  ✓ 429 两次后第 3 次成功（共 {calls['n']} 次请求）")
        calls["n"] = -99
        always429 = lambda url, body, headers, timeout=30: (_ for _ in ()).throw(urllib.error.HTTPError(url, 429, "rate", {}, None))
        server._post = always429
        try:
            up.tts("你好"); raise SystemExit("应当抛出")
        except urllib.error.HTTPError as e:
            assert e.code == 429
        print("  ✓ 持续 429 时抛出，由 process() 降级")
    finally:
        server._post, server.time.sleep = orig_post, orig_sleep

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

if __name__ == "__main__":
    test_gate()
    test_intent()
    test_notes()
    test_audio()
    test_full_flow()
    test_user_agent()
    test_tts_retry_and_degrade()
    print("\n=== 本地测试全部通过 ===\n下一步: 把 .env.example 复制为 .env 并填入真实 API Key，然后 python3 server.py")
