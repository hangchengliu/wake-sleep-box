// 板载语音对话: 蓝牙配网(Wi-Fi/服务器地址存 NVS) + 说话检测 + 上传录音 + 播放回复 + 执行指令。
// 依赖 display_name.ino 里的: tx_handle, audio_ok, speaker_vol, speaker_muted, night_mode,
// last_sound_end_ms, pending_night, pending_page, pending_sound, voice_say()/voice_playing。
// 守夜期间(night_mode)不录音、不上传，麦克风仍只算分贝——这是产品的隐私边界。
#pragma once
#include <WiFi.h>
#include <HTTPClient.h>
#include <Preferences.h>
#include "speech_detect.h"

// ---------- 配置(来自 NVS，手机通过蓝牙写入，不进源码、不进 git) ----------
struct ChatCfg {
    char ssid[33] = "";
    char pass[65] = "";
    char server[96] = "";                // 形如 http://172.20.10.2:8787
    bool enabled = false;                // 配置完整且用户没关闭
};
static ChatCfg chat_cfg;
static Preferences chat_prefs;

enum ChatState : uint8_t {
    CS_OFF = 0,          // 未配置
    CS_WIFI_CONNECTING,  // 正在连 Wi-Fi
    CS_READY,            // 在线，听着
    CS_RECORDING,        // 检测到有人说话，正在录
    CS_UPLOADING,        // 上传并等待回复
    CS_PLAYING,          // 播放回复
    CS_ERROR             // 出错(见 chat_last_err)，一段时间后自动恢复
};
static volatile ChatState chat_state = CS_OFF;
static char chat_last_err[48] = "";
static volatile uint32_t chat_err_until = 0;

static SpeechDetector chat_vad;
static int16_t *chat_buf = nullptr;      // 录音缓冲区，放 PSRAM
static uint8_t *chat_reply = nullptr;    // 回复音频缓冲区，放 PSRAM
static const uint32_t CHAT_REPLY_CAP = 16000 * 2 * 20;       // 最多 20 秒回复
static volatile uint32_t chat_reply_len = 0;
static char chat_reply_cmd[8] = "";      // 服务端经 X-Wake-Cmd 返回的板子指令
static volatile bool chat_job_ready = false;                  // 录好一段，等上传任务取走
static volatile uint32_t chat_job_samples = 0;
static TaskHandle_t chat_net_task = nullptr;
static uint32_t chat_wifi_try_ms = 0;
static uint32_t chat_wifi_fail = 0;
static volatile uint32_t chat_cooldown_until = 0;            // 播放/提示音之后的静默期，避免听到自己
static volatile int chat_wifi_progress = 0;                  // 0..100 Wi-Fi 连接进度
static volatile uint32_t chat_wifi_connected_ms = 0;         // 连接成功时刻
static volatile int chat_wifi_rssi = -100;                   // 实时 RSSI (dBm)
static volatile uint32_t wifi_banner_until = 0;              // 强制显示 WiFi 卡片截止时刻

static void chat_set_err(const char *m) {
    snprintf(chat_last_err, sizeof(chat_last_err), "%s", m);
    chat_state = CS_ERROR;
    chat_err_until = millis() + 4000;
    Serial.printf("[Chat] 错误: %s\n", m);
}

// ---------- NVS ----------
static void chat_load_cfg() {
    chat_prefs.begin("wakechat", true);
    chat_prefs.getString("ssid", chat_cfg.ssid, sizeof(chat_cfg.ssid));
    chat_prefs.getString("pass", chat_cfg.pass, sizeof(chat_cfg.pass));
    chat_prefs.getString("server", chat_cfg.server, sizeof(chat_cfg.server));
    chat_cfg.enabled = chat_prefs.getBool("on", false);
    chat_prefs.end();
    if (!chat_cfg.ssid[0] || !chat_cfg.server[0]) chat_cfg.enabled = false;
}

static void chat_save_cfg() {
    chat_prefs.begin("wakechat", false);
    chat_prefs.putString("ssid", chat_cfg.ssid);
    chat_prefs.putString("pass", chat_cfg.pass);
    chat_prefs.putString("server", chat_cfg.server);
    chat_prefs.putBool("on", chat_cfg.enabled);
    chat_prefs.end();
}

