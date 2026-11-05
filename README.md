# ec20-voice-steer

Proof of concept: voice-steered camera presets on an Epiphan EC20 with **no tracking processor** in the rack.

The idea (from the Smith + Andersen / Greg Bolton request): a Dante ceiling array such as the Audio-Technica ATND1061DAN
sends a VISCA over IP preset recall straight to the PTZ when a talker is detected in a zone. The EC20 already speaks
VISCA over IP (UDP 52381, fixed) and has presets 0-11. If the EC20 accepts the recall, the reference design is
`ceiling array -> EC20`, nothing in between.

## What this repo proves, in order

1. **EC20 accepts a VISCA over IP preset recall from an arbitrary network sender.** (`src/visca_ip.py`)
   This is the only unknown on the Epiphan side. If this works, the A-T array will work too, because it sends the same bytes.
2. **Zone -> preset routing works end to end** with a stand-in for the mic array. (`src/zone_router.py`)
   The stand-in is a laptop mic + crude level trigger, or just keystrokes. It emits "talker in zone N" events exactly
   the way the ATND1061DAN would, and the router recalls the mapped preset.
3. **Pearl Mini records the result** so there is a clip to show. Pearl Mini pulls the EC20 over NDI/RTSP and records; Edge
   gives remote access and the recording. No code needed for this step.
4. (Later, if a real ATND1061DAN shows up) swap the stand-in for the real array and re-run the same test plan.

## Hardware in the loop

| Have | Role |
|---|---|
| EC20 | PTZ under test, VISCA over IP target |
| Pearl Mini | records EC20 output, proves the shot changed |
| Edge account | remote view/record of the Pearl Mini, share the clip |
| Laptop on same LAN | runs the scripts, plays the mic array |

Not needed for steps 1-3: Dante network, ATND1061DAN, Q-SYS, Crestron.

## Quick start

```bash
python3 src/visca_ip.py --ip <EC20_IP> --save 1      # save current position as preset 1
# move the camera from the web UI, then
python3 src/visca_ip.py --ip <EC20_IP> --save 2
python3 src/visca_ip.py --ip <EC20_IP> --recall 1    # camera should move back
python3 src/zone_router.py --ip <EC20_IP>            # keys 1-6 = talker in zone 1-6
```

Log results in `docs/test-plan.md`.

## Why this matters

Designers like Greg are specifying rooms today with a $3-5k tracking processor whose only job is "audio says zone 2, tell
the camera preset 2". If the array can tell the EC20 directly, that line item disappears and the EC20 becomes the
simplest spec in the drawing. Product said the hardware is ready and the firmware side is not implemented;
this repo tests whether the existing VISCA preset path is enough without any firmware work.
