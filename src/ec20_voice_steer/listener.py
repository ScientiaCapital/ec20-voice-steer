"""A fake EC20: listen on UDP 52381 and decode every VISCA packet a sender such as a ceiling array sends.

Point the array's camera control target at the laptop instead of the camera. Nothing moves and no preset is
overwritten. Each packet is printed, decoded and compared with what `ec20-steer` itself sends. By default the
listener answers a request it recognizes (ACK, then completion) so a sender that waits for replies keeps going.
It doesn't answer anything it can't name, so a sender's bad packet isn't dressed up as a success.
"""

import asyncio
import contextlib
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from ec20_voice_steer.visca import (
    CMD,
    CONTROL,
    HEADER,
    HOME_MESSAGE,
    INQUIRY,
    MAX_PRESET,
    RESET_SEQUENCE,
    VERSION_INQUIRY,
    build_packet,
    recall_message,
    save_message,
)

REPLY = 0x0111
CONTROL_REPLY = 0x0201
PAYLOAD_TYPES = {CMD: "command", INQUIRY: "inquiry", REPLY: "reply", CONTROL: "control", CONTROL_REPLY: "control reply"}
ACK_BODY = bytes([0x90, 0x41, 0xFF])
COMPLETION_BODY = bytes([0x90, 0x51, 0xFF])
INQUIRY_COMPLETION_BODY = bytes([0x90, 0x50, 0xFF])
"""In VISCA an inquiry completion carries data. This fake one sends an empty completion."""
NOT_RECOGNIZED = "not recognized"
SEQ_MASK = 0xFFFFFFFF
HEX_LIMIT = 64
"""Bytes of a packet shown as hex in a printed line, log line or error report. Longer packets are cut short."""
LOG_QUEUE_MAX = 1000
"""Log lines waiting for the writer. Past this, new lines are dropped and counted, so a flood can't grow memory."""


def say(line: str) -> None:
    """Print and flush, so a listener whose output goes to a file or pipe loses nothing when it's stopped."""
    print(line, flush=True)


def warn(line: str) -> None:
    print(line, file=sys.stderr, flush=True)


def hex_preview(data: bytes, sep: str = "") -> str:
    """Hex of the first HEX_LIMIT bytes, and the total length when the rest is cut off."""
    head = data[:HEX_LIMIT]
    shown = head.hex(sep) if sep else head.hex()
    return shown if len(data) <= HEX_LIMIT else f"{shown} ... ({len(data)} bytes)"


class ListenError(Exception):
    """The listener can't start: the port is taken, the address isn't on this machine, or the log can't be written."""


@dataclass(frozen=True)
class Decoded:
    framing: str
    """"visca-over-ip" (8-byte header), "raw visca" (no header), or "unknown"."""
    payload_type: int | None
    seq: int | None
    body: bytes
    meaning: str
    notes: tuple[str, ...] = ()

    @property
    def type_name(self) -> str:
        if self.payload_type is None:
            return "-"
        return PAYLOAD_TYPES.get(self.payload_type, f"0x{self.payload_type:04x}")


def describe(body: bytes) -> str:
    """Name a VISCA message. Preset numbers are the raw byte the sender put on the wire."""
    if len(body) == 7 and body[1:4] == b"\x01\x04\x3f" and body[6] == 0xFF:
        action = {0x00: "preset reset", 0x01: "preset save", 0x02: "preset recall"}.get(body[4])
        if action:
            return f"{action} {body[5]} (camera address {body[0] & 0x0F})"
    if body[1:] == HOME_MESSAGE[1:]:
        return f"home (camera address {body[0] & 0x0F})"
    if body[1:] == VERSION_INQUIRY[1:]:
        return f"version inquiry (camera address {body[0] & 0x0F})"
    if body == RESET_SEQUENCE:
        return "sequence reset"
    return NOT_RECOGNIZED


def _looks_like_visca(data: bytes) -> bool:
    return len(data) >= 3 and 0x81 <= data[0] <= 0x88 and data[-1] == 0xFF


def decode(data: bytes) -> Decoded:
    """Split a datagram into header and VISCA message, and say what it asks the camera to do."""
    if len(data) >= HEADER.size:
        payload_type, length, seq = HEADER.unpack_from(data)
        if payload_type in PAYLOAD_TYPES:
            body = data[HEADER.size :]
            notes = []
            if length != len(body):
                notes.append(f"header says {length} payload bytes, packet carries {len(body)}")
            meaning = describe(body)
            if meaning == NOT_RECOGNIZED and payload_type in (CMD, INQUIRY, CONTROL):
                notes.append("message not recognized by this tool, so it isn't answered")
            return Decoded("visca-over-ip", payload_type, seq, body, meaning, tuple(notes))
    if _looks_like_visca(data):
        notes = (
            "no VISCA over IP header: ec20-steer always sends one, and whether the EC20 accepts a packet "
            "without it is a bench question. Not answered",
        )
        return Decoded("raw visca", None, None, data, describe(data), notes)
    note = f"neither VISCA over IP nor raw VISCA (first bytes {data[:2].hex() or 'none'})"
    return Decoded("unknown", None, None, data, NOT_RECOGNIZED, (note,))


