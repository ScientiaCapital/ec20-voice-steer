# Test plan

Fill in as you go. Each row is one question answered.

## T1  EC20 accepts VISCA over IP from a third-party sender
| Step | Command | Expected | Result | Notes |
|---|---|---|---|---|
| 1 | `visca_ip.py --ip X --version` | ACK/completion, not timeout | | confirms UDP 52381 open |
| 2 | `--save 1` at position A | ACK | | |
| 3 | move cam in web UI, `--save 2` | ACK | | |
| 4 | `--recall 1` | camera returns to A | | time the move (ms) |
| 5 | `--recall 2` | camera goes to B | | |
| 6 | recall while visual tracking is ON | does preset win, or does tracking override? | | key for the designer: can both coexist |

## T2  Zone -> preset routing (array stand-in)
| Step | Expected | Result |
|---|---|---|
| keys 1-4 | camera hits presets 1-4, debounce holds under 1.5 s | |
| key 0 | wide shot | |
| mic mode | loud = preset 1, quiet = preset 2, no thrash | |

## T3  Pearl Mini + Edge
| Step | Expected | Result |
|---|---|---|
| Pearl Mini ingests EC20 (NDI or RTSP) | source live in channel | |
| record a 60 s run of T2 | clip shows shot changes on each zone event | |
| pull the clip from Edge | shareable link to share | |

## T4  Real ATND1061DAN (when available)
- Point array's camera-control target at EC20 IP, port 52381, VISCA over IP
- Map array zones to presets 1-6 in A-T Digital Microphone Manager
- Re-run T2/T3 with people talking in the room

## Open questions to log
- Does EC20 send VISCA completion (0x5y) or only ACK (0x4y)?
- Preset recall latency from packet to camera settled?
- Behaviour when visual tracking and preset recall collide (T1 step 6)?
