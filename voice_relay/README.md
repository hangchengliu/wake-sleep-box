# Wake 语音中转服务

板子录音上传 → 本服务做 识别 / 唤醒词门控 / 意图 / 对话 / 合成 → 回给板子播放，并可附带板子要执行的指令。
只用 Python 标准库，无需安装依赖。API Key 只存在 `.env`，该文件已被 `.gitignore` 排除。

## 使用

```bash
cd voice_relay
cp .env.example .env        # 然后自己编辑 .env，填入 Key 和模型名，不要把 Key 贴到聊天里
python3 test_server.py      # 本地逻辑测试，不联网
python3 probe_upstream.py   # 探测上游接口: 模型清单、ASR/对话/TTS 是否可用、TTS 音频格式
python3 server.py           # 启动，默认监听 0.0.0.0:8787
./e2e_check.sh              # 另开终端: 用 say 生成中文语音，走一遍完整链路
```

## 接口

- `POST /api/voice`: body 为 PCM16 16kHz 单声道小端，长度 0.1 到 30 秒。
  - `200`: body 是回复语音 PCM16 16kHz，响应头 `X-Wake-Cmd` 为板子要执行的指令（`N:1` 开始守夜、`N:2` 结束守夜，可为空）。
  - `204`: 没听到唤醒词，板子保持安静。
  - `400` 音频长度不合法，`502` 上游接口出错。
- `GET /api/health`: 返回 `{"ok":true,"missing_env":[...]}`。

## 数据

- 梦境与笔记追加写入 `notes.jsonl`（本机，已被 git 忽略）。
- 对话历史只在内存，重启即清空。

## 隐私边界

- 只有板子「不在守夜」时才会上传录音；守夜期间麦克风仍然只算分贝，不录音、不上传。
- 录音会发给 `.env` 里配置的上游服务做识别，演示时应当如实说明。