// 配置写入后触发重连。由 BLE 回调设置标志，主循环里处理，避免在 BLE 任务里做耗时操作。
static volatile bool chat_cfg_dirty = false;

// 解析并应用 "C:ssid|pass|server" 格式。分隔符用 '|'。任何一项过长都拒绝，不截断。
static bool chat_apply_cfg_line(const String &payload) {
    int p1 = payload.indexOf('|');
    int p2 = payload.indexOf('|', p1 + 1);
    if (p1 < 1 || p2 < 0) return false;
    String ssid = payload.substring(0, p1), pass = payload.substring(p1 + 1, p2), srv = payload.substring(p2 + 1);
    ssid.trim(); srv.trim();
    if (ssid.length() == 0 || ssid.length() > 32 || pass.length() > 64 || srv.length() < 8 || srv.length() > 95) return false;
    if (!srv.startsWith("http://")) return false;                 // 局域网内明文，演示足够；不支持 https
    snprintf(chat_cfg.ssid, sizeof(chat_cfg.ssid), "%s", ssid.c_str());
    snprintf(chat_cfg.pass, sizeof(chat_cfg.pass), "%s", pass.c_str());
    snprintf(chat_cfg.server, sizeof(chat_cfg.server), "%s", srv.c_str());
    chat_cfg.enabled = true;
    chat_save_cfg();
    chat_cfg_dirty = true;
    Serial.printf("[Chat] 已保存配置: ssid=%s server=%s (密码不打印)\n", chat_cfg.ssid, chat_cfg.server);
    return true;
}

// ---------- 播放回复(主循环外的网络任务里调用) ----------
static void chat_play_reply(const uint8_t *pcm, uint32_t bytes) {
    if (!audio_ok || !tx_handle || speaker_muted || bytes < 640) return;
    int16_t buf[256 * 2];
    const int16_t *s = (const int16_t *)pcm;
    uint32_t n = bytes / 2, done = 0;
    while (done < n) {
        int chunk = (int)min((uint32_t)256, n - done);
        for (int i = 0; i < chunk; i++) {
            int16_t v = (int16_t)((int32_t)s[done + i] * speaker_vol / 100);
            buf[i * 2] = v; buf[i * 2 + 1] = v;
        }
        size_t bw = 0;
        i2s_channel_write(tx_handle, buf, chunk * 4, &bw, 100);
        done += chunk;
        last_sound_end_ms = millis();
    }
    // 尾部补 120ms 静音，让 I2S DMA 把最后一块真正播完再恢复收音
    memset(buf, 0, sizeof(buf));
    for (int g = 1920; g > 0; g -= 256) { size_t bw = 0; i2s_channel_write(tx_handle, buf, min(g, 256) * 4, &bw, 100); }
    last_sound_end_ms = millis();
}

