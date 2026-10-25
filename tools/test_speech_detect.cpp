// 在电脑上编译运行: c++ -std=c++17 -O1 -I display_name tools/test_speech_detect.cpp -o "$TMPDIR/sd_test" && "$TMPDIR/sd_test"
#include "speech_detect.h"
#include <cmath>
#include <cstdio>
#include <vector>
#include <random>

static std::mt19937 rng(42);

// 生成 n 帧: 噪声底 amp_noise；speech=true 时叠加 180~900Hz 的“语音”(幅度 amp_sp)
static std::vector<int16_t> make(int frames, float amp_noise, bool speech, float amp_sp, int dc = 0) {
    std::vector<int16_t> v((size_t)frames * SD_FRAME);
    std::normal_distribution<float> nd(0.f, 1.f);
    static double ph = 0;
    for (size_t i = 0; i < v.size(); i++) {
        float s = nd(rng) * amp_noise;
        if (speech) {
            // 真人语音有明显的音节起伏(约 4 Hz，能量在 0.1~1 之间摆动)，不是平稳音。
            float syl = 0.55f + 0.45f * sinf((float)i / 260.f);                // 约 4Hz 的音节节奏
            float word = 0.5f + 0.5f * sinf((float)i / 3100.f);                // 词与词之间的停顿
            float env = syl * (0.25f + 0.75f * word);
            ph += 0.09;
            s += amp_sp * env * (sinf((float)ph) + 0.5f * sinf((float)(ph * 2.3)));
        }
        v[i] = (int16_t)fmaxf(-32768.f, fminf(32767.f, s + dc));
    }
    return v;
}

struct Result { int starts = 0, ends = 0, shorts = 0, overflows = 0; uint32_t last_len = 0; };

// 冷启动：先喂 SD_WARM_F 帧该环境的背景声让检测器自行校准，然后才放入被测音频。
static void warm_up(SpeechDetector &d, float amp_noise) {
    d.recalibrate();
    auto bg = make(SD_WARM_F, amp_noise, false, 0);
    for (size_t o = 0; o + SD_FRAME <= bg.size(); o += SD_FRAME) d.push(&bg[o]);
}

static Result run(SpeechDetector &d, const std::vector<int16_t> &pcm) {
    Result r;
    for (size_t o = 0; o + SD_FRAME <= pcm.size(); o += SD_FRAME) {
        switch (d.push(&pcm[o])) {
            case SD_SPEECH_START: r.starts++; break;
            case SD_SPEECH_END: r.ends++; r.last_len = d.len; break;
            case SD_TOO_SHORT: r.shorts++; break;
            case SD_OVERFLOW: r.overflows++; break;
            default: break;
        }
    }
    return r;
}

static int fails = 0;
#define CHECK(cond, msg) do { if (cond) printf("  ✓ %s\n", msg); else { printf("  ✗ %s\n", msg); fails++; } } while (0)

static std::vector<int16_t> cat(std::initializer_list<std::vector<int16_t>> parts) {
    std::vector<int16_t> o; for (auto &p : parts) o.insert(o.end(), p.begin(), p.end()); return o;
}