def _ec20_steer_packet(d: Decoded) -> tuple[int, bytes] | None:
    """The payload type and message `ec20-steer` would send for the same request, or None if it has no such command."""
    preset = d.body[5] if len(d.body) == 7 else MAX_PRESET + 1
    if d.meaning.startswith("preset recall") and preset <= MAX_PRESET:
        return CMD, recall_message(preset)
    if d.meaning.startswith("preset save") and preset <= MAX_PRESET:
        return CMD, save_message(preset)
    if d.meaning.startswith("home"):
        return CMD, HOME_MESSAGE
    if d.meaning.startswith("version inquiry"):
        return INQUIRY, VERSION_INQUIRY
    if d.meaning == "sequence reset":
        return CONTROL, RESET_SEQUENCE
    return None


def ec20_steer_match(d: Decoded) -> str | None:
    """Compare a packet with what `ec20-steer` sends for the same request, sequence number aside.

    A match means the bytes equal what T1 and T2 send to the EC20 on the bench.
    """
    if d.framing != "visca-over-ip" or d.seq is None or d.payload_type in (None, REPLY, CONTROL_REPLY):
        return None
    ours = _ec20_steer_packet(d)
    if ours is None:
        return None
    payload_type, message = ours
    length_ok = not any(n.startswith("header says") for n in d.notes)
    if payload_type == d.payload_type and message == d.body and length_ok:
        return "same bytes as ec20-steer"
    diffs = []
    if payload_type != d.payload_type:
        diffs.append(f"payload type {d.type_name}, ec20-steer uses {PAYLOAD_TYPES[payload_type]}")
    if message != d.body:
        diffs.append(f"message {d.body.hex(' ')}, ec20-steer sends {message.hex(' ')}")
    if not length_ok:
        diffs.append("header length field is off")
    return "differs from ec20-steer: " + "; ".join(diffs)


def replies_for(d: Decoded) -> list[bytes]:
    """What this fake camera sends back: only for VISCA over IP requests it recognizes, never for anything else."""
    if d.framing != "visca-over-ip" or d.seq is None or d.meaning == NOT_RECOGNIZED:
        return []
    if d.payload_type == CONTROL:
        return [build_packet(CONTROL_REPLY, b"\x01", d.seq)]
    if d.payload_type == CMD:
        return [build_packet(REPLY, ACK_BODY, d.seq), build_packet(REPLY, COMPLETION_BODY, d.seq)]
    if d.payload_type == INQUIRY:
        return [build_packet(REPLY, INQUIRY_COMPLETION_BODY, d.seq)]
    return []


@dataclass
class SequenceWatch:
    """Track each sender's sequence numbers. A receiver may reject a sender whose numbers jump or repeat."""

    last: dict[tuple[str, int], int] = field(default_factory=dict)

    def check(self, sender: tuple[str, int], d: Decoded) -> str | None:
        if d.seq is None or d.payload_type in (REPLY, CONTROL_REPLY):
            return None
        if d.payload_type == CONTROL:
            self.last[sender] = d.seq
            return None
        previous = self.last.get(sender)
        self.last[sender] = d.seq
        if previous is None or d.seq == (previous + 1) & SEQ_MASK:
            return None
        if d.seq == previous:
            return f"sequence {d.seq} repeated"
        return f"sequence jumped from {previous} to {d.seq}"


def _append(path: Path, line: str) -> None:
    with path.open("a") as fh:
        fh.write(line + "\n")


