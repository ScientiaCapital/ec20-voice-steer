from pathlib import Path

import pytest

from ec20_voice_steer.router import WIDE, Outcome, Router, ZoneConfig, load_zone_config
from ec20_voice_steer.visca import Reply, ReplyKind


class FakeCam:
    def __init__(self, kind: ReplyKind = ReplyKind.ACK) -> None:
        self.recalled: list[int] = []
        self.kind = kind

    async def recall(self, preset: int) -> Reply:
        self.recalled.append(preset)
        return Reply(self.kind, None if self.kind is ReplyKind.TIMEOUT else b"")


class Clock:
    def __init__(self) -> None:
        self.t = 100.0

    def __call__(self) -> float:
        return self.t


@pytest.fixture
def clock() -> Clock:
    return Clock()


def make(clock: Clock, cam: FakeCam | None = None, **cfg: object) -> tuple[Router, FakeCam, list[str]]:
    cam = cam or FakeCam()
    lines: list[str] = []
    return Router(cam, ZoneConfig(**cfg), clock=clock, echo=lines.append), cam, lines


async def test_first_event_recalls(clock: Clock) -> None:
    router, cam, _ = make(clock)
    assert await router.event(2) is Outcome.RECALLED
    assert cam.recalled == [2]


async def test_debounce_drops_a_fast_second_zone(clock: Clock) -> None:
    router, cam, _ = make(clock, debounce_s=1.5)
    await router.event(1)
    clock.t += 1.0
    assert await router.event(2) is Outcome.DEBOUNCED
    clock.t += 0.6
    assert await router.event(2) is Outcome.RECALLED
    assert cam.recalled == [1, 2]


async def test_same_preset_is_not_resent(clock: Clock) -> None:
    router, cam, _ = make(clock)
    await router.event(1)
    clock.t += 10
    assert await router.event(1) is Outcome.ALREADY_THERE
    assert cam.recalled == [1]


async def test_wide_uses_wide_preset(clock: Clock) -> None:
    router, cam, _ = make(clock, wide_preset=9)
    await router.event(WIDE)
    assert cam.recalled == [9]


async def test_unmapped_zone_is_skipped(clock: Clock) -> None:
    router, cam, lines = make(clock, zones={"1": 1})
    assert await router.event(7) is Outcome.UNMAPPED
    assert cam.recalled == []
    assert "no preset mapped" in lines[0]


async def test_timeout_still_counts_as_a_recall_attempt(clock: Clock) -> None:
    router, _, lines = make(clock, FakeCam(ReplyKind.TIMEOUT))
    await router.event(1)
    assert "reply=timeout" in lines[0]


async def test_log_file_gets_one_line_per_recall(clock: Clock, tmp_path: Path) -> None:
    log = tmp_path / "logs" / "run.log"
    router = Router(FakeCam(), ZoneConfig(), log_path=log, clock=clock, echo=lambda _: None)
    await router.event(1)
    clock.t += 5
    await router.event(2)
    assert len(log.read_text().splitlines()) == 2


def test_packaged_default_config_loads() -> None:
    cfg = load_zone_config()
    assert cfg.zones["1"] == 1
    assert cfg.debounce_s == 1.5


def test_custom_config_file(tmp_path: Path) -> None:
    path = tmp_path / "zones.json"
    path.write_text('{"debounce_s": 0.5, "zones": {"1": 4}}')
    cfg = load_zone_config(path)
    assert cfg.preset_for("1") == 4
    assert cfg.preset_for("2") is None


def test_config_refuses_preset_255(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        ZoneConfig(wide_preset=255)


async def test_back_and_forth_fast_drops_inside_debounce(clock: Clock) -> None:
    # Two talkers trading lines every 0.5 s: only presses at least debounce_s after the last recall move the camera.
    router, cam, _ = make(clock, debounce_s=1.5)
    for zone in (1, 2, 1, 2, 1, 2):
        await router.event(zone)
        clock.t += 0.5
    assert cam.recalled == [1, 2]


async def test_back_and_forth_then_quiet_stays_on_first_talker(clock: Clock) -> None:
    # Documents today's behavior (test plan T2): a debounced zone is dropped, not deferred.
    router, cam, _ = make(clock, debounce_s=1.5)
    await router.event(1)
    clock.t += 1.0
    assert await router.event(2) is Outcome.DEBOUNCED
    clock.t += 10
    assert cam.recalled == [1]
    assert router.current == 1
