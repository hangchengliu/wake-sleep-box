#include <Arduino.h>
#include <Wire.h>
#include <math.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>
#include "driver/spi_master.h"
#include "driver/i2s_std.h"
#include "esp_lcd_panel_io.h"
#include "esp_lcd_panel_vendor.h"
#include "esp_lcd_panel_ops.h"
#include "esp32-hal-rmt.h"
#include "page_bitmaps.h"
#include "voice_data.h"   // 由 tools/gen_voice.py 生成的离线中文语音词库

#define BLE_DEVICE_NAME "Korvo-刘航成&夏工"
#define SERVICE_UUID    "4fafc201-1fb5-459e-8fcc-c5c9c331914b"
#define CHAR_UUID       "beb5483e-36e1-4688-b7f5-ea07361b26a8"

// I2C Bus
#define I2C_SDA_PIN 17
#define I2C_SCL_PIN 18
#define CST816S_ADDR 0x15
#define ES8311_ADDR  0x18
#define ES7210_ADDR  0x40

// ST7789 SPI LCD
#define LCD_HOST    SPI2_HOST
#define LCD_MOSI    0
#define LCD_SCLK    1
#define LCD_DC      2
#define LCD_CS      46
#define LCD_RST     -1
#define LCD_H_RES   280
#define LCD_V_RES   240
#define LCD_X_GAP   20

// Onboard I2S Audio & PA & ADC Keys
#define I2S_MCLK_PIN 16
#define I2S_BCLK_PIN 9
#define I2S_WS_PIN   45
#define I2S_DOUT_PIN 8
#define I2S_DIN_PIN  10
#define PA_CTRL_PIN  48
#define ADC_KEY_PIN  5

// Optional external sensors
#define PIR_PIN      19
#define WS2812_PIN   20
#define WS2812_NUM   8

#define NUM_PAGES    5
#define PAGE_WAKE    0
#define PAGE_MIC     1
#define PAGE_SPK     2
#define PAGE_KEYS    3
#define PAGE_EXT     4

// =========================================================
// Wake Sleep Box state
// =========================================================
static uint8_t tca_addr = 0;
static bool night_mode = false;         // true = screen off, monitoring the room
static bool has_report = false;         // morning report available
static uint32_t night_start_ms = 0;
static uint32_t night_grace_until = 0;  // ignore mic events right after start sound
static float noise_baseline = 45.0f;
static int ev_noise = 0;
static float ev_noise_max_db = 0.0f;
static uint32_t last_noise_ev_ms = 0;
static int ev_leak = 0;
static uint32_t last_leak_ev_ms = 0;
static bool leak_high = false;
static uint32_t bright_since_ms = 0;
static uint32_t dark_since_ms = 0;
static int ev_wake = 0;
static uint32_t wake_total_ms = 0;
static uint32_t wake_active_since = 0;
static bool wake_active = false;
static uint32_t sim_wake_until = 0;
static float night_temp_min = 99.0f, night_temp_max = -99.0f;
static uint32_t temp_bad_s = 0;
static uint32_t last_temp_tick = 0;
static int wake_score = -1;
static int wake_advice = 0;             // index into wake_advice_bmp
static uint32_t night_duration_s = 0;
static void notify_ble_state();

static esp_lcd_panel_handle_t panel_handle = NULL;
static uint16_t *fb_curr = NULL;
static uint16_t *fb_next = NULL;
static uint16_t *dma_strip = NULL;

static i2s_chan_handle_t tx_handle = NULL;
static i2s_chan_handle_t rx_handle = NULL;
static bool audio_ok = false;

// Live state
static int cur_page = 0;
static float cur_db = 35.0f;
static int cur_peak_pct = 0;
static uint8_t spec_bars[16] = {4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4};

static int adc_mv = 3300;
static int active_key = 0; // 0=None, 1..6=K1..K6
static int last_key = 0;
static int speaker_vol = 80;
static bool speaker_muted = false;
static int active_sound_pad = -1;
static uint32_t sound_pad_highlight_until = 0;

// Optional external sensor state
static uint8_t bh1750_addr = 0;
static uint8_t spa06_addr = 0;
static int32_t ext_lux = -1;
static float ext_temp = 0.0f;
static float ext_pres = 0.0f;
static bool ext_spa_online = false;
static int ext_pir = 0;

// SPA06 calibration
static int16_t c0 = 0, c1 = 0;
static int32_t c00 = 0, c10 = 0;
static int16_t c01 = 0, c11 = 0, c20 = 0, c21 = 0, c30 = 0;
static uint8_t tmp_cfg_val = 0xA0;

// BLE state
static BLEServer *pServer = NULL;
static BLECharacteristic *pSensorChar = NULL;
static volatile bool ble_connected = false;
static volatile int pending_page = -1;
static volatile int pending_sound = -1;
static volatile int pending_night = 0;   // 1 = start night watch, 2 = end night -> report
static volatile int pending_sim = 0;     // 4 = simulate getting up, 5 = simulate light leak
static uint32_t last_sound_end_ms = 0;   // mic ignores our own speaker output

static inline uint16_t rgb565_be(uint8_t r, uint8_t g, uint8_t b) {
    uint16_t c = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3);
    return __builtin_bswap16(c);
}

// =========================================================
// I2C Helpers
// =========================================================
static bool i2c_write_reg(uint8_t addr, uint8_t reg, uint8_t val) {
    Wire.beginTransmission(addr);
    Wire.write(reg);
    Wire.write(val);
    return (Wire.endTransmission() == 0);
}

static bool i2c_read_regs(uint8_t addr, uint8_t reg, uint8_t *buf, uint8_t len) {
    Wire.beginTransmission(addr);
    Wire.write(reg);
    if (Wire.endTransmission(false) != 0) return false;
    if (Wire.requestFrom(addr, len) != len) return false;
    for (uint8_t i = 0; i < len; i++) buf[i] = Wire.read();
    return true;
}

static uint8_t i2c_read_reg(uint8_t addr, uint8_t reg) {
    uint8_t v = 0;
    i2c_read_regs(addr, reg, &v, 1);
    return v;
}

static void i2c_update_bits(uint8_t addr, uint8_t reg, uint8_t mask, uint8_t data) {
    uint8_t v = i2c_read_reg(addr, reg);
    v = (v & (~mask)) | (data & mask);
    i2c_write_reg(addr, reg, v);
}

static void init_io_expander() {
    Wire.begin(I2C_SDA_PIN, I2C_SCL_PIN, 400000);
    const uint8_t addrs[] = {0x38, 0x20};
    for (uint8_t addr : addrs) {
        uint8_t dir = 0xFF, out = 0x00;
        if (i2c_read_regs(addr, 0x03, &dir, 1)) {
            i2c_read_regs(addr, 0x01, &out, 1);
            // P0 = PA/Peripherals, P1 = LCD BL, P2 = LCD RST
            dir &= ~0x07;
            out |= 0x07;
            i2c_write_reg(addr, 0x01, out);
            i2c_write_reg(addr, 0x03, dir);
            if (tca_addr == 0) tca_addr = addr;
            Serial.printf("TCA9554 initialized at 0x%02X\n", addr);
        }
    }
    delay(30);
}

// Hardware backlight switch via TCA9554 P1 (bit 1). Off = truly dark screen.
static void set_backlight(bool on) {
    if (tca_addr == 0) return;
    uint8_t out = i2c_read_reg(tca_addr, 0x01);
    if (on) out |= 0x02; else out &= ~0x02;
    i2c_write_reg(tca_addr, 0x01, out);
}

// WS2812 ring: only used as a dim amber night-light when someone gets up at night.
static bool ws_ready = false;
static int ws_last_level = -1;
static void ws2812_set_all(uint8_t r, uint8_t g, uint8_t b, int count) {
    if (!ws_ready) {
        ws_ready = rmtInit(WS2812_PIN, RMT_TX_MODE, RMT_MEM_NUM_BLOCKS_4, 10000000);
        if (ws_ready) rmtSetEOT(WS2812_PIN, LOW);
    }
    if (!ws_ready) return;
    static rmt_data_t data[WS2812_NUM * 24];
    int idx = 0;
    for (int n = 0; n < WS2812_NUM; n++) {
        uint8_t grb[3] = {0, 0, 0};
        if (n < count) { grb[0] = g; grb[1] = r; grb[2] = b; }
        for (int c = 0; c < 3; c++) {
            for (int bit = 7; bit >= 0; bit--) {
                bool one = grb[c] & (1 << bit);
                data[idx].level0 = 1; data[idx].duration0 = one ? 8 : 4;
                data[idx].level1 = 0; data[idx].duration1 = one ? 4 : 8;
                idx++;
            }
        }
    }
    rmtWrite(WS2812_PIN, data, WS2812_NUM * 24, RMT_WAIT_FOR_EVER);
}

static void night_light(bool on) {
    int level = on ? 1 : 0;
    if (level == ws_last_level) return;
    ws_last_level = level;
    if (on) ws2812_set_all(40, 14, 0, 1);   // one dim amber LED
    else    ws2812_set_all(0, 0, 0, 0);
}

