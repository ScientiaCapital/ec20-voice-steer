# Test plan

Fill in as you go. Each row answers one question. Use a bench EC20 only, and keep its IP address in `.env`, not in this file.

## T1: The EC20 accepts VISCA over IP from a third-party sender

| Step | Command | Expected | Result | Notes |
|---|---|---|---|---|
| 1 | `uv run ec20-steer version` | ACK or completion, not a timeout | | Confirms UDP 52381 is open |
| 2 | `uv run ec20-steer save 1` at position A | ACK | | |
| 3 | Move the camera in the web interface, then `uv run ec20-steer save 2` | ACK | | |
| 4 | `uv run ec20-steer recall 1` | The camera returns to A | | Time the move in ms |
| 5 | `uv run ec20-steer recall 2` | The camera goes to B | | |
| 6 | Recall while auto tracking is on | Does the preset win, or does tracking take over? | | Tells a designer whether both can run in one room |

## T2: Zone to preset routing with the array stand-in

Run `uv run ec20-steer route`. Each recall is appended to `docs/run.log`, which is gitignored.

| Step | Expected | Result |
|---|---|---|
| Keys 1–4 | The camera hits presets 1–4, and the debounce holds under 1.5 s | |
| Key 0 | Wide shot | |
| Back and forth, slow: keys 1, 2, 1, 2 with 3 s between presses | Every press moves the camera, and it ends on preset 2 | |
| Back and forth, fast: keys 1, 2, 1, 2 with about 0.5 s between presses | The debounce drops the presses inside 1.5 s, and the camera doesn't thrash. Note which preset it ends on | |
| Back and forth, then quiet: key 1, key 2 within 1 s, then nothing | Today the router drops the key 2 event, so the camera stays on preset 1 while zone 2 is the last talker. Note whether that's acceptable or whether a dropped zone should be recalled when the debounce ends | |
| Mic mode (`route --mic`) | Loud is preset 1, quiet is preset 2, with no thrash | |

## T3: Pearl Mini and Epiphan Edge

| Step | Expected | Result |
|---|---|---|
| Pearl Mini takes the EC20 in over NDI or RTSP | The source is live in a channel | |
| Record a 60 s run of T2, including the back and forth rows | The clip shows a shot change on each zone event | |
| Get the clip from Epiphan Edge | A link to share | |

## T4: A real ATND1061DAN (when one is available)

Check the array against the laptop first, so nothing moves until its packets look right. The EC20 takes Sony VISCA on UDP 52381, and the port can't be changed (kb: ec20/ec20-network-settings).

| Step | Expected | Result |
|---|---|---|
| Run `uv run ec20-steer listen --bind` with the laptop's bench network address (it binds 127.0.0.1 without one) and point the array's camera control target at that address, port 52381 | Each zone event shows up as a decoded packet | |
| Talk in zone 1, then zone 2 | `preset recall` lines carry the label `same bytes as ec20-steer` | |
| Read the preset numbers | Note which byte the array's preset 1 sends, `01` or `00`. Then check on the camera, in the next part of T4, which EC20 preset that byte recalls | |
| Watch for `!` lines | No missing header, no unrecognized message, and no sequence jumps. Note any that appear. Whether the EC20 accepts them is checked on the camera next | |
| Leave the room quiet | Note what the array sends, if anything, for a home or default shot | |
| Run `listen --no-reply` | Note whether the array waits for, retries without, or ignores the camera's replies | |

Then move the array to the real camera:

- Point the array's camera control target at the EC20's IP address, port 52381, VISCA over IP
- Map the array's zones to presets 1–6 in A-T Digital Microphone Manager
- Run T2 and T3 again with people talking in the room, including two people trading short lines

## T5: The EC20 brings Dante audio to a Pearl Nano

Pearl Nano has no Dante input. The EC20 takes Dante audio in (two channels, one stereo pair) and has no Dante output (kb: ec20/ec20-feature-list). Its audio input can be set to Line In, the built-in microphones, or Dante, and Dante needs the free license activated in Audinate Activator first (kb: ec20/ec20-audio-configuration). Pearl Nano takes one network source at a time, RTSP or SRT, with audio embedded (kb: pearl-nano/pearl-nano-av-inputs, pearl-nano/pearl-nano-tech-specs). If this works, a room with Dante ceiling mics streams from Pearl Nano with no Dante adapter in between.

Bench Dante source: the ceiling array if one is available, or any Dante mic, mixer, or a laptop running Dante Virtual Soundcard.

| Step | Expected | Result | Notes |
|---|---|---|---|
| 1 | Activate the EC20 Dante license, route the Dante source to the EC20 in Dante Controller, set Input Type to Dante | The audio meter in the EC20 web interface moves when someone talks | |
| 2 | Add the EC20 to Pearl Nano as an RTSP source | Video and Dante audio arrive together, and the Pearl Nano audio meter moves | Documented path |
| 3 | Repeat with SRT instead of RTSP | Same as step 2 | Note any difference in delay |
| 4 | Connect EC20 HDMI or SDI to Pearl Nano instead | Unknown. The docs don't say whether Dante audio is embedded in the EC20's HDMI or SDI output | Answer this one on the bench |
| 5 | Stream from Pearl Nano to a test endpoint and record locally | The stream and the recording carry the Dante audio | |
| 6 | Run T2 at the same time, with the array steering the camera | Shots change on each zone event and the audio stays continuous | Watch lip sync and note it, but don't claim it in docs |
| 7 | Watch the Pearl Nano in Epiphan Edge | The device and its recording show in Edge | |

## Open questions to log

- Does the EC20 send a VISCA completion (0x5y) or only an ACK (0x4y)?
- How long from the packet to a settled camera on a preset recall?
- What happens when auto tracking and a preset recall collide (T1 step 6)?
- How does the array's own hold or dwell setting compare with the router's debounce in the back and forth rows?
- Is Dante audio embedded in the EC20's HDMI and SDI outputs, or only in its network streams (T5 step 4)?
