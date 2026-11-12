import pytest
from conftest import fake_camera

from ec20_voice_steer import cli
from ec20_voice_steer.visca import ViscaIP

ACK = bytes.fromhex("0111000300000001") + bytes.fromhex("9041ff")


def test_help_lists_commands(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        cli.main(["--help"])
    out = capsys.readouterr().out
    for name in ("version", "save", "recall", "home", "route"):
        assert name in out


def test_preset_255_is_refused_before_anything_is_sent(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as info:
        cli.main(["--ip", "192.0.2.10", "recall", "255"])
    assert info.value.code == 2
    assert "preset must be 0-254" in capsys.readouterr().err


def test_no_address_exits_2(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["version"]) == 2
    assert "EC20_STEER_IP" in capsys.readouterr().err


@pytest.mark.parametrize(("replies", "code"), [([None, ACK], 0), ([None, None], 1)])
def test_recall_exit_code_follows_reply(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], replies: list[bytes | None], code: int
) -> None:
    holder: dict[str, object] = {}

    async def fake_open(ip: str, port: int, timeout_s: float) -> ViscaIP:
        cam, wire = fake_camera(replies)
        holder["wire"] = wire
        await cam.reset_sequence()
        return cam

    monkeypatch.setattr(ViscaIP, "open", staticmethod(fake_open))
    assert cli.main(["--ip", "192.0.2.10", "recall", "2"]) == code
    assert holder["wire"].closed  # type: ignore[attr-defined]
    assert ("ACK" if code == 0 else "timeout") in capsys.readouterr().out


def record_open(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    opened: list[str] = []

    async def fake_open(ip: str, port: int, timeout_s: float) -> ViscaIP:
        opened.append(ip)
        cam, _ = fake_camera([None, ACK])
        await cam.reset_sequence()
        return cam

    monkeypatch.setattr(ViscaIP, "open", staticmethod(fake_open))
    return opened


@pytest.mark.parametrize(
    ("address", "reason"),
    [
        ("224.0.0.1", "multicast"),
        ("ff02::1", "multicast"),
        ("255.255.255.255", "broadcast"),
        ("0.0.0.0", "unspecified"),
        ("::", "unspecified"),
        ("not-an-address", "not an IP address"),
    ],
)
def test_non_unicast_target_is_refused_before_anything_is_sent(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], address: str, reason: str
) -> None:
    opened = record_open(monkeypatch)
    assert cli.main(["--ip", address, "--allow-public", "recall", "2"]) == 2
    assert opened == []
    assert reason in capsys.readouterr().err


def test_env_target_is_checked_too(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    opened = record_open(monkeypatch)
    monkeypatch.setenv("EC20_STEER_IP", "255.255.255.255")
    assert cli.main(["recall", "2"]) == 2
    assert opened == []
    assert "broadcast" in capsys.readouterr().err


PUBLIC_IP = "192.0.3.10"
"""Just past TEST-NET-1, so `ipaddress` calls it public. ViscaIP.open is faked: nothing is ever sent to it."""


def test_public_target_needs_allow_public(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    opened = record_open(monkeypatch)
    assert cli.main(["--ip", PUBLIC_IP, "recall", "2"]) == 2
    assert opened == []
    assert "--allow-public" in capsys.readouterr().err


def test_public_target_is_allowed_with_the_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    opened = record_open(monkeypatch)
    assert cli.main(["--ip", PUBLIC_IP, "--allow-public", "recall", "2"]) == 0
    assert opened == [PUBLIC_IP]


@pytest.mark.parametrize("address", ["192.0.2.10", "10.0.0.5", "fe80::1"])
def test_private_target_needs_no_flag(monkeypatch: pytest.MonkeyPatch, address: str) -> None:
    opened = record_open(monkeypatch)
    assert cli.main(["--ip", address, "recall", "2"]) == 0
    assert opened == [address]