// =========================================================
// ES8311 DAC (0x18) + ES7210 Mic ADC (0x40) + I2S Setup
// =========================================================
static void init_es8311() {
    // Enhance I2C noise immunity
    i2c_write_reg(ES8311_ADDR, 0x44, 0x08);
    i2c_write_reg(ES8311_ADDR, 0x44, 0x08);

    i2c_write_reg(ES8311_ADDR, 0x01, 0x30);
    i2c_write_reg(ES8311_ADDR, 0x02, 0x00);
    i2c_write_reg(ES8311_ADDR, 0x03, 0x10);
    i2c_write_reg(ES8311_ADDR, 0x16, 0x24);
    i2c_write_reg(ES8311_ADDR, 0x04, 0x20);
    i2c_write_reg(ES8311_ADDR, 0x05, 0x00);
    i2c_write_reg(ES8311_ADDR, 0x0B, 0x00);
    i2c_write_reg(ES8311_ADDR, 0x0C, 0x00);
    i2c_write_reg(ES8311_ADDR, 0x10, 0x1F);
    i2c_write_reg(ES8311_ADDR, 0x11, 0x7F);
    i2c_write_reg(ES8311_ADDR, 0x00, 0x80); // Slave mode, CSM power on
    i2c_write_reg(ES8311_ADDR, 0x01, 0x3F); // Enable MCLK from pad

    // 16kHz with MCLK = 16000 * 256 = 4,096,000 Hz:
    // pre_div=1, mult=1, adc_div=1, dac_div=1, fs_mode=0, lrck=0x00ff, bclk_div=4, adc_osr=0x10, dac_osr=0x20
    i2c_write_reg(ES8311_ADDR, 0x02, 0x00);
    i2c_write_reg(ES8311_ADDR, 0x05, 0x00);
    i2c_write_reg(ES8311_ADDR, 0x03, 0x10);
    i2c_write_reg(ES8311_ADDR, 0x04, 0x20);
    i2c_write_reg(ES8311_ADDR, 0x07, 0x00);
    i2c_write_reg(ES8311_ADDR, 0x08, 0xFF);
    i2c_write_reg(ES8311_ADDR, 0x06, 0x03);

    // 16-bit Philips I2S normal format, unmute SDPIN
    i2c_write_reg(ES8311_ADDR, 0x09, 0x0C);
    i2c_write_reg(ES8311_ADDR, 0x0A, 0x0C);

    i2c_write_reg(ES8311_ADDR, 0x13, 0x10);
    i2c_write_reg(ES8311_ADDR, 0x1B, 0x0A);
    i2c_write_reg(ES8311_ADDR, 0x1C, 0x6A);

    // Start DAC
    i2c_write_reg(ES8311_ADDR, 0x17, 0xBF);
    i2c_write_reg(ES8311_ADDR, 0x0E, 0x02);
    i2c_write_reg(ES8311_ADDR, 0x12, 0x00);
    i2c_write_reg(ES8311_ADDR, 0x14, 0x1A);
    i2c_write_reg(ES8311_ADDR, 0x0D, 0x01);
    i2c_write_reg(ES8311_ADDR, 0x15, 0x40);
    i2c_write_reg(ES8311_ADDR, 0x37, 0x08);
    i2c_write_reg(ES8311_ADDR, 0x45, 0x00);
    i2c_write_reg(ES8311_ADDR, 0x44, 0x58);
    i2c_write_reg(ES8311_ADDR, 0x31, 0x00); // Unmute DAC
    i2c_write_reg(ES8311_ADDR, 0x32, 0xBF); // 0dB volume
}

static void init_es7210() {
    i2c_write_reg(ES7210_ADDR, 0x00, 0xFF);
    delay(5);
    i2c_write_reg(ES7210_ADDR, 0x00, 0x41);
    i2c_write_reg(ES7210_ADDR, 0x01, 0x3F);
    i2c_write_reg(ES7210_ADDR, 0x09, 0x30);
    i2c_write_reg(ES7210_ADDR, 0x0A, 0x30);
    i2c_write_reg(ES7210_ADDR, 0x23, 0x2A);
    i2c_write_reg(ES7210_ADDR, 0x22, 0x0A);
    i2c_write_reg(ES7210_ADDR, 0x20, 0x0A);
    i2c_write_reg(ES7210_ADDR, 0x21, 0x2A);
    i2c_update_bits(ES7210_ADDR, 0x08, 0x01, 0x00); // Slave mode
    i2c_write_reg(ES7210_ADDR, 0x40, 0x43);
    i2c_write_reg(ES7210_ADDR, 0x41, 0x70); // Mic12 bias 2.87V
    i2c_write_reg(ES7210_ADDR, 0x42, 0x70); // Mic34 bias 2.87V
    // 16kHz with 4.096MHz MCLK: adc_div=1, dll=1, doubler=1, osr=0x20, lrckh=0x01, lrckl=0x00
    i2c_write_reg(ES7210_ADDR, 0x02, 0xC1);
    i2c_write_reg(ES7210_ADDR, 0x07, 0x20);
    i2c_write_reg(ES7210_ADDR, 0x04, 0x01);
    i2c_write_reg(ES7210_ADDR, 0x05, 0x00);
    // 16-bit normal I2S (non-TDM stereo MIC1 + MIC2)
    i2c_write_reg(ES7210_ADDR, 0x11, 0x60);
    i2c_write_reg(ES7210_ADDR, 0x12, 0x00);
    // Power on MIC1 & MIC2 with 30dB gain (0x1A)
    i2c_write_reg(ES7210_ADDR, 0x47, 0x08);
    i2c_write_reg(ES7210_ADDR, 0x48, 0x08);
    i2c_write_reg(ES7210_ADDR, 0x49, 0x08);
    i2c_write_reg(ES7210_ADDR, 0x4A, 0x08);
    i2c_write_reg(ES7210_ADDR, 0x06, 0x00);
    i2c_write_reg(ES7210_ADDR, 0x4B, 0x00);
    i2c_write_reg(ES7210_ADDR, 0x4C, 0x00);
    i2c_write_reg(ES7210_ADDR, 0x43, 0x1B); // MIC1 enable + 33dB gain
    i2c_write_reg(ES7210_ADDR, 0x44, 0x1B); // MIC2 enable + 33dB gain
    i2c_write_reg(ES7210_ADDR, 0x45, 0x1B);
    i2c_write_reg(ES7210_ADDR, 0x46, 0x1B);
    i2c_write_reg(ES7210_ADDR, 0x01, 0x00); // Clocks ON
}

static void init_audio() {
    pinMode(PA_CTRL_PIN, OUTPUT);
    digitalWrite(PA_CTRL_PIN, HIGH);

    i2s_chan_config_t chan_cfg = I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_0, I2S_ROLE_MASTER);
    chan_cfg.dma_desc_num = 8;
    chan_cfg.dma_frame_num = 256;
    chan_cfg.auto_clear = true;
    if (i2s_new_channel(&chan_cfg, &tx_handle, &rx_handle) != ESP_OK) {
        Serial.println("Failed to create I2S duplex channels");
        return;
    }

    i2s_std_config_t std_cfg = {
        .clk_cfg = I2S_STD_CLK_DEFAULT_CONFIG(16000),
        .slot_cfg = I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_16BIT, I2S_SLOT_MODE_STEREO),
        .gpio_cfg = {
            .mclk = (gpio_num_t)I2S_MCLK_PIN,
            .bclk = (gpio_num_t)I2S_BCLK_PIN,
            .ws   = (gpio_num_t)I2S_WS_PIN,
            .dout = (gpio_num_t)I2S_DOUT_PIN,
            .din  = (gpio_num_t)I2S_DIN_PIN,
            .invert_flags = {false, false, false}
        }
    };
    std_cfg.clk_cfg.mclk_multiple = I2S_MCLK_MULTIPLE_256;

    i2s_channel_init_std_mode(tx_handle, &std_cfg);
    i2s_channel_init_std_mode(rx_handle, &std_cfg);
    i2s_channel_enable(tx_handle);
    i2s_channel_enable(rx_handle);

    init_es8311();
    init_es7210();
    audio_ok = true;
    Serial.println("Onboard ES8311 + ES7210 + I2S initialized!");
}

static void play_tone_burst(float freq1, float freq2, int duration_ms, float amp = 0.35f) {
    if (!audio_ok || !tx_handle || speaker_muted) return;
    const int sr = 16000;
    int total_samples = (sr * duration_ms) / 1000;
    int16_t buf[256 * 2];
    int written_samples = 0;
    while (written_samples < total_samples) {
        int chunk = min(256, total_samples - written_samples);
        for (int i = 0; i < chunk; i++) {
            int idx = written_samples + i;
            float env = 1.0f;
            if (idx < 160) env = idx / 160.0f;
            else if (total_samples - idx < 400) env = (total_samples - idx) / 400.0f;
            float t = (float)idx / (float)sr;
            float f = freq1 + (freq2 - freq1) * ((float)idx / (float)total_samples);
            float wave = sinf(2.0f * (float)M_PI * f * t) + 0.25f * sinf(4.0f * (float)M_PI * f * t);
            int16_t s = (int16_t)(wave * 14000.0f * amp * env * (speaker_vol / 100.0f));
            buf[i * 2] = s;
            buf[i * 2 + 1] = s;
        }
        size_t bytes_written = 0;
        i2s_channel_write(tx_handle, buf, chunk * 4, &bytes_written, 50);
        written_samples += chunk;
    }
    last_sound_end_ms = millis();
}

// =========================================================
// 离线中文语音与板载助眠白噪音：词序列与粉红噪声写 I2S（不阻塞主循环）
// =========================================================
#define VOICE_MAX_WORDS 40
static uint8_t voice_queue[VOICE_MAX_WORDS];
static volatile int voice_queue_len = 0;
static volatile bool voice_playing = false;
static volatile bool voice_abort = false;
static portMUX_TYPE voice_mux = portMUX_INITIALIZER_UNLOCKED;
static TaskHandle_t voice_task = NULL;

static volatile bool white_noise_active = false;
static uint32_t noise_seed = 1234567;
static int32_t noise_b0 = 0, noise_b1 = 0, noise_b2 = 0;

static void voice_push(uint8_t *seq, int &n, int w) {
    if (n < VOICE_MAX_WORDS) seq[n++] = (uint8_t)w;
}