class Listener(asyncio.DatagramProtocol):
    """Decode, answer, print and log every datagram. Tests drive `datagram_received` directly.

    Replies go out first, so a slow or failing console or log can't stall the sender. Log lines go on a queue that
    `write_log` drains off the event loop.
    """

    def __init__(
        self,
        reply: bool = True,
        log_path: Path | None = None,
        echo: Callable[[str], None] = say,
        clock: Callable[[], float] = time.time,
        report: Callable[[str], None] = warn,
        log_queue_size: int = LOG_QUEUE_MAX,
    ) -> None:
        self.reply, self.log_path, self.echo, self.clock, self.report = reply, log_path, echo, clock, report
        self.transport: asyncio.DatagramTransport | None = None
        self.sequence = SequenceWatch()
        self.log_queue: asyncio.Queue[str] = asyncio.Queue(maxsize=log_queue_size)
        self.done: asyncio.Future[None] | None = None
        self.count = self.replies_sent = self.socket_errors = self.log_errors = self.log_dropped = 0

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.transport = transport  # type: ignore[assignment]

    def connection_lost(self, exc: Exception | None) -> None:
        if self.done is not None and not self.done.done():
            if exc is None:
                self.done.set_result(None)
            else:
                self.done.set_exception(exc)

    def error_received(self, exc: Exception) -> None:
        self.socket_errors += 1
        self.report(f"      ! socket error: {exc!r} (the last reply may not have reached the sender)")

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        try:
            self._handle(data, addr)
        except Exception as exc:  # keep listening, but say exactly which packet broke what
            self.report(f"listen: failed on packet from {addr[0]}:{addr[1]} ({hex_preview(data)}): {exc!r}")

    def _send_replies(self, d: Decoded, addr: tuple[str, int]) -> str:
        if not self.reply:
            return "none (--no-reply)"
        packets = replies_for(d)
        if not packets:
            return "none"
        if self.transport is None:
            return "none (no socket)"
        for packet in packets:
            self.transport.sendto(packet, addr)
        self.replies_sent += len(packets)
        return " + ".join(p[HEADER.size :].hex(" ") for p in packets)

    def _handle(self, data: bytes, addr: tuple[str, int]) -> None:
        self.count += 1
        d = decode(data)
        sent = self._send_replies(d, addr)
        notes = list(d.notes)
        jump = self.sequence.check(addr, d)
        if jump:
            notes.append(jump)
        match = ec20_steer_match(d)
        now = self.clock()
        seq = "-" if d.seq is None else str(d.seq)
        line = f"#{self.count}  {d.framing}  {d.type_name}  seq {seq}  {hex_preview(d.body, ' ')}  -> {d.meaning}"
        if match:
            line += f"  [{match}]"
        line += f"  reply: {sent}"
        shown = time.strftime("%H:%M:%S", time.localtime(now)) + "  " + line
        for note in notes:
            shown += f"\n      ! {note}"
        self.echo(shown)
        if self.log_path is not None:
            stamp = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(now)) + f".{int(now % 1 * 1000):03d}"
            noted = "".join(f"  ! {n}" for n in notes)
            self._queue_log(f"{stamp}  listen from {addr[0]}:{addr[1]}  raw {hex_preview(data)}  {line}{noted}")

    def _queue_log(self, line: str) -> None:
        """Queue a log line, or drop and count it when the writer is behind. The first drop is reported."""
        try:
            self.log_queue.put_nowait(line)
        except asyncio.QueueFull:
            self.log_dropped += 1
            if self.log_dropped == 1:
                self.report(f"listen: log queue is full ({self.log_queue.maxsize} lines); dropping log lines")

    async def write_log(self) -> None:
        """Write queued log lines in order, off the event loop. A failing log is reported once, then counted."""
        while True:
            line = await self.log_queue.get()
            try:
                if self.log_path is not None:
                    await asyncio.to_thread(_append, self.log_path, line)
            except OSError as exc:
                self.log_errors += 1
                if self.log_errors == 1:
                    self.report(
                        f"listen: log writes to {self.log_path} are failing ({exc}); still decoding and answering"
                    )
            finally:
                self.log_queue.task_done()

    def summary(self) -> str:
        return (
            f"{self.count} packets, {self.replies_sent} replies sent, "
            f"{self.socket_errors} socket errors, {self.log_errors} log errors, {self.log_dropped} log lines dropped"
        )


def _touch(path: Path) -> Path:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a"):
        pass
    return path


async def _prepare_log(log_path: Path) -> Path:
    try:
        path = await asyncio.to_thread(_touch, log_path)
    except OSError as exc:
        raise ListenError(
            f"listen: can't write log {log_path}: {exc.strerror or exc}. Pass --log to choose another file"
        ) from None
    return path


async def serve(
    bind: str, port: int, reply: bool = True, log_path: Path | None = None, echo: Callable[[str], None] = say
) -> None:
    """Listen until stopped. Binds a local UDP port only and answers whoever sent to it; it never contacts a camera."""
    if log_path is not None:
        log_path = await _prepare_log(log_path)
    loop = asyncio.get_running_loop()
    listener = Listener(reply, log_path, echo)
    listener.done = loop.create_future()
    try:
        transport, _ = await loop.create_datagram_endpoint(lambda: listener, local_addr=(bind, port))
    except OSError as exc:
        hint = " Is another ec20-steer listen running? Pass --port to use another." if port == 52381 else ""
        raise ListenError(f"listen: can't bind {bind}:{port}: {exc.strerror or exc}.{hint}") from None
    writer = asyncio.create_task(listener.write_log())
    where = f", logging to {log_path}" if log_path is not None else ""
    echo(f"fake EC20 listening on {bind}:{port} (replies {'on' if reply else 'off'}{where}), ctrl-c to stop")
    try:
        await listener.done
    finally:
        transport.close()
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(listener.log_queue.join(), timeout=2)
        writer.cancel()
        echo(f"listen stopped: {listener.summary()}")
