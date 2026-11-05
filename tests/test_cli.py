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