// 0..100 的整数 -> 词序列。二用"两"仅在"两百"等场景才需要，这里 0-100 用"二"。
static void voice_push_number(uint8_t *seq, int &n, int v) {
    if (v < 0) v = 0;
    if (v >= 100) { voice_push(seq, n, VW_HUNDRED); return; }
    if (v < 10)   { voice_push(seq, n, VW_D0 + v); return; }
    int tens = v / 10, ones = v % 10;
    if (tens > 1) voice_push(seq, n, VW_D0 + tens);
    voice_push(seq, n, VW_TEN);
    if (ones) voice_push(seq, n, VW_D0 + ones);
}

// 次数：1 位用数字；>=10 同样走 push_number。2 次读"二"，不读"两"，与文本播报一致。
static void voice_build_report(uint8_t *seq, int &n) {
    n = 0;
    voice_push(seq, n, VW_GOOD_MORNING);
    voice_push(seq, n, VW_LAST_NIGHT_SCORE);
    voice_push_number(seq, n, wake_score);
    voice_push(seq, n, VW_POINTS);

    if (ev_noise > 0) {
        voice_push(seq, n, VW_NOISE_PRE);
        voice_push_number(seq, n, ev_noise);
        voice_push(seq, n, VW_NOISE_POST);
        voice_push(seq, n, VW_PEAK);
        voice_push_number(seq, n, (int)(ev_noise_max_db + 0.5f));
        voice_push(seq, n, VW_DB);
    } else {
        voice_push(seq, n, VW_NO_NOISE);
    }
    if (ev_leak > 0) {
        voice_push(seq, n, VW_LEAK_PRE);
        voice_push_number(seq, n, ev_leak);
        voice_push(seq, n, VW_TIMES);
    } else {
        voice_push(seq, n, VW_NO_LEAK);
    }
    if (ev_wake > 0) {
        voice_push(seq, n, VW_UP_PRE);
        voice_push_number(seq, n, ev_wake);
        voice_push(seq, n, VW_TIMES);
    } else {
        voice_push(seq, n, VW_NO_UP);
    }
    if (temp_bad_s > 0) voice_push(seq, n, VW_TEMP_BAD);

    voice_push(seq, n, VW_ADVICE_PRE);
    static const uint8_t adv_words[6] = {VW_ADV_GOOD, VW_ADV_GOOD, VW_ADV_NOISE, VW_ADV_LEAK, VW_ADV_UP, VW_ADV_TEMP};
    voice_push(seq, n, adv_words[(wake_advice >= 0 && wake_advice <= 5) ? wake_advice : 1]);
}

static void voice_task_fn(void *arg) {
    int16_t buf[256 * 2];
    for (;;) {
        TickType_t wait_ticks = white_noise_active ? 0 : portMAX_DELAY;
        uint32_t notified = ulTaskNotifyTake(pdTRUE, wait_ticks);

        if (notified) {
            uint8_t local[VOICE_MAX_WORDS];
            int local_n;
            portENTER_CRITICAL(&voice_mux);
            local_n = voice_queue_len;
            memcpy(local, voice_queue, sizeof(local));
            portEXIT_CRITICAL(&voice_mux);

            voice_playing = true;
            for (int wi = 0; wi < local_n && !voice_abort; wi++) {
                int w = local[wi];
                if (w < 0 || w >= VW_COUNT) continue;
                uint32_t off = voice_off[w], len = voice_len[w], done = 0;
                while (done < len && !voice_abort) {
                    int chunk = (int)min((uint32_t)256, len - done);
                    for (int i = 0; i < chunk; i++) {
                        int16_t s = (int16_t)pgm_read_word(&voice_pcm[off + done + i]);
                        s = (int16_t)((int32_t)s * speaker_vol / 100);
                        buf[i * 2] = s;
                        buf[i * 2 + 1] = s;
                    }
                    size_t bw = 0;
                    i2s_channel_write(tx_handle, buf, chunk * 4, &bw, 100);
                    done += chunk;
                    last_sound_end_ms = millis();              // 播放期间麦克风持续忽略自身声音
                }
                // 词间短停顿：60ms = 960 帧静音。buf 一次最多 256 帧，所以分块写。
                memset(buf, 0, sizeof(buf));
                for (int gap = 960; gap > 0 && !voice_abort; gap -= 256) {
                    size_t gw = 0;
                    i2s_channel_write(tx_handle, buf, min(gap, 256) * 4, &gw, 100);
                }
                last_sound_end_ms = millis();
            }
            voice_abort = false;
            voice_playing = false;
        } else if (white_noise_active && !speaker_muted && audio_ok && tx_handle) {
            // 板载数学算法实时合成柔和粉红噪声 (助眠雨声)，直接推送到 3W 腔体扬声器
            for (int i = 0; i < 256; i++) {
                noise_seed = noise_seed * 196314165 + 907633515;
                int32_t white = (int32_t)(noise_seed >> 16);
                noise_b0 = (noise_b0 * 997 + white * 5) / 1000;
                noise_b1 = (noise_b1 * 985 + white * 11) / 1000;
                noise_b2 = (noise_b2 * 950 + white * 30) / 1000;
                int32_t pink = (noise_b0 + noise_b1 + noise_b2 + white * 12);
                int32_t sample = (pink * (int32_t)speaker_vol) / 650;
                if (sample > 28000) sample = 28000;
                if (sample < -28000) sample = -28000;
                buf[i * 2] = (int16_t)sample;
                buf[i * 2 + 1] = (int16_t)sample;
            }
            size_t bw = 0;
            i2s_channel_write(tx_handle, buf, 256 * 4, &bw, 50);
            last_sound_end_ms = millis();
        } else {
            vTaskDelay(pdMS_TO_TICKS(15));
        }
    }
}

static void voice_start_task() {
    if (voice_task) return;
    // 栈 4KB：buf 在栈上 1KB + local 40B，够用。优先级 5 高于 loop 任务(1)，保证 I2S 喂数实时不断流。
    xTaskCreatePinnedToCore(voice_task_fn, "voice", 4096, NULL, 5, &voice_task, 0);
}

// 请求念一段词序列。正在念时先打断旧的，再播新的。
static void voice_say(const uint8_t *seq, int n) {
    if (!audio_ok || speaker_muted || !voice_task || n <= 0) return;
    if (n > VOICE_MAX_WORDS) n = VOICE_MAX_WORDS;
    if (voice_playing) {
        voice_abort = true;
        for (int i = 0; i < 50 && voice_playing; i++) delay(10);   // 最多等 500ms 让旧任务退出
    }
    portENTER_CRITICAL(&voice_mux);
    memcpy(voice_queue, seq, n);
    voice_queue_len = n;
    portEXIT_CRITICAL(&voice_mux);
    xTaskNotifyGive(voice_task);
}

static void voice_say_report() {
    uint8_t seq[VOICE_MAX_WORDS];
    int n = 0;
    voice_build_report(seq, n);
    voice_say(seq, n);
}

static void voice_say_no_report() {
    const uint8_t seq[] = {VW_NO_REPORT};
    voice_say(seq, 1);
}

static void play_sound_effect(int effect_id) {
    if (!audio_ok || speaker_muted) return;
    // 语音播报正在进行时，跳过短音效和按键提示音，避免多任务并发写入 I2S 造成爆音卡顿
    if (voice_playing && effect_id != 7 && effect_id != 8) return;
    switch (effect_id) {
        case 0: // Page swipe tick
            play_tone_burst(880.0f, 1320.0f, 35, 0.22f);
            break;
        case 1: // 欢迎和弦 (C5 - E5 - G5 - C6)
            play_tone_burst(523.25f, 523.25f, 90, 0.40f);
            play_tone_burst(659.25f, 659.25f, 90, 0.40f);
            play_tone_burst(783.99f, 783.99f, 90, 0.40f);
            play_tone_burst(1046.50f, 1046.50f, 180, 0.45f);
            break;
        case 2: // 叮咚门铃 (E5 -> C5)
            play_tone_burst(659.25f, 659.25f, 160, 0.45f);
            play_tone_burst(523.25f, 523.25f, 260, 0.45f);
            break;
        case 3: // 警报蜂鸣 (Siren sweep)
            play_tone_burst(600.0f, 1400.0f, 160, 0.45f);
            play_tone_burst(1400.0f, 600.0f, 160, 0.45f);
            break;
        case 4: { // 音阶连奏 (Do Re Mi Fa Sol La Si Do)
            const float notes[] = {523.25f, 587.33f, 659.25f, 698.46f, 783.99f, 880.0f, 987.77f, 1046.50f};
            for (int i = 0; i < 8; i++) play_tone_burst(notes[i], notes[i], 65, 0.38f);
            break;
        }
        case 5: { // 入睡: soft descending G4-E4-C4
            const float notes[] = {392.0f, 329.63f, 261.63f};
            for (int i = 0; i < 3; i++) play_tone_burst(notes[i], notes[i], 220, 0.22f);
            break;
        }
        case 6: { // 晨起日出: ascending C5-E5-G5-C6-E6
            const float notes[] = {523.25f, 659.25f, 783.99f, 1046.50f, 1318.51f};
            for (int i = 0; i < 5; i++) play_tone_burst(notes[i], notes[i], 140, 0.40f);
            break;
        }
        case 7: // 日出和弦(同步播完) + 离线中文语音晨报(后台任务)。两者不会同时写 I2S。
            play_sound_effect(6);
            if (has_report) voice_say_report(); else voice_say_no_report();
            break;
        case 8: { // 晚安语音（开始守夜时）
            const uint8_t seq[] = {VW_GOOD_NIGHT};
            voice_say(seq, 1);
            break;
        }
        default:
            if (effect_id >= 10 && effect_id <= 15) {
                const float k_notes[] = {523.25f, 587.33f, 659.25f, 698.46f, 783.99f, 880.0f};
                float f = k_notes[effect_id - 10];
                play_tone_burst(f, f, 70, 0.35f);
            }
            break;
    }
}

