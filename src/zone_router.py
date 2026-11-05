#!/usr/bin/env python3
"""Stand-in for the ceiling mic array: turns 'talker in zone N' events into EC20 preset recalls.

The real ATND1061DAN does exactly this in firmware (zone -> VISCA preset). Until one is on the bench,
this script plays that role so the EC20 side and the routing logic can be proven.

Modes:
  (default)  press 1-6 to simulate a talker in zone 1-6, 0 = wide, q = quit
  --mic      crude level trigger on the laptop mic: loud = zone 1, quiet = zone 2 (needs sounddevice + numpy)

Config: zones.json maps zone -> preset and holds a debounce (seconds) so chatter does not thrash the camera,
mirroring the hold/dwell settings a real array exposes.
"""
import argparse
import json
import sys
import time
from pathlib import Path

from visca_ip import ViscaIP

DEFAULT_CFG = {
    "debounce_s": 1.5,
    "hold_s": 3.0,
    "zones": {"1": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6},
    "wide_preset": 0
}


class Router:
    def __init__(self, cam, cfg, log):
        self.cam, self.cfg, self.log = cam, cfg, log
        self.current = None
        self.last_recall = 0.0

    def event(self, zone):
        preset = self.cfg["zones"].get(str(zone))
        if preset is None:
            print(f"zone {zone}: no preset mapped")
            return
        now = time.time()
        if preset == self.current:
            return
        if now - self.last_recall < self.cfg["debounce_s"]:
            print(f"zone {zone}: debounced")
            return
        t0 = time.time()
        r = self.cam.recall(preset)
        dt = (time.time() - t0) * 1000
        self.current, self.last_recall = preset, now
        line = f"{time.strftime('%H:%M:%S')} zone={zone} preset={preset} reply={'ok' if r else 'timeout'} {dt:.0f}ms"
        print(line)
        self.log.write(line + "\n"); self.log.flush()


def run_keys(router):
    print("press 1-6 for zone, 0 for wide, q to quit")
    import termios, tty
    fd = sys.stdin.fileno(); old = termios.tcgetattr(fd); tty.setcbreak(fd)
    try:
        while True:
            ch = sys.stdin.read(1)
            if ch == "q":
                break
            if ch == "0":
                router.event("wide")
            elif ch.isdigit():
                router.event(int(ch))
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def run_mic(router, threshold):
    import numpy as np
    import sounddevice as sd
    print(f"mic mode: RMS > {threshold} = zone 1, else zone 2 (ctrl-c to quit)")
    def cb(indata, frames, t, status):
        rms = float(np.sqrt(np.mean(indata ** 2)))
        router.event(1 if rms > threshold else 2)
    with sd.InputStream(channels=1, samplerate=16000, blocksize=8000, callback=cb):
        while True:
            time.sleep(0.5)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ip", required=True)
    ap.add_argument("--config", default=str(Path(__file__).with_name("zones.json")))
    ap.add_argument("--mic", action="store_true")
    ap.add_argument("--threshold", type=float, default=0.05)
    a = ap.parse_args()

    cfg = dict(DEFAULT_CFG)
    p = Path(a.config)
    if p.exists():
        cfg.update(json.loads(p.read_text()))
    cfg["zones"]["wide"] = cfg["wide_preset"]

    log = open(Path(__file__).parents[1] / "docs" / "run.log", "a")
    router = Router(ViscaIP(a.ip), cfg, log)
    if a.mic:
        run_mic(router, a.threshold)
    else:
        run_keys(router)


if __name__ == "__main__":
    main()
