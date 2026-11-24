# Changelog

## 0.0.1 (2026-11-24)

First numbered version. Everything before it is in the git history.

* built on xiaozhi-esp32 2.6.0, with its WebSocket and MQTT + UDP transports, wake word and device-side MCP
* board support for Aule v0.2: audio power, the ES7210 and ES8311 codecs, the amplifier, the talk button and the status LED, none of it tested on a board yet; the e-ink display and touch come next
* the Aule board checks for updates and activates with Aule's own server instead of xiaozhi's cloud; that address is not live yet
* at boot, the firmware's first log line names the version, the commit and the board, and the update check reports the commit