static void poll_microphone() {
    if (!audio_ok || !rx_handle) return;
    int16_t pcm[256 * 2];
    size_t bytes_read = 0;
    if (i2s_channel_read(rx_handle, pcm, sizeof(pcm), &bytes_read, 5) == ESP_OK && bytes_read >= 64) {
        int frames = bytes_read / 4;
        // Remove DC offset first
        int64_t sum_l = 0;
        for (int i = 0; i < frames; i++) sum_l += pcm[i * 2];
        int32_t mean_l = (int32_t)(sum_l / frames);

        double sum_sq = 0;
        int32_t max_abs = 0;
        int seg_len = max(1, frames / 16);

        for (int b = 0; b < 16; b++) {
            int64_t seg_sum = 0;
            for (int j = 0; j < seg_len; j++) {
                int idx = b * seg_len + j;
                if (idx < frames) {
                    int32_t v = abs((int32_t)pcm[idx * 2] - mean_l);
                    seg_sum += v;
                    sum_sq += (double)v * (double)v;
                    if (v > max_abs) max_abs = v;
                }
            }
            int32_t avg_v = (int32_t)(seg_sum / seg_len);
            // Map avg_v (0..4000) to bar height (4..88)
            int target_h = 4 + (int)(sqrtf((float)avg_v) * 1.45f);
            if (target_h > 88) target_h = 88;
            // Smooth decay/attack
            if (target_h > spec_bars[b]) spec_bars[b] = (uint8_t)((spec_bars[b] + target_h * 2) / 3);
            else spec_bars[b] = (uint8_t)((spec_bars[b] * 2 + target_h) / 3);
        }

        double rms = sqrt(sum_sq / frames);
        float db = 32.0f;
        if (rms > 1.0) {
            db = 28.0f + 16.5f * log10f((float)rms);
            if (db < 32.0f) db = 32.0f;
            if (db > 96.0f) db = 96.0f;
        }
        cur_db = cur_db * 0.65f + db * 0.35f;
        cur_peak_pct = min(100, (int)((max_abs * 100) / 12000));
    }
}

// =========================================================
// Onboard 6-Key ADC Matrix (GPIO 5)
// =========================================================
static void poll_adc_keys() {
    int mv = analogReadMilliVolts(ADC_KEY_PIN);
    adc_mv = (adc_mv * 2 + mv) / 3;

    // Thresholds from KSDIY Korvo BSP: {380, 820, 1180, 1570, 1980, 2410} mV
    int detected = 0;
    if (mv >= 150 && mv < 600)        detected = 1; // K1 VOL+
    else if (mv >= 600 && mv < 1000)  detected = 2; // K2 VOL-
    else if (mv >= 1000 && mv < 1375) detected = 3; // K3 SET
    else if (mv >= 1375 && mv < 1775) detected = 4; // K4 PLAY
    else if (mv >= 1775 && mv < 2195) detected = 5; // K5 MUTE
    else if (mv >= 2195 && mv < 2680) detected = 6; // K6 REC

    active_key = detected;
    if (active_key != 0 && last_key == 0) {
        // Key just pressed!
        if (night_mode) {
            // Screen is off: keys act as silent demo triggers
            if (active_key == 3 || active_key == 6) pending_night = 2;   // end night -> report
            else if (active_key == 4) pending_sim = 4;                  // simulate getting up
            else if (active_key == 5) pending_sim = 5;                  // simulate light leak
        } else {
            play_sound_effect(9 + active_key);
            if (active_key == 1) {
                pending_page = (cur_page + NUM_PAGES - 1) % NUM_PAGES;
            } else if (active_key == 2) {
                pending_page = (cur_page + 1) % NUM_PAGES;
            } else if (active_key == 3) {
                pending_night = 1;                                      // start night watch
            } else if (active_key == 4) {
                white_noise_active = !white_noise_active;               // K4: 切换板载助眠白噪音
                if (white_noise_active && voice_task) xTaskNotifyGive(voice_task);
                notify_ble_state();
            } else if (active_key == 5) {
                pending_sound = 2;                                      // K5: 叮咚门铃音效
            } else if (active_key == 6) {
                pending_page = PAGE_WAKE;                               // K6: 早安晨报复盘
                pending_sound = 7;
            }
        }
    }
    last_key = active_key;
}

// =========================================================
// Optional External Sensors Poll (Auto-detect online/offline)
// =========================================================
static void poll_external_sensors() {
    ext_pir = (digitalRead(PIR_PIN) == HIGH) ? 1 : 0;

    // Check BH1750 (0x23)
    Wire.beginTransmission(0x23);
    if (Wire.endTransmission() == 0) {
        if (bh1750_addr == 0) {
            bh1750_addr = 0x23;
            Wire.beginTransmission(0x23); Wire.write(0x01); Wire.endTransmission();
            Wire.beginTransmission(0x23); Wire.write(0x10); Wire.endTransmission();
        } else if (Wire.requestFrom((uint8_t)0x23, (uint8_t)2) == 2) {
            uint16_t raw = ((uint16_t)Wire.read() << 8) | Wire.read();
            ext_lux = (int32_t)((raw * 10 + 6) / 12);
        }
    } else {
        bh1750_addr = 0;
        ext_lux = -1;
    }

    // Check SPA06 (0x76)
    Wire.beginTransmission(0x76);
    if (Wire.endTransmission() == 0) {
        if (spa06_addr == 0) {
            uint8_t coef[18] = {0};
            if (i2c_read_regs(0x76, 0x10, coef, 18)) {
                spa06_addr = 0x76;
                c0 = ((int16_t)coef[0] << 4) | (coef[1] >> 4); if (c0 & 0x0800) c0 |= 0xF000;
                c1 = ((int16_t)(coef[1] & 0x0F) << 8) | coef[2]; if (c1 & 0x0800) c1 |= 0xF000;
                c00 = ((int32_t)coef[3] << 12) | ((int32_t)coef[4] << 4) | (coef[5] >> 4); if (c00 & 0x080000) c00 |= 0xFFF00000;
                c10 = ((int32_t)(coef[5] & 0x0F) << 16) | ((int32_t)coef[6] << 8) | coef[7]; if (c10 & 0x080000) c10 |= 0xFFF00000;
                c01 = ((int16_t)coef[8] << 8) | coef[9];
                c11 = ((int16_t)coef[10] << 8) | coef[11];
                c20 = ((int16_t)coef[12] << 8) | coef[13];
                c21 = ((int16_t)coef[14] << 8) | coef[15];
                c30 = ((int16_t)coef[16] << 8) | coef[17];
                uint8_t srce = 0x80; i2c_read_regs(0x76, 0x28, &srce, 1);
                tmp_cfg_val = (srce & 0x80) | 0x20;
                i2c_write_reg(0x76, 0x06, 0x23);
                i2c_write_reg(0x76, 0x07, tmp_cfg_val);
                i2c_write_reg(0x76, 0x08, 0x07);
            }
        } else {
            uint8_t raw[6] = {0};
            if (i2c_read_regs(0x76, 0x00, raw, 6)) {
                int32_t p_raw = ((int32_t)raw[0] << 16) | ((int32_t)raw[1] << 8) | raw[2];
                if (p_raw & 0x800000) p_raw |= 0xFF000000;
                int32_t t_raw = ((int32_t)raw[3] << 16) | ((int32_t)raw[4] << 8) | raw[5];
                if (t_raw & 0x800000) t_raw |= 0xFF000000;
                if (t_raw != 0) {
                    float t_sc = (float)t_raw / 524288.0f;
                    float p_sc = (float)p_raw / 7864320.0f;
                    ext_temp = (float)c0 * 0.5f + (float)c1 * t_sc;
                    float pres_pa = (float)c00 + p_sc * ((float)c10 + p_sc * ((float)c20 + p_sc * (float)c30))
                                    + t_sc * (float)c01 + t_sc * p_sc * ((float)c11 + p_sc * (float)c21);
                    ext_pres = pres_pa / 100.0f;
                    ext_spa_online = true;
                }
            }
        }
    } else {
        spa06_addr = 0;
        ext_spa_online = false;
    }
}

// =========================================================
// Wake Sleep Box engine: night watch -> events -> score -> one advice
// =========================================================
static uint32_t wake_last_motion_ms = 0;
static bool auto_armed = true;   // needs a bright room before another auto night can start
static uint32_t morning_bright_since = 0;

static void render_page_to_fb(uint16_t *fb, int page_idx);
static void flush_fb_to_lcd(const uint16_t *fb);
static void fb_fill_black_and_flush();

static void start_night(uint32_t now) {
    ev_noise = 0; ev_noise_max_db = 0.0f; last_noise_ev_ms = 0;
    ev_leak = 0; last_leak_ev_ms = 0; leak_high = false;
    ev_wake = 0; wake_total_ms = 0; wake_active = false; sim_wake_until = 0;
    night_temp_min = 99.0f; night_temp_max = -99.0f; temp_bad_s = 0; last_temp_tick = now;
    morning_bright_since = 0;
    has_report = false;

    play_sound_effect(5);                 // soft "good night" tones while screen is still on
    play_sound_effect(8);                 // "晚安，开始守夜" 由板载喇叭说出
    fb_fill_black_and_flush();
    set_backlight(false);                 // hardware backlight off: zero light pollution
    night_mode = true;
    auto_armed = false;
    night_start_ms = millis();
    night_grace_until = night_start_ms + 1500;
    noise_baseline = cur_db;
    Serial.println("[Wake] Night watch started");
}

