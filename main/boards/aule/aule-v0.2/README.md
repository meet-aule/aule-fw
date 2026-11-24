# Aule v0.2

Board support for [Aule](https://github.com/meet-aule/aule-hw), the open-source AI tutor: ESP32-S3-WROOM-1 (16 MB flash, 8 MB octal PSRAM), ES7210 + ES8311 audio with a speaker reference for echo cancellation, PAM8302A amplifier, 7.5" e-ink with GT911 touch, a talk button and a hardware microphone mute.

## Status

| Feature | State |
|---|---|
| Audio power switch (Q1), codecs, amplifier | Implemented, not yet tested on hardware |
| Talk button (SW1), status LED | Implemented, not yet tested on hardware |
| Hardware microphone mute (SW6) | Read at boot; the switch itself works without firmware |
| E-ink display (UC8179) and GT911 touch | Not yet: next step |
| Battery level, accelerometer wake | Not yet |

The microphone and reference gains in `config.h` are starting values from the board's level budget, not measurements.

## Server

This build points to Aule's server, `https://capricorn.meetaule.com/ota/`, instead of xiaozhi's default cloud (`api.tenclass.net`), so the device never sends its identifiers or a child's voice to a third party by default. That server is [aule-sw](https://github.com/meet-aule/aule-sw), which answers the check-in and activation calls under `/ota/`. It is not published at that address yet: until it is, the device cannot activate. To use another server, set `CONFIG_OTA_URL` before building (menuconfig, *Xiaozhi Assistant → Default OTA URL*). A URL saved on the device in `wifi.ota_url` takes precedence over it.

The reference boards built in CI (Waveshare) keep xiaozhi's default server and are for development only; their artifacts are named `dev-xiaozhi-cloud_*`.

## Notes

- The codecs and the audio I2C pull-ups are powered through Q1 (`AUDIO_POWER_EN_GPIO`, low = on), so audio is powered before the I2C bus is created.
- The touch controller has its own I2C bus, and its address is latched at reset from the INT pin, which has no resistor on the board. The driver must run the GT911 reset sequence described in `config.h`.
- Pin map source: [aule-hw/software](https://github.com/meet-aule/aule-hw/tree/main/software).
