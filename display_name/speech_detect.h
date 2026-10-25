// 说话检测(VAD)状态机。纯 C++，不依赖 Arduino/ESP-IDF，所以可以在电脑上用合成音频做单元测试。
// 输入: 每 16ms 一帧(256 采样 @16kHz)的 PCM16 单声道。
// 输出: 起讲/收尾事件；录到的整段话(含起讲前的预滚动)写进调用方给的缓冲区。
#pragma once
#include <stdint.h>
#include <string.h>
#include <stdlib.h>
#include <math.h>

#define SD_FRAME      256                    // 一帧采样数，16ms
#define SD_PREROLL_F  14                     // 预滚动 14 帧 ≈ 224ms，避免“小夜”起头被切掉
#define SD_START_F    3                      // 连续 3 帧高于起讲门限才算开始说话(≈48ms，滤掉敲桌声)
#define SD_HANG_F     44                     // 连续 44 帧(≈700ms)低于收尾门限才算说完
#define SD_MIN_F      18                     // 有效语音至少 18 帧(≈290ms)，更短的当噪声丢弃
#define SD_MAX_F      1500                   // 最长 1500 帧 = 24 秒；服务端上限 30 秒，留余量
#define SD_FLAT_F     125                    // 能量平稳持续 125 帧(≈2 秒)判为持续噪声
#define SD_NOISE_MAX  4000.0f                // 噪声底上限：再吵就不是“环境底噪”了，宁可不识别也不无限抬高门限
#define SD_WARM_F     62                     // 冷启动静听 62 帧 ≈ 1 秒
#define SD_BUF_SAMPLES ((SD_MAX_F + SD_PREROLL_F + 2) * SD_FRAME)   // 缓冲区容量(采样数): 上限 + 预滚动 + 余量

enum SdEvent { SD_NONE = 0, SD_SPEECH_START = 1, SD_SPEECH_END = 2, SD_TOO_SHORT = 3, SD_OVERFLOW = 4 };

struct SpeechDetector {
    // 缓冲区由调用方分配(板子上放 PSRAM)，容量以采样数计。
    int16_t *buf = nullptr;
    uint32_t cap = 0;
    uint32_t len = 0;                        // 当前缓冲区里有效采样数

    float noise = 300.0f;                    // 自适应噪声底(帧 RMS)
    float start_mult = 3.0f;                 // 起讲门限 = max(noise*start_mult, min_start)
    float stop_mult = 1.8f;                  // 收尾门限 = max(noise*stop_mult, min_stop)
    float min_start = 700.0f;                // 绝对下限，避免在极安静环境里被底噪触发
    float min_stop = 400.0f;

    bool in_speech = false;
    int hi_run = 0;                          // 连续高能量帧
    int lo_run = 0;                          // 说话中连续低能量帧
    float run_mean = 0, run_dev = 0;         // 说话态里帧能量的慢速均值与平均偏差
    int flat_run = 0;                        // 连续“能量过于平稳”的帧数
    uint32_t speech_frames = 0;
    int16_t pre[SD_PREROLL_F][SD_FRAME];     // 预滚动环形缓冲
    int pre_n = 0, pre_head = 0;

    int warm = 0;                            // 冷启动校准：已听的帧数。开机/复位后先静听 SD_WARM_F 帧学噪声底，不触发

    void init(int16_t *buffer, uint32_t capacity_samples) {
        buf = buffer; cap = capacity_samples; reset(); warm = 0;
    }
    void reset() {
        len = 0; in_speech = false; hi_run = lo_run = 0; speech_frames = 0; pre_n = pre_head = 0;
        run_mean = run_dev = 0; flat_run = 0;
    }
    // 重新校准：噪声底设为“未知”，下一段 SD_WARM_F 帧只学习不触发。（例如播完提示音、守夜结束后调用）
    void recalibrate() { reset(); warm = 0; noise = -1; }

    static float frame_rms(const int16_t *x) {
        // 先去直流再算 RMS，ES7210 的输出常带偏置
        int64_t s = 0;
        for (int i = 0; i < SD_FRAME; i++) s += x[i];
        float mean = (float)s / SD_FRAME, acc = 0;
        for (int i = 0; i < SD_FRAME; i++) { float d = x[i] - mean; acc += d * d; }
        float r = acc / SD_FRAME;
        return r > 0 ? sqrtf(r) : 0;          // 标准库开方。之前手写牛顿迭代在大幅度信号上严重偏高(±3000 算成 17748)
    }