static void end_night(uint32_t now) {
    if (wake_active) {
        wake_total_ms += now - wake_active_since;
        wake_active = false;
    }
    night_light(false);
    white_noise_active = false; // 晨起唤醒自动关闭助眠白噪音
    night_duration_s = (now - night_start_ms) / 1000;

    int p_noise = min(30, ev_noise * 8);
    int p_leak  = min(25, ev_leak * 10);
    int p_wake  = min(24, ev_wake * 8 + (int)(wake_total_ms / 60000));
    int p_temp  = (temp_bad_s > 0) ? min(20, 5 + (int)(temp_bad_s / 30)) : 0;
    wake_score = max(0, 100 - p_noise - p_leak - p_wake - p_temp);

    // Advice = biggest penalty
    int worst = 0, adv = 1;
    if (p_noise > worst) { worst = p_noise; adv = 2; }
    if (p_leak  > worst) { worst = p_leak;  adv = 3; }
    if (p_wake  > worst) { worst = p_wake;  adv = 4; }
    if (p_temp  > worst) { worst = p_temp;  adv = 5; }
    wake_advice = adv;
    has_report = true;
    night_mode = false;

    cur_page = PAGE_WAKE;
    set_backlight(true);
    render_page_to_fb(fb_curr, cur_page);
    flush_fb_to_lcd(fb_curr);
    play_sound_effect(7);                 // sunrise chord, then spoken report on the board speaker
    Serial.printf("[Wake] Report: score=%d noise=%d leak=%d wake=%d tempBad=%lus advice=%d\n",
                  wake_score, ev_noise, ev_leak, ev_wake, (unsigned long)temp_bad_s, wake_advice);
}

static void update_wake_engine(uint32_t now) {
    // ---- Auto start: room dark (<2 lx) for 10 s, only when BH1750 is connected ----
    if (!night_mode) {
        if (ext_lux >= 0) {
            if (ext_lux >= 20) auto_armed = true;
            if (ext_lux < 2) {
                if (dark_since_ms == 0) dark_since_ms = now;
                if (auto_armed && now - dark_since_ms >= 10000) pending_night = 1;
            } else {
                dark_since_ms = 0;
            }
        } else {
            dark_since_ms = 0;
        }
        return;
    }

    // ---- 1. Noise events (mic envelope only, never recorded) ----
    bool own_sound = (now - last_sound_end_ms < 900);
    if (!own_sound && now <= night_grace_until) {
        // Grace window: converge quickly on the room's real noise floor
        // (the start-of-night tones may have leaked into the mic).
        noise_baseline = noise_baseline * 0.9f + cur_db * 0.1f;
    }
    if (!own_sound && now > night_grace_until) {
        float thresh = max(noise_baseline + 12.0f, 50.0f);
        if (cur_db > thresh && now - last_noise_ev_ms > 3000) {
            ev_noise++;
            last_noise_ev_ms = now;
            Serial.printf("[Wake] Noise event %.1f dB\n", cur_db);
        }
        if (cur_db > thresh && cur_db > ev_noise_max_db) ev_noise_max_db = cur_db;
        if (cur_db < noise_baseline + 5.0f) noise_baseline = noise_baseline * 0.995f + cur_db * 0.005f;
    }

    // ---- 2. Light leak (BH1750 > 5 lx) / morning (>= 50 lx for 8 s) ----
    if (ext_lux >= 0) {
        bool high = ext_lux > 5;
        if (high && !leak_high && now - last_leak_ev_ms > 3000) {
            ev_leak++;
            last_leak_ev_ms = now;
            Serial.printf("[Wake] Light leak %ld lx\n", (long)ext_lux);
        }
        leak_high = high;
        if (ext_lux >= 50) {
            if (morning_bright_since == 0) morning_bright_since = now;
            if (now - morning_bright_since >= 8000) pending_night = 2;
        } else {
            morning_bright_since = 0;
        }
    }

    // ---- 3. Getting up (PIR or K4 simulation) + dim amber night-light ----
    bool motion = (ext_pir == 1) || (now < sim_wake_until);
    if (motion) wake_last_motion_ms = now;
    if (motion && !wake_active) {
        wake_active = true;
        wake_active_since = now;
        ev_wake++;
        Serial.println("[Wake] Getting up detected");
    } else if (wake_active && now - wake_last_motion_ms > 15000) {
        wake_total_ms += now - wake_active_since;
        wake_active = false;
    }
    night_light(wake_active);

    // ---- 4. Temperature comfort (SPA06), 1 s ticks ----
    if (now - last_temp_tick >= 1000) {
        last_temp_tick = now;
        if (ext_spa_online) {
            if (ext_temp < night_temp_min) night_temp_min = ext_temp;
            if (ext_temp > night_temp_max) night_temp_max = ext_temp;
            if (ext_temp < 16.0f || ext_temp > 25.0f) temp_bad_s++;
        }
    }
}

// =========================================================
// Framebuffer Drawing Primitives (280 x 240)
// =========================================================
static void fb_fill_rect(uint16_t *fb, int x0, int y0, int w, int h, uint8_t r, uint8_t g, uint8_t b) {
    uint16_t col = rgb565_be(r, g, b);
    for (int y = max(0, y0); y < min(LCD_V_RES, y0 + h); y++) {
        uint16_t *row = &fb[y * LCD_H_RES];
        for (int x = max(0, x0); x < min(LCD_H_RES, x0 + w); x++) {
            row[x] = col;
        }
    }
}

static void fb_draw_round_box(uint16_t *fb, int x0, int y0, int w, int h,
                              uint8_t fill_r, uint8_t fill_g, uint8_t fill_b,
                              uint8_t bdr_r, uint8_t bdr_g, uint8_t bdr_b, int border_px = 2) {
    for (int dy = 0; dy < h; dy++) {
        int y = y0 + dy;
        if (y < 0 || y >= LCD_V_RES) continue;
        for (int dx = 0; dx < w; dx++) {
            int x = x0 + dx;
            if (x < 0 || x >= LCD_H_RES) continue;
            int cx = (dx < 6) ? (5 - dx) : ((dx >= w - 6) ? (dx - (w - 6)) : 0);
            int cy = (dy < 6) ? (5 - dy) : ((dy >= h - 6) ? (dy - (h - 6)) : 0);
            int d2 = cx * cx + cy * cy;
            if (d2 <= 28) {
                bool is_bdr = (dx < border_px || dx >= w - border_px || dy < border_px || dy >= h - border_px || d2 >= 15);
                if (is_bdr) fb[y * LCD_H_RES + x] = rgb565_be(bdr_r, bdr_g, bdr_b);
                else        fb[y * LCD_H_RES + x] = rgb565_be(fill_r, fill_g, fill_b);
            }
        }
    }
}

static void fb_blend_bitmap(uint16_t *fb, int x0, int y0, int w, int h, const uint8_t *bmp,
                            uint8_t fg_r, uint8_t fg_g, uint8_t fg_b,
                            uint8_t bg_r, uint8_t bg_g, uint8_t bg_b) {
    for (int dy = 0; dy < h; dy++) {
        int y = y0 + dy;
        if (y < 0 || y >= LCD_V_RES) continue;
        for (int dx = 0; dx < w; dx++) {
            int x = x0 + dx;
            if (x < 0 || x >= LCD_H_RES) continue;
            uint8_t a = bmp[dy * w + dx];
            if (a > 4) {
                uint8_t r = (uint8_t)((bg_r * (255 - a) + fg_r * a) / 255);
                uint8_t g = (uint8_t)((bg_g * (255 - a) + fg_g * a) / 255);
                uint8_t b = (uint8_t)((bg_b * (255 - a) + fg_b * a) / 255);
                fb[y * LCD_H_RES + x] = rgb565_be(r, g, b);
            }
        }
    }
}

static int glyph_index_for_char(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    switch (c) {
        case '.': return 10;
        case '-': return 11;
        case ' ': return 12;
        case 'd': return 13;
        case 'B': return 14;
        case 'm': return 15;
        case 'V': return 16;
        case 'l': return 17;
        case 'x': return 18;
        case 'C': return 19;
        case 'h': return 20;
        case 'P': return 21;
        case 'a': return 22;
        case '%': return 23;
        default:  return 12;
    }
}

static void fb_draw_ascii(uint16_t *fb, int x0, int y0, const char *str,
                          uint8_t fg_r, uint8_t fg_g, uint8_t fg_b,
                          uint8_t bg_r, uint8_t bg_g, uint8_t bg_b) {
    int cx = x0;
    for (int i = 0; str[i] != '\0'; i++) {
        int gidx = glyph_index_for_char(str[i]);
        fb_blend_bitmap(fb, cx, y0, 12, 24, glyph_bmp[gidx], fg_r, fg_g, fg_b, bg_r, bg_g, bg_b);
        cx += 12;
    }
}

