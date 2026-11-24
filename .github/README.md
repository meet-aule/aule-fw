# Aule Firmware

<p>
  <a href="https://github.com/meet-aule/aule-hw"><img src="https://img.shields.io/badge/Hardware-aule--hw-1f6feb.svg" alt="Aule hardware"></a>
  <a href="https://github.com/meet-aule/aule-fw"><img src="https://img.shields.io/badge/Firmware-Aule-2da44e.svg" alt="Aule firmware"></a>
  <a href="https://github.com/meet-aule/aule-sw"><img src="https://img.shields.io/badge/Server-aule--sw-d97706.svg" alt="Aule server"></a>
  <a href="https://github.com/meet-aule/aule-app"><img src="https://img.shields.io/badge/App-aule--app-8250df.svg" alt="Aule app"></a>
  <a href="https://github.com/78/xiaozhi-esp32"><img src="https://img.shields.io/badge/Based%20on-xiaozhi--esp32-555.svg" alt="Based on xiaozhi-esp32"></a>
</p>

(English | [Español](README.es.md))

**Aule is the open-source AI tutor.** This repository is its firmware: the software that runs on the device, listens to the child, speaks back and draws the lesson on the e-ink page.

We did not start from zero, and we do not want to. Aule's firmware is a fork of [xiaozhi-esp32](https://github.com/78/xiaozhi-esp32), the most widely used open-source voice-AI firmware for ESP32. We add what a tutor for children needs on top of it, and we send everything generic back upstream.

## What we add

- **A LiveKit transport.** Voice over WebRTC with [LiveKit](https://github.com/livekit/client-sdk-esp32), next to xiaozhi's WebSocket and MQTT transports. It connects the device to any [LiveKit Agents](https://github.com/livekit/agents) tutor, such as our server, [aule-sw](https://github.com/meet-aule/aule-sw), and lets a parent or a human tutor join the same session.
- **The Aule board.** Support for the [aule-hw](https://github.com/meet-aule/aule-hw) device: 7.5" e-ink with touch, physical microphone mute, wake on motion.
- **A tutor interface for e-ink.** Exercises, hints and progress designed for a page, not a phone screen.
- **Lessons from the field.** Pieces from our earlier device, which families used at home: Bluetooth and browser Wi-Fi setup, per-device credentials and audio-dropout concealment tuned on real home networks.

## Branches

| Branch | Purpose |
|---|---|
| The default branch | Our work. |
| `main` | Mirror of [78/xiaozhi-esp32](https://github.com/78/xiaozhi-esp32)'s `main`. Only fast-forwarded from upstream, never edited by hand. |

To bring in xiaozhi's changes:

```bash
git remote add upstream https://github.com/78/xiaozhi-esp32.git
git fetch upstream
git push origin upstream/main:main   # fast-forward the mirror
# then open a pull request from main into the default branch
```

xiaozhi's own build workflow ("Build Boards") is disabled in this fork, so updating `main` does not start its full board matrix. Branch names must not start with `ci/`, where that workflow would otherwise apply. When a sync touches xiaozhi's issue forms or `SUPPORT.md`, keep them deleted: this repository uses its own forms in `.github/ISSUE_TEMPLATE/`.

Changes meant for xiaozhi go to xiaozhi as pull requests from topic branches based on `main`. We already contribute upstream on the LiveKit side: [livekit/client-sdk-esp32#74](https://github.com/livekit/client-sdk-esp32/pull/74).

## Status

Early. Every push and pull request builds the Aule board and two reference boards on GitHub Actions. The Aule board support covers audio, the talk button and the status LED; the e-ink display, touch and the LiveKit transport are next. Nothing has run on an Aule board yet.

## License

MIT, the same license as xiaozhi-esp32. See [LICENSE](../LICENSE). xiaozhi-esp32 is © Shenzhen Xinzhi Future Technology Co., Ltd.; our additions are © Aule.

---

Made in Lima, Peru by [Aule](https://meetaule.com) · admin@meetaule.com
