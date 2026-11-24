// Aule board v0.2 (capri-slate v0.2.x touch). Pin map from aule-hw/software.
// Hardware: https://github.com/meet-aule/aule-hw
#ifndef _BOARD_CONFIG_H_
#define _BOARD_CONFIG_H_

#include <driver/gpio.h>
#include <driver/i2c_types.h>

#define AUDIO_INPUT_SAMPLE_RATE     24000
#define AUDIO_OUTPUT_SAMPLE_RATE    24000

// Audio: ES7210 ADC (two microphones + speaker reference on MIC3), ES8311 DAC, PAM8302A amplifier.
// Same I2S and I2C pins as the Waveshare ESP32-S3 Audio Board, except WS (GPIO4 instead of 14).
#define AUDIO_I2S_GPIO_MCLK         GPIO_NUM_12
#define AUDIO_I2S_GPIO_BCLK         GPIO_NUM_13
#define AUDIO_I2S_GPIO_WS           GPIO_NUM_4
#define AUDIO_I2S_GPIO_DIN          GPIO_NUM_15   // ES7210 SDOUT -> ESP32
#define AUDIO_I2S_GPIO_DOUT         GPIO_NUM_16   // ESP32 -> ES8311 DSDIN
#define AUDIO_CODEC_PA_PIN          GPIO_NUM_21   // PAM8302A SD: high = on, 100k pull-down
#define AUDIO_CODEC_ES8311_ADDR     ES8311_CODEC_DEFAULT_ADDR
#define AUDIO_CODEC_ES7210_ADDR     ES7210_CODEC_DEFAULT_ADDR
#define AUDIO_INPUT_REFERENCE       true

// Starting gains from the board's level budget, to be confirmed on the bench: 30 dB clips the
// microphones near 102 dB SPL and clips the reference from ~90 % volume.
#define AUDIO_INPUT_GAIN_DB         24.0f
#define AUDIO_REFERENCE_MIC_CHANNEL 2         // physical MIC3 on the ES7210
#define AUDIO_REFERENCE_GAIN_DB     18.0f

// Q1 load switch for AUDIO_3V3: codecs, microphones and the pull-ups of the audio I2C bus.
// Low = on. A 100k pull-up keeps audio off while the ESP32 is in reset or deep sleep.
#define AUDIO_POWER_EN_GPIO         GPIO_NUM_8
#define AUDIO_POWER_SETTLE_MS       20        // AUDIO_3V3 stable before I2C; PAM8302A needs >= 10 ms

// Audio I2C bus (ES8311 0x18, ES7210 0x40, LIS2DH12 0x19). Its pull-ups go to AUDIO_3V3,
// so the bus only works while audio is powered.
#define I2C_SCL_IO                  GPIO_NUM_10
#define I2C_SDA_IO                  GPIO_NUM_11

// Controls and LEDs
#define BOOT_BUTTON_GPIO            GPIO_NUM_0    // only on the TC2030 programming pads (recovery)
#define TALK_BUTTON_GPIO            GPIO_NUM_2    // SW1, active low, RC debounced
#define BUILTIN_LED_GPIO            GPIO_NUM_38   // one WS2812B-2020

// Microphone mute (SW6) is pure hardware: muted cuts the microphones' bias and the green
// "mic on" LED, and the firmware cannot override it. This pin only reports the switch.
#define MIC_ENABLED_N_GPIO          GPIO_NUM_6    // low = microphones enabled

// LIS2DH12 accelerometer, for wake on motion
#define ACCEL_I2C_ADDR              0x19
#define ACCEL_INT1_GPIO             GPIO_NUM_17   // RTC GPIO, active high

// Power sensing. VSYS/2 only estimates the battery while USB is absent.
#define VBAT_SENSE_GPIO             GPIO_NUM_1    // ADC1_CH0
#define VBAT_SENSE_DIVIDER_RATIO    2.0f
#define VBUS_SENSE_GPIO             GPIO_NUM_18   // low = USB connected

// E-ink: Good Display GDEY075T7 (UC8179), 7.5", 800 x 480, 4 grays, 4-wire SPI over J5.
#define EPD_SPI_SCK_GPIO            GPIO_NUM_7
#define EPD_SPI_MOSI_GPIO           GPIO_NUM_9
#define EPD_CS_GPIO                 GPIO_NUM_14   // 10k pull-up: deselected during boot
#define EPD_DC_GPIO                 GPIO_NUM_47
#define EPD_RST_GPIO                GPIO_NUM_48   // active low
#define EPD_BUSY_GPIO               GPIO_NUM_39   // UC8179: low = busy
#define EPD_SPI_SCLK_HZ             (10 * 1000 * 1000)
#define EPD_WIDTH                   800
#define EPD_HEIGHT                  480

// Capacitive touch: GT911 on the panel, on its own I2C bus (always powered, unlike the audio bus).
// Its I2C address is latched from INT at the rising edge of RST, and INT has no resistor on the
// board, so the driver must always run the GT911 reset sequence before talking to it.
#define TOUCH_I2C_PORT              I2C_NUM_1
#define TOUCH_I2C_SCL_GPIO          GPIO_NUM_40   // 4.7k pull-up to 3V3
#define TOUCH_I2C_SDA_GPIO          GPIO_NUM_41   // 4.7k pull-up to 3V3
#define TOUCH_I2C_FREQ_HZ           (400 * 1000)
#define TOUCH_RST_GPIO              GPIO_NUM_42   // active low, 10k pull-up
#define TOUCH_INT_GPIO              GPIO_NUM_5    // RTC GPIO
#define TOUCH_I2C_ADDR              0x5D          // INT low during reset
#define TOUCH_I2C_ADDR_ALT          0x14          // INT high during reset

#endif // _BOARD_CONFIG_H_