// =========================================================
// Render Complete Page into `fb`
// =========================================================
static void render_page_to_fb(uint16_t *fb, int page_idx) {
    const uint8_t bg_r = 9, bg_g = 15, bg_b = 32;
    fb_fill_rect(fb, 0, 0, LCD_H_RES, LCD_V_RES, bg_r, bg_g, bg_b);

    // 1. Top Header Bar ("刘航成 & 夏工")
    fb_blend_bitmap(fb, 0, 3, 280, 28, header_bmp, 255, 255, 255, bg_r, bg_g, bg_b);
    fb_fill_rect(fb, 12, 33, LCD_H_RES - 24, 1, 38, 130, 195);

    // BLE connection dot in top-right corner
    uint8_t dot_r = ble_connected ? 52  : 100;
    uint8_t dot_g = ble_connected ? 211 : 116;
    uint8_t dot_b = ble_connected ? 153 : 139;
    fb_draw_round_box(fb, 254, 10, 14, 14, dot_r, dot_g, dot_b, 255, 255, 255, 1);

    // 2. Page Content Area (y = 38 .. 202)
    if (page_idx == PAGE_WAKE) {
        // PAGE 0: Wake Sleep Box - score + 3 event counters, one advice, two buttons
        const uint8_t cell_r = 18, cell_g = 28, cell_b = 52;
        for (int i = 0; i < 4; i++) {
            int cx = 12 + i * 65;
            uint8_t br = 56, bg = 85, bb = 130;
            if (i == 0 && has_report) {
                if (wake_score >= 85)      { br = 52;  bg = 211; bb = 153; }
                else if (wake_score >= 65) { br = 251; bg = 191; bb = 36;  }
                else                       { br = 248; bg = 113; bb = 113; }
            }
            fb_draw_round_box(fb, cx, 40, 61, 60, cell_r, cell_g, cell_b, br, bg, bb, 2);
            fb_blend_bitmap(fb, cx + 10, 43, 40, 22, wake_metric_bmp[i], 148, 163, 184, cell_r, cell_g, cell_b);
            char v[8];
            if (!has_report) snprintf(v, sizeof(v), "--");
            else if (i == 0) snprintf(v, sizeof(v), "%d", wake_score);
            else if (i == 1) snprintf(v, sizeof(v), "%d", ev_noise);
            else if (i == 2) snprintf(v, sizeof(v), "%d", ev_leak);
            else             snprintf(v, sizeof(v), "%d", ev_wake);
            int tw = strlen(v) * 12;
            uint8_t vr = (i == 0 && has_report) ? br : 240;
            uint8_t vg = (i == 0 && has_report) ? bg : 248;
            uint8_t vb = (i == 0 && has_report) ? bb : 255;
            fb_draw_ascii(fb, cx + (61 - tw) / 2, 70, v, vr, vg, vb, cell_r, cell_g, cell_b);
        }

        // One-sentence advice
        fb_draw_round_box(fb, 12, 106, 256, 32, 14, 22, 42, 45, 70, 115, 1);
        int adv = has_report ? wake_advice : 0;
        fb_blend_bitmap(fb, 16, 111, 248, 22, wake_advice_bmp[adv], 226, 232, 240, 14, 22, 42);

        // Buttons: [开始熄屏守夜] [查看晨间报告]
        fb_draw_round_box(fb, 12, 146, 124, 50, 30, 41, 99, 129, 140, 248, 2);
        fb_blend_bitmap(fb, 18, 159, 112, 24, wake_btn_bmp[0], 255, 255, 255, 30, 41, 99);
        uint8_t r2 = has_report ? 180 : 40, g2 = has_report ? 83 : 50, b2 = has_report ? 9 : 70;
        fb_draw_round_box(fb, 144, 146, 124, 50, r2, g2, b2, 251, 191, 36, 2);
        fb_blend_bitmap(fb, 150, 159, 112, 24, wake_btn_bmp[1], 255, 255, 255, r2, g2, b2);
    } else if (page_idx == PAGE_MIC) {
        // PAGE 0: Onboard Dual-Mic Sound & 16-Bar Live Spectrum
        fb_draw_round_box(fb, 12, 40, 256, 44, 18, 28, 52, 34, 211, 238, 2);
        char db_str[16];
        snprintf(db_str, sizeof(db_str), "%d dB", (int)roundf(cur_db));
        fb_draw_ascii(fb, 28, 50, db_str, 34, 211, 238, 18, 28, 52);

        char pct_str[16];
        snprintf(pct_str, sizeof(pct_str), "%d%%", cur_peak_pct);
        fb_draw_ascii(fb, 196, 50, pct_str, 251, 191, 36, 18, 28, 52);

        // Live level bar inside top box
        int bar_w = (int)((cur_db - 30.0f) * 1.4f);
        if (bar_w < 4) bar_w = 4;
        if (bar_w > 82) bar_w = 82;
        fb_fill_rect(fb, 104, 56, 84, 12, 10, 16, 30);
        fb_fill_rect(fb, 105, 57, bar_w, 10, (cur_db > 72) ? 248 : 52, (cur_db > 72) ? 113 : 211, 153);

        // 16-Bar Spectrum Analyzer Box (y = 88 .. 182)
        fb_draw_round_box(fb, 12, 88, 256, 92, 14, 22, 42, 45, 70, 115, 1);
        for (int i = 0; i < 16; i++) {
            int bh = spec_bars[i];
            if (bh > 80) bh = 80;
            int bx = 20 + i * 15;
            int by = 175 - bh;
            uint8_t br = (uint8_t)min(255, 34 + i * 13);
            uint8_t bg = (uint8_t)max(60, 220 - bh * 2);
            uint8_t bb = 240;
            fb_fill_rect(fb, bx, by, 11, bh, br, bg, bb);
            // Peak cap
            fb_fill_rect(fb, bx, max(92, by - 3), 11, 2, 251, 191, 36);
        }

        fb_blend_bitmap(fb, 15, 183, 250, 20, mic_hint_bmp, 148, 163, 184, bg_r, bg_g, bg_b);
    } else if (page_idx == PAGE_SPK) {
        // PAGE 2: Onboard 3W Speaker Soundboard (2x2 touch pads)
        const uint8_t pad_colors[4][3] = {
            {37, 99, 235},   // Blue: 欢迎和弦
            {22, 163, 74},   // Green: 叮咚门铃
            {13, 148, 136},  // Teal: 助眠白噪音
            {147, 51, 234}   // Purple: 晨报语音试听
        };
        uint32_t now = millis();
        for (int i = 0; i < 4; i++) {
            int col = i % 2;
            int row = i / 2;
            int px = 14 + col * 130;
            int py = 44 + row * 78;
            bool hi = (active_sound_pad == i && now < sound_pad_highlight_until);
            uint8_t r = pad_colors[i][0], g = pad_colors[i][1], b = pad_colors[i][2];
            if (i == 2 && white_noise_active) {
                r = 245; g = 158; b = 11; // Amber glow when active
            }
            if (hi) {
                r = min(255, r + 50); g = min(255, g + 50); b = min(255, b + 50);
            }
            fb_draw_round_box(fb, px, py, 122, 68, r, g, b, 255, 255, 255, hi ? 3 : 2);
            fb_blend_bitmap(fb, px + 13, py + 21, 96, 26, spk_btn_bmp[i], 255, 255, 255, r, g, b);
            if (i == 2 && white_noise_active) {
                // Amber status bar beneath "助眠白噪" indicating active state
                fb_fill_rect(fb, px + 41, py + 52, 40, 4, 251, 191, 36);
            }
        }
    } else if (page_idx == PAGE_KEYS) {
        // PAGE 2: Onboard 6 ADC Buttons Matrix (GPIO 5)
        fb_draw_round_box(fb, 12, 40, 256, 38, 18, 28, 52, 251, 146, 60, 2);
        char mv_str[20];
        snprintf(mv_str, sizeof(mv_str), "%d mV", adc_mv);
        fb_draw_ascii(fb, 86, 47, mv_str, 251, 191, 36, 18, 28, 52);

        // 3x2 grid of K1..K6
        for (int i = 0; i < 6; i++) {
            int col = i % 3;
            int row = i / 3;
            int kx = 12 + col * 86;
            int ky = 86 + row * 56;
            bool pressed = (active_key == (i + 1));
            uint8_t fr = pressed ? 234 : 24;
            uint8_t fg = pressed ? 138 : 36;
            uint8_t fb_c = pressed ? 12 : 64;
            uint8_t br = pressed ? 255 : 71;
            uint8_t bg_c = pressed ? 255 : 95;
            uint8_t bb = pressed ? 255 : 130;
            fb_draw_round_box(fb, kx, ky, 82, 48, fr, fg, fb_c, br, bg_c, bb, pressed ? 3 : 2);
            fb_blend_bitmap(fb, kx + 4, ky + 12, 74, 24, adc_key_bmp[i], 255, 255, 255, fr, fg, fb_c);
        }
    } else {
        // PAGE 3: External Sensors Status (Graceful Offline / Online display)
        for (int r = 0; r < 4; r++) {
            int ry = 41 + r * 40;
            fb_draw_round_box(fb, 12, ry, 256, 36, 18, 28, 52, 56, 85, 130, 1);
            fb_blend_bitmap(fb, 20, ry + 6, 112, 24, ext_label_bmp[r], 180, 200, 230, 18, 28, 52);

            if (r == 0) {
                // PIR
                int st = ext_pir ? 2 : 1;
                uint8_t cr = ext_pir ? 251 : 148;
                uint8_t cg = ext_pir ? 191 : 163;
                uint8_t cb = ext_pir ? 36  : 184;
                fb_blend_bitmap(fb, 182, ry + 6, 68, 24, ext_status_bmp[st], cr, cg, cb, 18, 28, 52);
            } else if (r == 1) {
                if (ext_lux >= 0) {
                    char s[16]; snprintf(s, sizeof(s), "%ld lx", (long)ext_lux);
                    fb_draw_ascii(fb, 164, ry + 6, s, 251, 191, 36, 18, 28, 52);
                } else {
                    fb_blend_bitmap(fb, 182, ry + 6, 68, 24, ext_status_bmp[0], 248, 113, 113, 18, 28, 52);
                }
            } else if (r == 2) {
                if (ext_spa_online) {
                    char s[16]; snprintf(s, sizeof(s), "%.1f C", ext_temp);
                    fb_draw_ascii(fb, 164, ry + 6, s, 251, 146, 60, 18, 28, 52);
                } else {
                    fb_blend_bitmap(fb, 182, ry + 6, 68, 24, ext_status_bmp[0], 248, 113, 113, 18, 28, 52);
                }
            } else if (r == 3) {
                if (ext_spa_online) {
                    char s[16]; snprintf(s, sizeof(s), "%d hPa", (int)roundf(ext_pres));
                    fb_draw_ascii(fb, 152, ry + 6, s, 52, 211, 153, 18, 28, 52);
                } else {
                    fb_blend_bitmap(fb, 182, ry + 6, 68, 24, ext_status_bmp[0], 248, 113, 113, 18, 28, 52);
                }
            }
        }
    }

    // 3. Bottom Navigation Bar (y = 206 .. 239): [ < ]  Title + Dots  [ > ]
    fb_draw_round_box(fb, 10, 206, 44, 30, 24, 38, 68, 56, 189, 248, 2);
    fb_draw_ascii(fb, 26, 209, "-", 56, 189, 248, 24, 38, 68);

    fb_blend_bitmap(fb, 60, 209, 160, 24, page_titles_bmp[page_idx], 240, 248, 255, bg_r, bg_g, bg_b);

    fb_draw_round_box(fb, 226, 206, 44, 30, 24, 38, 68, 56, 189, 248, 2);
    fb_draw_ascii(fb, 242, 209, ".", 56, 189, 248, 24, 38, 68);
}

