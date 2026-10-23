# Opendev API 接口清单

**你需要在 Opendev 文档里找到这些信息，填入 `voice_relay/.env` 文件：**

---

## 1. API Base URL 与 Key

```bash
OPENDEV_BASE_URL=https://api.opendev.ai/v1  # ← 把这个替换成 Opendev 给你的实际接口地址
OPENDEV_API_KEY=sk-xxxxx...                  # ← 你的 API Key
```

**我需要确认：**
- ✅ Opendev 的 API 是否兼容 OpenAI 格式？（`/v1/audio/transcriptions`, `/v1/chat/completions`, `/v1/audio/speech`）
- ✅ 如果不兼容，接口的实际路径是什么？

---

## 2. 语音识别（ASR）

服务调用：`POST {BASE_URL}/audio/transcriptions`

请求参数（multipart/form-data）：
- `file`: WAV 音频（16kHz 单声道 16bit PCM）
- `model`: ASR 模型名称
- `language`: "zh"

返回：`{"text": "识别出的文字"}`

**我需要你在 Opendev 文档找到：**
- ✅ 支持的 ASR 模型名（例如 `whisper-1` / `whisper-large` / ...）

```bash
ASR_MODEL=whisper-1  # ← 替换成真实模型名
```

---

## 3. 对话生成（Chat）

服务调用：`POST {BASE_URL}/chat/completions`

请求参数（JSON）：
```json
{
  "model": "gpt-4o-mini",
  "messages": [{"role": "user", "content": "你好"}],
  "max_tokens": 160,
  "temperature": 0.7
}
```

返回：`{"choices": [{"message": {"content": "回复文本"}}]}`

**我需要你在 Opendev 文档找到：**
- ✅ 对话模型名（例如 `gpt-4o-mini` / `gpt-3.5-turbo` / 其他模型）

```bash
CHAT_MODEL=gpt-4o-mini  # ← 替换成真实模型名
```

---

## 4. 语音合成（TTS）

服务调用：`POST {BASE_URL}/audio/speech`

请求参数（JSON）：
```json
{
  "model": "tts-1",
  "voice": "alloy",
  "input": "要合成的文本",
  "response_format": "wav"
}
```

返回：WAV 音频二进制流

**我需要你在 Opendev 文档找到：**
- ✅ TTS 模型名（例如 `tts-1` / `tts-hd` / ...）
- ✅ 支持的音色（`alloy` / `echo` / `nova` / ...）
- ✅ `response_format` 是否支持 `wav`（如果只支持 `mp3`，告诉我，我需要改解码逻辑）

```bash
TTS_MODEL=tts-1          # ← 替换成真实模型名
TTS_VOICE=alloy          # ← 替换成真实音色名
```

---

## 5. 唤醒词（可选）

你希望板子听到什么词才开始识别？多个用逗号分隔：

```bash
WAKE_WORDS=小夜,晓夜,小也
```

如果留空，表示关闭唤醒词门控，每次录音都识别。

---

## 6. 其他配置（保持默认即可）

```bash
FOLLOW_UP_SECONDS=20  # 唤醒后连续对话窗口秒数
PORT=8787             # 中转服务监听端口
```

---

## 接下来的步骤

1. 把上面清单里**加粗✅的信息**找到，填入 `voice_relay/.env`
2. 告诉我 Opendev 的 API 是否完全兼容 OpenAI 格式（路径、参数、返回值）
3. 如果不兼容，把 Opendev 的 API 文档链接或关键差异告诉我

我马上改代码。
