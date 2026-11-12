"""Command line: `ec20-steer version | save N | recall N | home | route [--mic] | listen`.

Every command except `listen` sends VISCA over IP to one camera address. Use a bench EC20 only. `listen` plays
the camera instead: it binds a local UDP port, decodes what a sender such as a ceiling array sends, and never
contacts a camera.
"""

import argparse
import asyncio
import sys
import time
from collections.abc import Sequence
from pathlib import Path

from ec20_voice_steer import __version__
from ec20_voice_steer.listener import ListenError, serve
from ec20_voice_steer.router import WIDE, Router, load_zone_config
from ec20_voice_steer.settings import SettingsError, load_settings
from ec20_voice_steer.visca import MAX_PRESET, PORT, ReplyKind, ViscaIP, parse_reply


def _preset(value: str) -> int:
    n = int(value)
    if not 0 <= n <= MAX_PRESET:
        raise argparse.ArgumentTypeError(f"preset must be 0-{MAX_PRESET}")
    return n


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="ec20-steer", description=__doc__.splitlines()[0])
    ap.add_argument("--ip", help="EC20 address (default: EC20_STEER_IP from .env)")
    ap.add_argument("--port", type=int, help="VISCA over IP port (the EC20 uses 52381)")
    ap.add_argument("--timeout", type=float, help="seconds to wait for a reply")
    ap.add_argument("-V", "--package-version", action="version", version=f"ec20-voice-steer {__version__}")
    sub = ap.add_subparsers(dest="command", required=True)
    sub.add_parser("version", help="send the VISCA version inquiry (a safe first check)")
    sub.add_parser("home", help="move the camera to home")
    for name, text in (("save", "save the current position as preset N"), ("recall", "move to preset N")):
        p = sub.add_parser(name, help=text)
        p.add_argument("preset", type=_preset, metavar="N")
    route = sub.add_parser("route", help="play the mic array: keys 1-9 are zones, 0 is wide, q quits")
    route.add_argument("--config", type=Path, help="zone file (default: the packaged zones.default.json)")
    route.add_argument("--log", type=Path, default=Path("docs/run.log"), help="append each recall here")
    route.add_argument("--mic", action="store_true", help="laptop mic level trigger instead of keys (needs [mic])")
    route.add_argument("--threshold", type=float, default=0.05, help="mic RMS above this is zone 1, else zone 2")
    listen = sub.add_parser("listen", help="play the camera: decode VISCA a sender (such as an array) sends here")
    listen.add_argument(
        "--bind",
        default="127.0.0.1",
        help="local address to listen on (default: 127.0.0.1, this machine only). To hear an array on the "
        "network, pass this machine's bench network address, or 0.0.0.0 for every interface",
    )
    listen.add_argument(
        "--port", dest="listen_port", type=int, help="UDP port to listen on (default 52381; .env isn't read)"
    )
    listen.add_argument("--no-reply", action="store_true", help="decode only, don't answer with ACK and completion")
    listen.add_argument("--log", type=Path, default=Path("docs/run.log"), help="append each packet here")
    return ap


async def _listen(args: argparse.Namespace) -> int:
    """`listen` reads no settings: it plays the camera, so there is no camera address or port to look up."""
    if args.ip or args.timeout:
        print("listen ignores --ip and --timeout: it contacts no camera", file=sys.stderr)
    port = next((p for p in (args.listen_port, args.port) if p is not None), PORT)
    try:
        await serve(args.bind, port, reply=not args.no_reply, log_path=args.log)
    except ListenError as exc:
        print(exc, file=sys.stderr)
        return 2
    return 0


async def _one_shot(cam: ViscaIP, command: str, preset: int | None) -> int:
    started = time.monotonic()
    if command == "recall" and preset is not None:
        reply = await cam.recall(preset)
    elif command == "save" and preset is not None:
        reply = await cam.save(preset)
    elif command == "home":
        reply = await cam.home()
    else:
        reply = await cam.inquiry_version()
    print(f"{reply}  ({(time.monotonic() - started) * 1000:.0f} ms)")
    extra = await cam.receive()
    if extra is not None:
        print(parse_reply(extra))
    return 1 if reply.kind is ReplyKind.TIMEOUT else 0


async def _run_keys(router: Router) -> None:
    import termios
    import tty

    print("press 1-9 for a zone, 0 for wide, q to quit")
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    tty.setcbreak(fd)
    try:
        while True:
            ch = await asyncio.to_thread(sys.stdin.read, 1)
            if ch in ("q", ""):
                break
            if ch == "0":
                await router.event(WIDE)
            elif ch.isdigit():
                await router.event(int(ch))
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


async def _run_mic(router: Router, threshold: float) -> None:
    try:
        import numpy as np
        import sounddevice as sd
    except ImportError:
        print("mic mode needs the extra: uv sync --extra mic", file=sys.stderr)
        return
    loop = asyncio.get_running_loop()
    zones: asyncio.Queue[int] = asyncio.Queue()

    def on_block(indata: "np.ndarray", frames: int, t: object, status: object) -> None:
        rms = float(np.sqrt(np.mean(indata**2)))
        loop.call_soon_threadsafe(zones.put_nowait, 1 if rms > threshold else 2)

    print(f"mic mode: RMS > {threshold} is zone 1, else zone 2 (ctrl-c to quit)")
    with sd.InputStream(channels=1, samplerate=16000, blocksize=8000, callback=on_block):
        while True:
            await router.event(await zones.get())


async def _main(args: argparse.Namespace) -> int:
    if args.command == "listen":
        return await _listen(args)
    settings = load_settings()
    ip = args.ip or settings.ip
    if not ip:
        print("no camera address: pass --ip or set EC20_STEER_IP in .env", file=sys.stderr)
        return 2
    cam = await ViscaIP.open(ip, args.port or settings.port, args.timeout or settings.timeout_s)
    try:
        if args.command == "route":
            router = Router(cam, load_zone_config(args.config), log_path=args.log)
            await (_run_mic(router, args.threshold) if args.mic else _run_keys(router))
            return 0
        return await _one_shot(cam, args.command, getattr(args, "preset", None))
    finally:
        cam.close()


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return asyncio.run(_main(args))
    except SettingsError as exc:
        print(exc, file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