static void flush_fb_to_lcd(const uint16_t *fb) {
    const int strip_h = 40;
    for (int y = 0; y < LCD_V_RES; y += strip_h) {
        memcpy(dma_strip, &fb[y * LCD_H_RES], LCD_H_RES * strip_h * sizeof(uint16_t));
        esp_lcd_panel_draw_bitmap(panel_handle, LCD_X_GAP, y, LCD_X_GAP + LCD_H_RES, y + strip_h, dma_strip);
    }
}

static void fb_fill_black_and_flush() {
    memset(fb_curr, 0, LCD_H_RES * LCD_V_RES * sizeof(uint16_t));
    flush_fb_to_lcd(fb_curr);
}

static void animate_page_transition(int old_page, int new_page, int dir) {
    render_page_to_fb(fb_curr, old_page);
    render_page_to_fb(fb_next, new_page);

    const int strip_h = 40;
    // Smooth 4-step horizontal slide animation for middle viewport (y = 40..200)
    const int shifts[4] = {70, 140, 210, 280};
    for (int s = 0; s < 4; s++) {
        int offset = shifts[s];
        for (int y = 40; y < 200; y += strip_h) {
            for (int dy = 0; dy < strip_h; dy++) {
                int row_y = y + dy;
                uint16_t *dst = &dma_strip[dy * LCD_H_RES];
                const uint16_t *src_old = &fb_curr[row_y * LCD_H_RES];
                const uint16_t *src_new = &fb_next[row_y * LCD_H_RES];
                for (int x = 0; x < LCD_H_RES; x++) {
                    if (dir > 0) {
                        // Slide left (next page enters from right)
                        if (x + offset < LCD_H_RES) dst[x] = src_old[x + offset];
                        else dst[x] = src_new[x + offset - LCD_H_RES];
                    } else {
                        // Slide right (prev page enters from left)
                        if (x < offset) dst[x] = src_new[LCD_H_RES - offset + x];
                        else dst[x] = src_old[x - offset];
                    }
                }
            }
            esp_lcd_panel_draw_bitmap(panel_handle, LCD_X_GAP, y, LCD_X_GAP + LCD_H_RES, y + strip_h, dma_strip);
        }
        vTaskDelay(pdMS_TO_TICKS(4)); // Yield CPU and DMA bus so voice task feeds I2S smoothly without starvation
    }
    cur_page = new_page;
    memcpy(fb_curr, fb_next, LCD_H_RES * LCD_V_RES * sizeof(uint16_t));
    flush_fb_to_lcd(fb_curr);
    if (!voice_playing && !white_noise_active) {
        play_sound_effect(0);
    }
}

// =========================================================
// Touch Screen & Gesture Reader (CST816S)
// =========================================================
static bool read_touch(int *sx, int *sy, uint8_t *gesture) {
    uint8_t buf[6];
    if (!i2c_read_regs(CST816S_ADDR, 0x01, buf, 6)) return false;
    *gesture = buf[0];
    uint8_t fingers = buf[1];
    if (fingers == 0 || fingers > 2) return false;

    int raw_x = ((buf[2] & 0x0F) << 8) | buf[3];
    int raw_y = ((buf[4] & 0x0F) << 8) | buf[5];

    int x = (240 - raw_y) + 20;
    int y = raw_x;
    if (x < 0) x = 0;
    if (x >= LCD_H_RES) x = LCD_H_RES - 1;
    if (y < 0) y = 0;
    if (y >= LCD_V_RES) y = LCD_V_RES - 1;

    *sx = x;
    *sy = y;
    return true;
}

// =========================================================
// BLE GATT Server
// =========================================================
static bool ble_send_wake_next = false;
static void notify_ble_state() {
    if (!pSensorChar) return;
    char json[256];
    ble_send_wake_next = !ble_send_wake_next;
    if (ble_send_wake_next) {
        // Wake sleep-box packet
        uint32_t now = millis();
        uint32_t dur = night_mode ? (now - night_start_ms) / 1000 : night_duration_s;
        uint32_t wsec = wake_total_ms / 1000 + ((night_mode && wake_active) ? (now - wake_active_since) / 1000 : 0);
        snprintf(json, sizeof(json),
                 "{\"w\":1,\"night\":%d,\"rep\":%d,\"score\":%d,\"ne\":%d,\"nmax\":%.1f,\"le\":%d,\"we\":%d,\"wsec\":%lu,\"adv\":%d,\"tmin\":%.1f,\"tmax\":%.1f,\"tbad\":%lu,\"dur\":%lu,\"wact\":%d,\"wn\":%d}",
                 night_mode ? 1 : 0, has_report ? 1 : 0, wake_score, ev_noise, ev_noise_max_db,
                 ev_leak, ev_wake, (unsigned long)wsec, wake_advice,
                 (night_temp_min < 90.0f) ? night_temp_min : 0.0f,
                 (night_temp_max > -90.0f) ? night_temp_max : 0.0f,
                 (unsigned long)temp_bad_s, (unsigned long)dur, wake_active ? 1 : 0,
                 white_noise_active ? 1 : 0);
    } else {
        snprintf(json, sizeof(json),
                 "{\"page\":%d,\"db\":%.1f,\"pct\":%d,\"mv\":%d,\"key\":%d,\"vol\":%d,\"pir\":%d,\"lux\":%ld,\"temp\":%.1f,\"pres\":%.1f,\"spa\":%d,\"wn\":%d}",
                 cur_page,
                 cur_db,
                 cur_peak_pct,
                 adc_mv,
                 active_key,
                 speaker_muted ? 0 : speaker_vol,
                 ext_pir,
                 (long)ext_lux,
                 ext_temp,
                 ext_pres,
                 ext_spa_online ? 1 : 0,
                 white_noise_active ? 1 : 0);
    }
    pSensorChar->setValue((uint8_t *)json, strlen(json));
    if (ble_connected) {
        pSensorChar->notify();
    }
}

class MyServerCallbacks : public BLEServerCallbacks {
    void onConnect(BLEServer *pS) override {
        ble_connected = true;
    }
    void onDisconnect(BLEServer *pS) override {
        ble_connected = false;
        pS->startAdvertising();
    }
};

class MyCharCallbacks : public BLECharacteristicCallbacks {
    void onWrite(BLECharacteristic *pChar) override {
        String val = pChar->getValue();
        if (val.length() >= 3 && val[1] == ':') {
            int arg = val.substring(2).toInt();
            char cmd = val[0];
            if (cmd == 'P' || cmd == 'p') {
                if (arg >= 0 && arg < NUM_PAGES) pending_page = arg;
            } else if (cmd == 'S' || cmd == 's') {
                pending_sound = arg;
            } else if (cmd == 'V' || cmd == 'v') {
                speaker_vol = constrain(arg, 0, 100);
                speaker_muted = (speaker_vol == 0);
            } else if (cmd == 'N' || cmd == 'n') {
                if (arg == 1 || arg == 2) pending_night = arg;   // N:1 start night, N:2 end night
            } else if (cmd == 'W' || cmd == 'w') {
                if (arg == 4 || arg == 5) pending_sim = arg;     // W:4 simulate getting up, W:5 light leak
            } else if (cmd == 'B' || cmd == 'b') {
                white_noise_active = (arg != 0);                 // B:1 start white noise, B:0 stop
                if (white_noise_active && voice_task) xTaskNotifyGive(voice_task);
                notify_ble_state();
            } else if (cmd == 'K' || cmd == 'k') {
                // 远程模拟物理按键按下 (K1~K6 行为与开发板硬件 100% 统一)
                if (arg == 1) pending_page = (cur_page + NUM_PAGES - 1) % NUM_PAGES;
                else if (arg == 2) pending_page = (cur_page + 1) % NUM_PAGES;
                else if (arg == 3) pending_night = 1;
                else if (arg == 4) {
                    if (night_mode) pending_sim = 4;
                    else {
                        white_noise_active = !white_noise_active;
                        if (white_noise_active && voice_task) xTaskNotifyGive(voice_task);
                        notify_ble_state();
                    }
                } else if (arg == 5) {
                    if (night_mode) pending_sim = 5;
                    else pending_sound = 2; // 叮咚门铃
                } else if (arg == 6) {
                    if (night_mode) pending_night = 2;
                    else { pending_page = PAGE_WAKE; pending_sound = 7; }
                }
            }
        }
    }
};

