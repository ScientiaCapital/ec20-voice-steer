"""A small async VISCA over IP client for the Epiphan EC20.

The EC20 listens for Sony VISCA on UDP 52381, and the port can't be changed (kb: ec20/ec20-network-settings).
Each datagram is an 8-byte header followed by a VISCA message:

    bytes 0-1  payload type: 0x0100 command, 0x0110 inquiry, 0x0200 control
    bytes 2-3  payload length, big-endian
    bytes 4-7  sequence number, big-endian

Preset messages for camera address 1: recall ``81 01 04 3F 02 pp FF``, save ``81 01 04 3F 01 pp FF``.
"""

import asyncio
import struct
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

PORT = 52381
CMD = 0x0100
INQUIRY = 0x0110
CONTROL = 0x0200
HEADER = struct.Struct(">HHI")
MAX_PRESET = 0xFE
"""0xFF ends a VISCA message, so the highest preset number one byte can carry is 254."""


def build_packet(payload_type: int, payload: bytes, seq: int) -> bytes:
    """Wrap a VISCA message in the VISCA over IP header."""
    return HEADER.pack(payload_type, len(payload), seq & 0xFFFFFFFF) + payload


def _preset_byte(preset: int) -> int:
    if not 0 <= preset <= MAX_PRESET:
        raise ValueError(f"preset must be 0-{MAX_PRESET}, got {preset}")
    return preset


def recall_message(preset: int) -> bytes:
    return bytes([0x81, 0x01, 0x04, 0x3F, 0x02, _preset_byte(preset), 0xFF])


def save_message(preset: int) -> bytes:
    return bytes([0x81, 0x01, 0x04, 0x3F, 0x01, _preset_byte(preset), 0xFF])


HOME_MESSAGE = bytes([0x81, 0x01, 0x06, 0x04, 0xFF])
VERSION_INQUIRY = bytes([0x81, 0x09, 0x00, 0x02, 0xFF])
RESET_SEQUENCE = b"\x01"


class ReplyKind(StrEnum):
    ACK = "ACK"
    COMPLETION = "COMPLETION"
    ERROR = "ERROR"
    OTHER = "reply"
    TIMEOUT = "no reply (timeout)"


@dataclass(frozen=True)
class Reply:
    kind: ReplyKind
    raw: bytes | None

    def __str__(self) -> str:
        if self.raw is None:
            return str(self.kind)
        body = self.raw[HEADER.size :] if self.kind is not ReplyKind.OTHER else self.raw
        return f"{self.kind} {body.hex()}"


def parse_reply(data: bytes | None) -> Reply:
    """Classify a reply by the high nibble of its second VISCA byte: 4 ACK, 5 completion, 6 error."""
    if data is None:
        return Reply(ReplyKind.TIMEOUT, None)
    body = data[HEADER.size :]
    if len(body) >= 3:
        nibble = body[1] & 0xF0
        if nibble == 0x40:
            return Reply(ReplyKind.ACK, data)
        if nibble == 0x50:
            return Reply(ReplyKind.COMPLETION, data)
        if nibble == 0x60:
            return Reply(ReplyKind.ERROR, data)
    return Reply(ReplyKind.OTHER, data)


class DatagramTransport(Protocol):
    def sendto(self, data: bytes, addr: tuple[str, int] | None = None) -> None: ...
    def close(self) -> None: ...


class _Inbox(asyncio.DatagramProtocol):
    def __init__(self) -> None:
        self.queue: asyncio.Queue[bytes] = asyncio.Queue()

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        self.queue.put_nowait(data)


class ViscaIP:
    """One camera. Use ``await ViscaIP.open(ip)``; the constructor takes a transport so tests need no network."""

    def __init__(self, transport: DatagramTransport, inbox: asyncio.Queue[bytes], timeout_s: float = 1.0) -> None:
        self._transport = transport
        self._inbox = inbox
        self.timeout_s = timeout_s
        self.seq = 0

    @classmethod
    async def open(cls, ip: str, port: int = PORT, timeout_s: float = 1.0) -> "ViscaIP":
        loop = asyncio.get_running_loop()
        transport, inbox = await loop.create_datagram_endpoint(_Inbox, remote_addr=(ip, port))
        cam = cls(transport, inbox.queue, timeout_s)
        await cam.reset_sequence()
        return cam

    def close(self) -> None:
        self._transport.close()

    async def receive(self, timeout_s: float | None = None) -> bytes | None:
        try:
            return await asyncio.wait_for(self._inbox.get(), timeout_s if timeout_s is not None else self.timeout_s)
        except TimeoutError:
            return None

    async def _send(self, payload_type: int, payload: bytes) -> Reply:
        self.seq = (self.seq + 1) & 0xFFFFFFFF
        self._transport.sendto(build_packet(payload_type, payload, self.seq))
        return parse_reply(await self.receive())

    async def reset_sequence(self) -> None:
        """Ask the camera to reset its sequence counter. A missing reply is not an error here."""
        self.seq = 0
        self._transport.sendto(build_packet(CONTROL, RESET_SEQUENCE, 0))
        await self.receive()

    async def recall(self, preset: int) -> Reply:
        return await self._send(CMD, recall_message(preset))

    async def save(self, preset: int) -> Reply:
        return await self._send(CMD, save_message(preset))

    async def home(self) -> Reply:
        return await self._send(CMD, HOME_MESSAGE)

    async def inquiry_version(self) -> Reply:
        return await self._send(INQUIRY, VERSION_INQUIRY)
