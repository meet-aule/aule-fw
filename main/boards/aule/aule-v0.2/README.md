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

The default firmware update endpoint is `https://ota.meetaule.com/ota/`.
It serves the Aule v0.2 application over HTTPS, only when the board matches and
the published version is newer. It does not force downgrades. This public
firmware service does not activate a device, link it to a child, or provide a
voice transport; those remain separate from OTA. The Aule variant overrides
xiaozhi's default cloud and does not fall back to it.

For a self-hosted service, set `CONFIG_OTA_URL` in this variant's `config.json` before running
`scripts/build.py`; that file supplies the board's build defaults. When using
ESP-IDF directly, the setting is in menuconfig under *Xiaozhi Assistant →
Default OTA URL*. Use the verified HTTPS address of your own deployment; the
browser tutor URL is not an OTA API. The public updater lives in
[aule-sw/infra/edge](https://github.com/meet-aule/aule-sw/tree/main/infra/edge).

Use the release's `aule-v0.2-X.Y.Z.ota.bin` for OTA. The `.bin` without `.ota`
is a full USB flash image for offset 0x0 and must never be offered as an OTA
application. Verify `SHA256SUMS` before publishing. Existing inherited 2.6.0
firmware needs a USB installation to enter Aule's 0.0.x version line.

A valid URL saved on the device in `wifi.ota_url` takes precedence over the
compiled default. Rebuilding does not replace that saved setting: update it
through the device's provisioning flow when changing servers. Do not erase
unrelated device settings to change the OTA address.

The reference boards built in CI (Waveshare) keep xiaozhi's default server and are for development only; their artifacts are named `dev-xiaozhi-cloud_*`.

## Notes

- The codecs and the audio I2C pull-ups are powered through Q1 (`AUDIO_POWER_EN_GPIO`, low = on), so audio is powered before the I2C bus is created.
- The touch controller has its own I2C bus, and its address is latched at reset from the INT pin, which has no resistor on the board. The driver must run the GT911 reset sequence described in `config.h`.
- Pin map source: [aule-hw/software](https://github.com/meet-aule/aule-hw/tree/main/software).
