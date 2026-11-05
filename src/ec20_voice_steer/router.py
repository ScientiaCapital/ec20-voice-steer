"""Turn "talker in zone N" events into EC20 preset recalls.

A ceiling array such as the Audio-Technica ATND1061DAN does this itself. Until one is on the bench, the key and
mic stand-ins in `cli.py` play its part, and this router holds the mapping and the debounce.
"""

import asyncio
import json
import time
from collections.abc import Callable
from enum import StrEnum
from importlib import resources
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, Field

from ec20_voice_steer.visca import Reply, ReplyKind

WIDE = "wide"


class ZoneConfig(BaseModel):
    debounce_s: float = Field(default=1.5, ge=0)
    hold_s: float = Field(default=3.0, ge=0)
    """Read from the config file but not used yet. A real array exposes a hold or dwell setting like this."""
    wide_preset: int = Field(default=0, ge=0, le=254)
    zones: dict[str, int] = Field(default_factory=lambda: {str(n): n for n in range(1, 7)})

    def preset_for(self, zone: str) -> int | None:
        return self.wide_preset if zone == WIDE else self.zones.get(zone)


def load_zone_config(path: Path | None = None) -> ZoneConfig:
    """Read a zone file, or the packaged default when no path is given."""
    if path is None:
        text = resources.files("ec20_voice_steer").joinpath("zones.default.json").read_text()
    else:
        text = path.read_text()
    return ZoneConfig.model_validate(json.loads(text))


class Camera(Protocol):
    async def recall(self, preset: int) -> Reply: ...


class Outcome(StrEnum):
    RECALLED = "recalled"
    UNMAPPED = "no preset mapped"
    ALREADY_THERE = "already on that preset"
    DEBOUNCED = "debounced"


class Router:
    def __init__(
        self,
        cam: Camera,
        cfg: ZoneConfig,
        log_path: Path | None = None,
        clock: Callable[[], float] = time.monotonic,
        echo: Callable[[str], None] = print,
    ) -> None:
        self.cam, self.cfg, self.log_path = cam, cfg, log_path
        self.clock, self.echo = clock, echo
        self.current: int | None = None
        self.last_recall: float | None = None

    async def event(self, zone: int | str) -> Outcome:
        zone = str(zone)
        preset = self.cfg.preset_for(zone)
        if preset is None:
            self.echo(f"zone {zone}: {Outcome.UNMAPPED}")
            return Outcome.UNMAPPED
        if preset == self.current:
            return Outcome.ALREADY_THERE
        now = self.clock()
        if self.last_recall is not None and now - self.last_recall < self.cfg.debounce_s:
            self.echo(f"zone {zone}: {Outcome.DEBOUNCED}")
            return Outcome.DEBOUNCED
        started = self.clock()
        reply = await self.cam.recall(preset)
        elapsed_ms = (self.clock() - started) * 1000
        self.current, self.last_recall = preset, now
        status = "timeout" if reply.kind is ReplyKind.TIMEOUT else "ok"
        line = f"{time.strftime('%H:%M:%S')} zone={zone} preset={preset} reply={status} {elapsed_ms:.0f}ms"
        self.echo(line)
        if self.log_path is not None:
            await asyncio.to_thread(_append, self.log_path, line)
        return Outcome.RECALLED


def _append(path: Path, line: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as fh:
        fh.write(line + "\n")