// ---------- 网络任务: 连 Wi-Fi、上传、取回复。放在核心 0，不阻塞主循环的屏幕/麦克风 ----------
static void chat_net_fn(void *) {
    for (;;) {
        // 1) 配置变更 -> 断开重连
        if (chat_cfg_dirty) {
            chat_cfg_dirty = false;
            WiFi.disconnect(true, false);
            chat_wifi_fail = 0;
            vTaskDelay(pdMS_TO_TICKS(200));
        }
        if (!chat_cfg.enabled) { chat_state = CS_OFF; vTaskDelay(pdMS_TO_TICKS(300)); continue; }

        // 2) 保持 Wi-Fi 连接，失败按指数退避，最多 30 秒试一次
        if (WiFi.status() != WL_CONNECTED) {
            if (chat_state != CS_ERROR) chat_state = CS_WIFI_CONNECTING;
            uint32_t now = millis();
            // 退避: 3s, 6s, 12s, 24s, 之后封顶 30s。不用 min() 模板，避免 uint32_t 与 unsigned 的推导冲突。
            uint32_t shift = chat_wifi_fail > 4 ? 4 : (uint32_t)chat_wifi_fail;
            uint32_t wait = (uint32_t)3000 << shift;
            if (wait > 30000) wait = 30000;
            if (now - chat_wifi_try_ms > wait || chat_wifi_try_ms == 0) {
                chat_wifi_try_ms = now;
                WiFi.mode(WIFI_STA);
                WiFi.begin(chat_cfg.ssid, chat_cfg.pass);
                Serial.printf("[Chat] 连接 Wi-Fi: %s\n", chat_cfg.ssid);
                for (int i = 0; i < 100 && WiFi.status() != WL_CONNECTED; i++) {
                    chat_wifi_progress = i + 1;
                    vTaskDelay(pdMS_TO_TICKS(100));
                }
                if (WiFi.status() == WL_CONNECTED) {
                    chat_wifi_fail = 0;
                    chat_wifi_progress = 100;
                    chat_wifi_connected_ms = millis();
                    chat_wifi_rssi = WiFi.RSSI();
                    wifi_banner_until = millis() + 4000;
                    Serial.printf("[Chat] Wi-Fi 已连接 IP=%s RSSI=%d\n", WiFi.localIP().toString().c_str(), (int)chat_wifi_rssi);
                } else {
                    chat_wifi_fail++;
                    chat_wifi_progress = 0;
                    chat_set_err("Wi-Fi 连接失败");
                }
            }
            vTaskDelay(pdMS_TO_TICKS(200));
            continue;
        }
        if (WiFi.status() == WL_CONNECTED) {
            static uint32_t last_rssi_check = 0;
            if (millis() - last_rssi_check >= 2000) {
                last_rssi_check = millis();
                chat_wifi_rssi = WiFi.RSSI();
            }
        }
        if (chat_state == CS_WIFI_CONNECTING || chat_state == CS_OFF) chat_state = CS_READY;
        if (chat_state == CS_ERROR && millis() > chat_err_until) chat_state = CS_READY;

        // 3) 有录好的音频就上传
        if (chat_job_ready) {
            uint32_t bytes = chat_job_samples * 2;
            chat_state = CS_UPLOADING;
            HTTPClient http;
            String url = String(chat_cfg.server) + "/api/voice";
            http.setConnectTimeout(4000);
            http.setTimeout(45000);                              // 服务端可能要重试上游 429
            const char *want[] = {"X-Wake-Cmd"};
            bool ok = http.begin(url);
            if (ok) {
                http.collectHeaders(want, 1);
                http.addHeader("Content-Type", "application/octet-stream");
                int code = http.POST((uint8_t *)chat_buf, bytes);
                Serial.printf("[Chat] POST %u 字节 -> HTTP %d\n", (unsigned)bytes, code);
                chat_reply_cmd[0] = 0;
                if (code == 200) {
                    String cmd = http.header("X-Wake-Cmd");
                    snprintf(chat_reply_cmd, sizeof(chat_reply_cmd), "%s", cmd.c_str());
                    int len = http.getSize();
                    uint32_t got = 0;
                    if (len > 0 && (uint32_t)len <= CHAT_REPLY_CAP) {
                        WiFiClient *st = http.getStreamPtr();
                        uint32_t t0 = millis();
                        while (got < (uint32_t)len && millis() - t0 < 20000) {
                            int avail = st->available();
                            if (avail > 0) got += st->read(chat_reply + got, min((uint32_t)avail, (uint32_t)len - got));
                            else vTaskDelay(pdMS_TO_TICKS(5));
                        }
                    } else if (len > (int)CHAT_REPLY_CAP) {
                        Serial.printf("[Chat] 回复 %d 字节超过上限，丢弃音频\n", len);
                    }
                    chat_reply_len = got;
                } else if (code == 204) {
                    chat_reply_len = 0;                          // 没听到唤醒词: 静默，不打扰
                } else {
                    chat_reply_len = 0;
                    chat_set_err(code < 0 ? "连不上服务器" : "服务器出错");
                }
                http.end();
            } else {
                chat_set_err("服务器地址无效");
            }
            chat_job_ready = false;

            // 4) 先执行指令(例如开始守夜)，再播放回复。守夜指令会让屏幕熄灭，所以语音要在它之前播完。
            if (chat_reply_len > 0) {
                chat_state = CS_PLAYING;
                chat_play_reply(chat_reply, chat_reply_len);
                chat_reply_len = 0;
            }
            if (chat_reply_cmd[0]) {
                if (!strcmp(chat_reply_cmd, "N:1")) pending_night = 1;
                else if (!strcmp(chat_reply_cmd, "N:2")) pending_night = 2;
                chat_reply_cmd[0] = 0;
            }
            chat_cooldown_until = millis() + 600;
            if (chat_state != CS_ERROR) chat_state = CS_READY;
        }
        vTaskDelay(pdMS_TO_TICKS(30));
    }
}

