# Architecture

This page records what's verified about the EC20 side, what's a bench test, and what's unknown. The Epiphan facts come from kb.epiphan.com, read on 2026-11-05, with the page id beside each one. Nothing here comes from memory.

## The idea

A ceiling microphone array already knows which zone a talker is in. Some arrays, such as the Audio-Technica ATND1061DAN, can send a camera control command when that zone changes. If the EC20 accepts a VISCA over IP preset recall from that array, the room needs no tracking processor between them:

```text
today, often:   ceiling array  ->  tracking processor  ->  EC20
tested here:    ceiling array  ->  EC20
```

Until a real array is on the bench, `ec20-steer route` plays its part. It sends the same VISCA bytes the array would, so a pass with the stand-in carries over.

## Signal path

| Step | What happens | Where it lives |
|---|---|---|
| 1 | A talker speaks in zone N | The array, or a key press or mic level on the laptop |
| 2 | Zone N maps to preset P, unless the debounce drops it | `src/ec20_voice_steer/router.py`, `zones.default.json` |
| 3 | A VISCA over IP preset recall goes to the EC20 on UDP 52381 | `src/ec20_voice_steer/visca.py` |
| 4 | Pearl Mini takes the EC20 in over NDI or RTSP and records the shot changes | Pearl Mini, no code |
| 5 | Epiphan Edge shows the recording and shares the clip | Epiphan Edge, a Claude session step, no code |

## Verified

- The EC20 takes Sony VISCA on port 52381, and the port can't be changed (ec20/ec20-network-settings).
- VISCA over IP is one of the EC20's network control interfaces, along with the REST API, NDI, ONVIF, and the browser interface (ec20/ec20-technical-specifications).
- Presets max is 255 (ec20/ec20-technical-specifications). `ec20-steer` accepts 0 to 254, because 0xFF ends a VISCA message and can't be a preset number in one byte.
- Auto tracking has a Zone mode that calls a preset when the target enters one of up to four zones (ec20/ec20-auto-tracking-in-the-web-interface). That's video-based, and this repo tests the audio-based route.
- Pearl Mini takes SRT, RTSP and NDI|HX network video inputs (pearl-family/network-ip-video-inputs-and-ndi-support).

## Packet format used

Each datagram is an 8-byte header and a VISCA message. The header is the payload type (`0x0100` command, `0x0110` inquiry, `0x0200` control), the payload length, and a sequence number, all big-endian. Preset recall for camera address 1 is `81 01 04 3F 02 pp FF`, and preset save is `81 01 04 3F 01 pp FF`. This is the Sony VISCA over IP framing. The Epiphan pages confirm the port and that VISCA over IP is supported, and T1 confirms the framing on the bench.

## Bench tests

These are in `docs/test-plan.md`:

- T1: The EC20 replies to the version inquiry and moves on a preset recall from the laptop.
- T2: Zone routing, including two talkers going back and forth faster and slower than the debounce.
- T3: Pearl Mini records the result and Epiphan Edge shares it.
- T4: A real ATND1061DAN in place of the laptop.
- T5: Dante audio from the array into the EC20, then to Pearl Nano over RTSP or SRT.

## Unknown

- Whether the EC20 sends a VISCA completion after the ACK.
- Whether a VISCA preset recall wins over auto tracking when tracking is on.
- Whether dropping a zone change during the debounce, instead of deferring it, is good enough in a real room.
- Whether Dante audio is embedded in the EC20's HDMI and SDI outputs, or only in its network streams. The EC20 takes Dante audio in and has no Dante output (ec20/ec20-feature-list).
- Exactly what the array sends, and how its own hold or dwell setting interacts with the router's debounce.