    SdEvent push(const int16_t *x) {
        float e = frame_rms(x);

        // 冷启动：这 1 秒里不判断说话，只用帧能量的滑动均值直接定出噪声底。
        // 首帧直接采用（noise<0 表示未知），之后用较快的系数收敛。
        if (warm < SD_WARM_F) {
            noise = (noise < 0) ? e : noise + 0.15f * (e - noise);
            warm++;
            memcpy(pre[pre_head], x, sizeof(pre[0]));
            pre_head = (pre_head + 1) % SD_PREROLL_F;
            if (pre_n < SD_PREROLL_F) pre_n++;
            return SD_NONE;
        }
        if (noise < 0) noise = e;
        float t_start = noise * start_mult; if (t_start < min_start) t_start = min_start;
        float t_stop  = noise * stop_mult;  if (t_stop  < min_stop)  t_stop  = min_stop;

        if (!in_speech) {
            // 只在”安静”时更新噪声底，防止把说话声学进去。快速下降、慢速上升。
            // t_start 现在还是上一轮的门限(如果 noise 刚跳高它还没跟上),所以:
            // 当前 noise 更低时(e > noise),慢速上拉(避免语音拉高它);
            // 当前 noise 更高时(e < noise),快速下降(跟不上说话);
            // 但无论哪种,都只在 e 还没越过旧门限时才学习,一旦越过就进语音判断流程。
            if (e < t_start) {
                noise += (e > noise ? 0.02f : 0.10f) * (e - noise);
                if (noise > SD_NOISE_MAX) noise = SD_NOISE_MAX;
            }
            memcpy(pre[pre_head], x, sizeof(pre[0]));
            pre_head = (pre_head + 1) % SD_PREROLL_F;
            if (pre_n < SD_PREROLL_F) pre_n++;

            hi_run = (e >= t_start) ? hi_run + 1 : 0;
            if (hi_run >= SD_START_F) {
                // 起讲：把预滚动按时间顺序拷进缓冲区
                len = 0;
                int first = (pre_head - pre_n + SD_PREROLL_F) % SD_PREROLL_F;
                for (int k = 0; k < pre_n && len + SD_FRAME <= cap; k++) {
                    memcpy(buf + len, pre[(first + k) % SD_PREROLL_F], sizeof(pre[0]));
                    len += SD_FRAME;
                }
                // speech_frames 只统计“起讲之后”的有效语音帧，预滚动不算，否则咳嗽也会凑够最小时长。
                // 触发起讲的那 SD_START_F 帧已经在预滚动里，所以从 SD_START_F 开始记。
                in_speech = true; lo_run = 0; speech_frames = SD_START_F; hi_run = 0;
                run_mean = e; run_dev = e * 0.5f; flat_run = 0;
                return SD_SPEECH_START;
            }
            return SD_NONE;
        }

        // 说话中：追加
        if (len + SD_FRAME > cap) { in_speech = false; return SD_OVERFLOW; }
        memcpy(buf + len, x, sizeof(pre[0]));
        len += SD_FRAME; speech_frames++;
        lo_run = (e < t_stop) ? lo_run + 1 : 0;

        // 能量几乎不起伏 = 持续噪声(空调、风扇、展馆人声底噪)，不是语音。语音有音节起伏，
        // 帧能量的变化幅度大。用能量的慢速均值/方差判断；平稳超过约 2 秒就放弃这一段，
        // 并把噪声底直接抬到当前水平，之后重新检测。
        run_mean += 0.05f * (e - run_mean);
        float dev = e > run_mean ? e - run_mean : run_mean - e;
        run_dev += 0.05f * (dev - run_dev);
        flat_run = (speech_frames > 20 && run_dev < 0.15f * run_mean) ? flat_run + 1 : 0;
        if (flat_run >= SD_FLAT_F) {
            // 把噪声底抬到刚好让新的起讲门限略高于这段平稳噪声，避免立刻重复触发。
            // 例: 平稳能量 3000, start_mult=3, 则 noise = 3000/3*1.2 = 1200, 新门限 3600 > 3000, 不再触发。
            noise = run_mean / start_mult * 1.2f;
            if (noise < 100) noise = 100;
            if (noise > SD_NOISE_MAX) noise = SD_NOISE_MAX;
            in_speech = false; len = 0; speech_frames = 0; lo_run = hi_run = 0; flat_run = 0;
            return SD_TOO_SHORT;
        }

        if (speech_frames >= SD_MAX_F) { in_speech = false; return SD_SPEECH_END; }   // 超长强制截断
        if (lo_run >= SD_HANG_F) {
            in_speech = false;
            // 有效语音帧 = 起讲后记录的帧数 - 末尾静音帧数
            uint32_t voiced = speech_frames - (uint32_t)lo_run;
            // 去掉尾部静音，只保留约 150ms(9 帧)收尾
            uint32_t trim = (uint32_t)(lo_run - 9) * SD_FRAME;
            len = (len > trim) ? len - trim : len;
            return (voiced >= SD_MIN_F) ? SD_SPEECH_END : SD_TOO_SHORT;
        }
        return SD_NONE;
    }
};