static void chat_init() {
    chat_buf = (int16_t *)heap_caps_malloc(SD_BUF_SAMPLES * sizeof(int16_t), MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    chat_reply = (uint8_t *)heap_caps_malloc(CHAT_REPLY_CAP, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    if (!chat_buf || !chat_reply) {
        Serial.println("[Chat] PSRAM 分配失败，语音对话禁用");
        return;
    }
    chat_vad.init(chat_buf, SD_BUF_SAMPLES);
    chat_load_cfg();
    Serial.printf("[Chat] 配置: %s\n", chat_cfg.enabled ? "已有，将联网" : "未配置，等待手机蓝牙配网");
    // 栈 8KB: HTTPClient + String 需要空间。优先级 1，与 loop 相同，核心 0。
    xTaskCreatePinnedToCore(chat_net_fn, "chatnet", 8192, nullptr, 1, &chat_net_task, 0);
}

// ---------- 由 poll_microphone() 每读到 256 帧立体声调用一次: 取左声道喂给说话检测 ----------
static void chat_feed_left(const int16_t *stereo, int frames) {
    if (!chat_buf || !chat_cfg.enabled) return;
    // 这些时刻不该听: 守夜中(隐私)、没联网、正在上传/播放、自己刚发过声、冷却期内
    bool deaf = night_mode || WiFi.status() != WL_CONNECTED ||
                chat_state == CS_UPLOADING || chat_state == CS_PLAYING || chat_job_ready ||
                (millis() - last_sound_end_ms < 700) || millis() < chat_cooldown_until || voice_playing;
    static bool was_deaf = true;
    if (deaf) {
        if (!was_deaf) { chat_vad.recalibrate(); was_deaf = true; }   // 恢复收音时重新测噪声底，不用旧值
        return;
    }
    was_deaf = false;
    if (frames < SD_FRAME) return;
    int16_t mono[SD_FRAME];
    for (int i = 0; i < SD_FRAME; i++) mono[i] = stereo[i * 2];

    SdEvent ev = chat_vad.push(mono);
    if (ev == SD_SPEECH_START) { chat_state = CS_RECORDING; Serial.println("[Chat] 开始说话"); }
    else if (ev == SD_SPEECH_END) {
        Serial.printf("[Chat] 说完了 %.2f 秒，上传\n", chat_vad.len / 16000.0f);
        // 交接: 先记下长度再置位。chat_buf 在网络任务上传期间归它独占——上面的 deaf 条件含
        // chat_job_ready，所以上传完成前 VAD 不会 push，也就不会往 chat_buf 里写新语音。
        chat_job_samples = chat_vad.len;
        chat_job_ready = true;
        chat_vad.reset();                      // 只清状态位，不动缓冲区内容
    } else if (ev == SD_TOO_SHORT || ev == SD_OVERFLOW) {
        chat_state = CS_READY; chat_vad.reset();
    }
}

static const char *chat_state_name() {
    switch (chat_state) {
        case CS_OFF: return "off";
        case CS_WIFI_CONNECTING: return "wifi";
        case CS_READY: return "ready";
        case CS_RECORDING: return "rec";
        case CS_UPLOADING: return "up";
        case CS_PLAYING: return "play";
        case CS_ERROR: return "err";
    }
    return "?";
}
