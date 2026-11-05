# ec20-voice-steer: project context

Safe to commit. No names of customers, consultants, people, rooms or devices belong here.

## Why this exists
A consulting AV designer asked whether a Dante ceiling microphone array can steer an EC20 directly. Rooms specified
today often add a tracking processor whose only job is to turn "the audio says zone 2" into "camera, go to preset
2". If the array can send that recall itself, that line item goes away and the EC20 is the simplest camera in the
drawing. Product said the hardware is ready and a firmware feature for this isn't implemented, so this repo tests
whether the existing VISCA preset path is enough without firmware work.

## Decisions
- Working name: ec20-voice-steer. Apache 2.0. Copyright Epiphan Systems Inc. Not an officially supported Epiphan
  product.
- Private repository.
- A laptop plays the array (keys, or a crude mic level trigger) until a real array is on the bench. It sends the
  same bytes the array would, so a pass on the bench carries over.
- Debounce drops a zone change that arrives too soon after the last recall. It doesn't defer it. The test plan's
  back and forth rows decide whether that's good enough.
- `hold_s` is read from the zone file and not used yet.
- Preset numbers are limited to 0 to 254, because 0xFF ends a VISCA message.

## Verified facts (kb.epiphan.com, checked 2026-11-05)
- The EC20 takes Sony VISCA on port 52381, and that port can't be changed (ec20/ec20-network-settings).
- Network control: REST API, VISCA over IP, NDI, ONVIF, and the browser interface (ec20/ec20-technical-specifications).
- Presets max is 255 (ec20/ec20-technical-specifications). The web interface shows saved presets out of a maximum,
  for example "Total 3 / 50" (ec20/ec20-web-interface-overview). The Q-SYS plugin exposes presets 0 to 11
  (ec20/control-panel); that is the plugin's range, not the camera's.
- Auto tracking has Presenter and Zone modes. Zone mode calls a preset when the target enters one of up to four
  zones, and either mode can start from, and return to, a saved preset (ec20/ec20-auto-tracking-in-the-web-interface).
- The EC20 accepts Dante audio input, two channels (one stereo pair). It doesn't support Dante output or Dante
  video (ec20/ec20-feature-list). Input Type can be Line In, the built-in microphones, or Dante, after the free
  Dante license is activated in Audinate Activator. Audio is AAC at 48 kHz (ec20/ec20-audio-configuration).
- Pearl Mini network video inputs: SRT, RTSP, NDI|HX (pearl-family/network-ip-video-inputs-and-ndi-support).
- Pearl Nano network video inputs: SRT and RTSP, one at a time, with audio embedded over Ethernet
  (pearl-nano/pearl-nano-av-inputs, pearl-nano/pearl-nano-tech-specs).

## Open questions
- Does the EC20 send a VISCA completion or only an ACK? (T1)
- When auto tracking is on, does a VISCA preset recall win or does tracking take over? (T1 step 6)
- Is the debounce-drop behavior acceptable for two talkers trading short lines? (T2 back and forth rows)
- Is Dante audio embedded in the EC20's HDMI and SDI outputs, or only in its network streams? (T5 step 4)
- What does the array send exactly, and does its own hold or dwell setting replace the router's debounce? (T4)

## Where to pick up (November 5, 2026)
State: PR #1 brought the repo to the roomsync standard. The code, the tests and the docs are in place. Nothing has
run against real hardware yet. Tim is setting up a Pearl Mini and an EC20 at home as the first bench.

Start here, in order:
1. Bench setup. Put the EC20, the Pearl Mini and a laptop on one network you control. Note the EC20 firmware
   version from its web interface. Copy `.env.example` to `.env` and set `EC20_STEER_IP`. Never commit the address.
2. T1 in `docs/test-plan.md`. Start with `uv run ec20-steer version`, then save and recall two presets, then step 6
   with auto tracking on. Write results in the test plan without addresses or room names.
3. T2, including the back and forth rows. Decide whether a debounced zone should be dropped (today) or recalled
   when the debounce ends, and open an issue if it should change.
4. T3. Add the EC20 to the Pearl Mini as an RTSP or NDI|HX source, record a 60-second run of T2, and share the clip
   from Epiphan Edge.
5. T5 needs a Dante source and a Pearl Nano. T4 needs a real ceiling array. Both wait on hardware.

Before starting, read `AGENTS.md`. The short version: only the bench EC20 moves, every EC20 fact is cited from
kb.epiphan.com, and no customer names or camera addresses go in the repo.

Still open for the maintainer:
- The first commit (2e20a8e) still names the customer and the consultant. Rewriting history would remove them.
- Main has no branch protection, so a PR can merge before CI finishes. Roomsync-style protection would require
  green CI and a review.