int main() {
    static int16_t buf[SD_BUF_SAMPLES];
    SpeechDetector d; d.init(buf, SD_BUF_SAMPLES);

    printf("1) 安静环境 + 一句 1.5 秒的话\n");
    warm_up(d, 120);
    auto a = cat({make(60, 120, false, 0), make(94, 120, true, 4000), make(80, 120, false, 0)});
    auto r = run(d, a);
    CHECK(r.starts == 1 && r.ends == 1, "检测到 1 次起讲、1 次收尾");
    float sec = r.last_len / 16000.f;
    printf("     录音时长 %.2f 秒(话 1.5 秒 + 预滚动 0.22 + 收尾约 0.15)\n", sec);
    CHECK(sec > 1.6f && sec < 2.2f, "时长在合理范围，收尾静音已被裁掉");

    printf("2) 预滚动: 起讲前的片段确实被带进来\n");
    warm_up(d, 100);
    auto b = cat({make(40, 100, false, 0), make(60, 100, true, 4000), make(60, 100, false, 0)});
    r = run(d, b);
    CHECK(r.ends == 1 && r.last_len >= (uint32_t)(60 + 14 - 12) * SD_FRAME, "录音长度包含预滚动(不是从起讲后才开始)");

    printf("3) 展馆环境: 持续背景噪声(幅度 900)里说话\n");
    warm_up(d, 900);
    auto c = cat({make(200, 900, false, 0), make(90, 900, true, 6000), make(80, 900, false, 0)});
    r = run(d, c);
    CHECK(r.starts == 1 && r.ends == 1, "噪声底自适应后仍能正确切出一句话");
    printf("     自适应后的噪声底 = %.0f(初始 300)\n", d.noise);
    CHECK(d.noise > 600, "噪声底确实跟上了环境");

    printf("4) 纯噪声不触发(持续 30 秒)\n");
    warm_up(d, 500);
    r = run(d, make(1900, 500, false, 0));
    CHECK(r.starts == 0, "30 秒纯噪声 0 次触发");

    printf("5) 敲桌子 / 关门: 极短冲击不触发\n");
    warm_up(d, 120);
    auto k = cat({make(100, 120, false, 0), make(2, 120, true, 12000), make(100, 120, false, 0)});
    r = run(d, k);
    CHECK(r.starts == 0, "2 帧冲击(32ms)不触发起讲");

    printf("6) 咳嗽/短音: 触发了也会被当成过短丢弃\n");
    warm_up(d, 120);
    auto s = cat({make(100, 120, false, 0), make(8, 120, true, 5000), make(80, 120, false, 0)});
    r = run(d, s);
    CHECK(r.ends == 0, "短于 0.29 秒的声音不会当成有效语音");
    printf("     (starts=%d shorts=%d ends=%d)\n", r.starts, r.shorts, r.ends);

    printf("7) 一直说话超过上限会被强制截断，不会溢出缓冲区\n");
    warm_up(d, 120);
    r = run(d, cat({make(30, 120, false, 0), make(1700, 120, true, 4000)}));
    CHECK(r.ends == 1 && r.overflows == 0, "到 24 秒强制结束，无溢出");
    CHECK(r.last_len <= (uint32_t)SD_FRAME * SD_MAX_F + SD_FRAME * SD_PREROLL_F, "长度不超过上限");

    printf("8) 带直流偏置的信号(ES7210 常见)\n");
    warm_up(d, 120);
    auto dc = cat({make(80, 120, false, 0, 3000), make(90, 120, true, 4000, 3000), make(80, 120, false, 0, 3000)});
    r = run(d, dc);
    CHECK(r.starts == 1 && r.ends == 1, "直流偏置 3000 不影响判断");

    printf("9) 连续两句话, 中间停顿 1 秒\n");
    warm_up(d, 120);
    auto two = cat({make(60, 120, false, 0), make(70, 120, true, 4000), make(75, 120, false, 0),
                    make(70, 120, true, 4000), make(80, 120, false, 0)});
    r = run(d, two);
    CHECK(r.starts == 2 && r.ends == 2, "切成 2 段");

    printf("10) 持续平稳的大噪声(空调/风扇)突然开启，不会一直录\n");
    warm_up(d, 120);
    r = run(d, cat({make(60, 120, false, 0), make(400, 3000, false, 0)}));
    CHECK(r.starts <= 2 && !d.in_speech, "最多误触发 2 次，随后噪声底抬高，不再卡在录音态");
    printf("     (starts=%d shorts=%d, 噪声底→%.0f)\n", r.starts, r.shorts, d.noise);

    printf("11) 开机时环境就已经很吵(900)：冷启动校准后不会被卡在录音态\n");
    warm_up(d, 900);
    r = run(d, cat({make(50, 900, false, 0), make(90, 900, true, 6000), make(80, 900, false, 0)}));
    CHECK(r.starts == 1 && r.ends == 1, "开机即吵：校准后仍能切出一句话");
    printf("     (starts=%d ends=%d, 噪声底→%.0f)\n", r.starts, r.ends, d.noise);

    printf("\n%s (失败 %d 项)\n", fails ? "有失败" : "全部通过", fails);
    return fails ? 1 : 0;
}
