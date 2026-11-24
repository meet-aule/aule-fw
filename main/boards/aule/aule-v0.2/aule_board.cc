#include "wifi_board.h"
#include "codecs/box_audio_codec.h"
#include "application.h"
#include "button.h"
#include "config.h"
#include "led/single_led.h"

#include <esp_log.h>
#include <driver/gpio.h>
#include <driver/i2c_master.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>

#define TAG "AuleBoard"

// Aule v0.2: audio, talk button and status LED. The e-ink display and touch come next.
class AuleBoard : public WifiBoard {
private:
    i2c_master_bus_handle_t i2c_bus_ = nullptr;
    Button talk_button_;

    // The codecs and the audio I2C pull-ups sit behind Q1, so audio must be powered before
    // the I2C bus is created.
    void PowerOnAudio() {
        gpio_config_t config = {
            .pin_bit_mask = 1ULL << AUDIO_POWER_EN_GPIO,
            .mode = GPIO_MODE_OUTPUT,
            .pull_up_en = GPIO_PULLUP_DISABLE,
            .pull_down_en = GPIO_PULLDOWN_DISABLE,
            .intr_type = GPIO_INTR_DISABLE,
        };
        ESP_ERROR_CHECK(gpio_config(&config));
        ESP_ERROR_CHECK(gpio_set_level(AUDIO_POWER_EN_GPIO, 0));
        vTaskDelay(pdMS_TO_TICKS(AUDIO_POWER_SETTLE_MS));
    }

    void InitializeI2c() {
        i2c_master_bus_config_t i2c_bus_cfg = {
            .i2c_port = I2C_NUM_0,
            .sda_io_num = I2C_SDA_IO,
            .scl_io_num = I2C_SCL_IO,
            .clk_source = I2C_CLK_SRC_DEFAULT,
            .glitch_ignore_cnt = 7,
            .intr_priority = 0,
            .trans_queue_depth = 0,
            .flags = {
                .enable_internal_pullup = 0,  // external pull-ups to AUDIO_3V3
            },
        };
        ESP_ERROR_CHECK(i2c_new_master_bus(&i2c_bus_cfg, &i2c_bus_));
    }

    void InitializeMicSwitch() {
        gpio_config_t config = {
            .pin_bit_mask = 1ULL << MIC_ENABLED_N_GPIO,
            .mode = GPIO_MODE_INPUT,
            .pull_up_en = GPIO_PULLUP_DISABLE,
            .pull_down_en = GPIO_PULLDOWN_DISABLE,
            .intr_type = GPIO_INTR_DISABLE,
        };
        ESP_ERROR_CHECK(gpio_config(&config));
        if (!IsMicEnabled()) {
            ESP_LOGW(TAG, "Microphones are muted by the hardware switch");
        }
    }

    void InitializeButtons() {
        talk_button_.OnClick([this]() {
            auto& app = Application::GetInstance();
            if (app.GetDeviceState() == kDeviceStateStarting) {
                EnterWifiConfigMode();
                return;
            }
            app.ToggleChatState();
        });
    }

public:
    AuleBoard() : talk_button_(TALK_BUTTON_GPIO) {
        PowerOnAudio();
        InitializeI2c();
        InitializeMicSwitch();
        InitializeButtons();
    }

    bool IsMicEnabled() const {
        return gpio_get_level(MIC_ENABLED_N_GPIO) == 0;
    }

    virtual Led* GetLed() override {
        static SingleLed led(BUILTIN_LED_GPIO);
        return &led;
    }

    virtual AudioCodec* GetAudioCodec() override {
        static BoxAudioCodec audio_codec(i2c_bus_, AUDIO_INPUT_SAMPLE_RATE, AUDIO_OUTPUT_SAMPLE_RATE,
            AUDIO_I2S_GPIO_MCLK, AUDIO_I2S_GPIO_BCLK, AUDIO_I2S_GPIO_WS, AUDIO_I2S_GPIO_DOUT,
            AUDIO_I2S_GPIO_DIN, AUDIO_CODEC_PA_PIN, AUDIO_CODEC_ES8311_ADDR, AUDIO_CODEC_ES7210_ADDR,
            AUDIO_INPUT_REFERENCE, AUDIO_INPUT_GAIN_DB, AUDIO_REFERENCE_MIC_CHANNEL,
            AUDIO_REFERENCE_GAIN_DB);
        return &audio_codec;
    }
};

DECLARE_BOARD(AuleBoard);
