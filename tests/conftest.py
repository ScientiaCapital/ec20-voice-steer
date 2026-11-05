import asyncio
import os
from pathlib import Path

import pytest

from ec20_voice_steer.visca import ViscaIP

FAKE_IP = "192.0.2.10"  # TEST-NET-1, never a real camera


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """No test reads the developer's real environment or a real .env file."""
    for name in list(os.environ):
        if name.startswith("EC20_STEER_"):
            monkeypatch.delenv(name)
    monkeypatch.chdir(tmp_path)


class FakeTransport:
    """Records what would go on the wire. Optionally answers each send from a script."""

    def __init__(self, inbox: asyncio.Queue[bytes], replies: list[bytes | None] | None = None) -> None:
        self.sent: list[bytes] = []
        self.closed = False
        self._inbox = inbox
        self._replies = list(replies or [])

    def sendto(self, data: bytes, addr: tuple[str, int] | None = None) -> None:
        self.sent.append(data)
        if self._replies:
            reply = self._replies.pop(0)
            if reply is not None:
                self._inbox.put_nowait(reply)

    def close(self) -> None:
        self.closed = True


def fake_camera(replies: list[bytes | None] | None = None, timeout_s: float = 0.01) -> tuple[ViscaIP, FakeTransport]:
    inbox: asyncio.Queue[bytes] = asyncio.Queue()
    transport = FakeTransport(inbox, replies)
    return ViscaIP(transport, inbox, timeout_s), transport