static void init_ble() {
    BLEDevice::init(BLE_DEVICE_NAME);
    BLEDevice::setMTU(247);
    pServer = BLEDevice::createServer();
    pServer->setCallbacks(new MyServerCallbacks());
    BLEService *pService = pServer->createService(SERVICE_UUID);
    pSensorChar = pService->createCharacteristic(
        CHAR_UUID,
        BLECharacteristic::PROPERTY_READ |
        BLECharacteristic::PROPERTY_WRITE |
        BLECharacteristic::PROPERTY_NOTIFY
    );
    pSensorChar->addDescriptor(new BLE2902());
    pSensorChar->setCallbacks(new MyCharCallbacks());
    pService->start();
    BLEAdvertising *pAdv = BLEDevice::getAdvertising();
    pAdv->addServiceUUID(SERVICE_UUID);
    pAdv->setScanResponse(true);
    pAdv->setMinPreferred(0x06);
    BLEDevice::startAdvertising();
}

// =========================================================
// Setup & Main Loop
// =========================================================
void setup() {
    Serial.begin(115200);
    delay(150);
    Serial.println("Starting Wake Sleep Box + BLE: 刘航成 & 夏工");

    pinMode(PIR_PIN, INPUT_PULLDOWN);
    analogReadResolution(12);

    init_io_expander();
    init_audio();

    spi_bus_config_t buscfg = {};
    buscfg.sclk_io_num = LCD_SCLK;
    buscfg.mosi_io_num = LCD_MOSI;
    buscfg.miso_io_num = -1;
    buscfg.quadwp_io_num = -1;
    buscfg.quadhd_io_num = -1;
    buscfg.max_transfer_sz = LCD_H_RES * 40 * sizeof(uint16_t);
    ESP_ERROR_CHECK(spi_bus_initialize(LCD_HOST, &buscfg, SPI_DMA_CH_AUTO));

    esp_lcd_panel_io_handle_t io_handle = NULL;
    esp_lcd_panel_io_spi_config_t io_config = {};
    io_config.dc_gpio_num = LCD_DC;
    io_config.cs_gpio_num = LCD_CS;
    io_config.pclk_hz = 40 * 1000 * 1000;
    io_config.lcd_cmd_bits = 8;
    io_config.lcd_param_bits = 8;
    io_config.spi_mode = 0;
    io_config.trans_queue_depth = 10;
    ESP_ERROR_CHECK(esp_lcd_new_panel_io_spi((esp_lcd_spi_bus_handle_t)LCD_HOST, &io_config, &io_handle));

    esp_lcd_panel_dev_config_t panel_config = {};
    panel_config.reset_gpio_num = LCD_RST;
    panel_config.rgb_ele_order = LCD_RGB_ELEMENT_ORDER_RGB;
    panel_config.bits_per_pixel = 16;
    ESP_ERROR_CHECK(esp_lcd_new_panel_st7789(io_handle, &panel_config, &panel_handle));

    ESP_ERROR_CHECK(esp_lcd_panel_reset(panel_handle));
    ESP_ERROR_CHECK(esp_lcd_panel_init(panel_handle));
    ESP_ERROR_CHECK(esp_lcd_panel_swap_xy(panel_handle, true));
    ESP_ERROR_CHECK(esp_lcd_panel_mirror(panel_handle, false, true));
    ESP_ERROR_CHECK(esp_lcd_panel_invert_color(panel_handle, true));
    ESP_ERROR_CHECK(esp_lcd_panel_disp_on_off(panel_handle, true));

    fb_curr   = (uint16_t *)heap_caps_malloc(LCD_H_RES * LCD_V_RES * sizeof(uint16_t), MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    fb_next   = (uint16_t *)heap_caps_malloc(LCD_H_RES * LCD_V_RES * sizeof(uint16_t), MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    dma_strip = (uint16_t *)heap_caps_malloc(LCD_H_RES * 40 * sizeof(uint16_t), MALLOC_CAP_DMA);
    if (!fb_curr || !fb_next || !dma_strip) {
        Serial.println("FATAL: framebuffer allocation failed (check PSRAM=opi build option)");
        while (true) delay(1000);
    }

    voice_start_task();
    init_ble();
    render_page_to_fb(fb_curr, cur_page);
    flush_fb_to_lcd(fb_curr);
    play_sound_effect(1); // Play welcome chord on boot
}

static bool touching = false;
static bool swipe_done = false;
static int touch_x0 = 0, touch_y0 = 0;
static uint32_t touch_t0 = 0;
static uint32_t last_ext_poll = 0;
static uint32_t last_ble_notify = 0;

void loop() {
    uint32_t now = millis();

    // 1. Poll microphone & ADC buttons
    poll_microphone();
    poll_adc_keys();

    if (now - last_ext_poll >= 500) {
        last_ext_poll = now;
        poll_external_sensors();
    }

    // 2. Wake engine (night watch, events, auto start / morning)
    update_wake_engine(now);

    // 3. Touch Swipe & Tap Navigation
    int sx = 0, sy = 0;
    uint8_t gesture = 0;
    if (read_touch(&sx, &sy, &gesture)) {
        if (!touching) {
            touching = true;
            swipe_done = false;
            touch_x0 = sx;
            touch_y0 = sy;
            touch_t0 = now;
        } else if (!swipe_done && !night_mode) {
            int dx = sx - touch_x0;
            int dy = sy - touch_y0;
            if (abs(dx) >= 34 || abs(dy) >= 34) {
                swipe_done = true;
                int dir = 0;
                if (abs(dx) >= abs(dy)) {
                    dir = (dx < 0) ? 1 : -1; // Swipe left -> next, Swipe right -> prev
                } else {
                    dir = (dy < 0) ? 1 : -1; // Swipe up -> next, Swipe down -> prev
                }
                int target = (cur_page + (dir > 0 ? 1 : (NUM_PAGES - 1))) % NUM_PAGES;
                animate_page_transition(cur_page, target, dir);
                notify_ble_state();
            }
        }
    } else {
        if (touching && !swipe_done && (now - touch_t0 < 450)) {
            // Short tap at (touch_x0, touch_y0)
            if (night_mode) {
                pending_night = 2;                      // tap the dark screen = good morning
            } else if (touch_y0 >= 200) {
                if (touch_x0 < 75) {
                    int target = (cur_page + NUM_PAGES - 1) % NUM_PAGES;
                    animate_page_transition(cur_page, target, -1);
                    notify_ble_state();
                } else if (touch_x0 > 205) {
                    int target = (cur_page + 1) % NUM_PAGES;
                    animate_page_transition(cur_page, target, 1);
                    notify_ble_state();
                }
            } else if (cur_page == PAGE_WAKE && touch_y0 >= 140 && touch_y0 < 200) {
                if (touch_x0 < 140) pending_night = 1;  // [开始熄屏守夜]
                else pending_sound = 7;                 // [查看晨间报告] 日出和弦 + 板载喇叭语音晨报
            } else if (cur_page == PAGE_SPK && touch_y0 >= 42 && touch_y0 < 198) {
                // Tap on 2x2 Speaker Soundboard pads
                int col = (touch_x0 >= 140) ? 1 : 0;
                int row = (touch_y0 >= 120) ? 1 : 0;
                int pad = row * 2 + col;
                active_sound_pad = pad;
                sound_pad_highlight_until = now + 400;
                render_page_to_fb(fb_curr, cur_page);
                flush_fb_to_lcd(fb_curr);
                if (pad == 2) {
                    white_noise_active = !white_noise_active;
                    if (white_noise_active && voice_task) xTaskNotifyGive(voice_task);
                    else play_sound_effect(0);
                    notify_ble_state();
                } else if (pad == 3) {
                    pending_sound = 7;
                } else {
                    pending_sound = pad + 1;
                }
            }
        }
        touching = false;
    }

    // 4. Handle pending night / simulation / page / sound commands
    if (pending_night == 1) {
        pending_night = 0;
        if (!night_mode) start_night(millis());
    } else if (pending_night == 2) {
        pending_night = 0;
        if (night_mode) {
            end_night(millis());
        } else if (has_report) {
            // Not watching: N:2 just re-shows the last report with the sunrise chord
            pending_page = PAGE_WAKE;
            pending_sound = 7;
        }
    }

    if (pending_sim != 0) {
        int sim = pending_sim;
        pending_sim = 0;
        if (night_mode) {
            if (sim == 4) {
                sim_wake_until = millis() + 8000;      // pretend someone got up for 8 s
            } else if (sim == 5) {
                ev_leak++;                             // pretend a light leak happened
                last_leak_ev_ms = millis();
                Serial.println("[Wake] Simulated light leak");
            }
        }
    }

    if (night_mode) {
        pending_page = -1;
    } else if (pending_page >= 0 && pending_page != cur_page) {
        int target = pending_page;
        pending_page = -1;
        int dir = (target > cur_page) ? 1 : -1;
        animate_page_transition(cur_page, target, dir);
        notify_ble_state();
    } else {
        pending_page = -1;
    }

    if (pending_sound > 0) {
        int s = pending_sound;
        pending_sound = -1;
        play_sound_effect(s);
    }

    // 5. Refresh current page frame (screen stays dark in night mode)
    if (!night_mode) {
        render_page_to_fb(fb_curr, cur_page);
        flush_fb_to_lcd(fb_curr);
    }

    // 6. Notify BLE at ~5Hz (alternating sensor / wake packets)
    if (now - last_ble_notify >= 200) {
        last_ble_notify = now;
        notify_ble_state();
    }

    delay(night_mode ? 5 : 15);
}
