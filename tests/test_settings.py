from pathlib import Path

import pytest
from conftest import FAKE_IP

from ec20_voice_steer.settings import SettingsError, load_settings


def test_defaults_have_no_camera_address() -> None:
    settings = load_settings()
    assert settings.ip is None
    assert settings.port == 52381


def test_reads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EC20_STEER_IP", FAKE_IP)
    monkeypatch.setenv("EC20_STEER_TIMEOUT_S", "2.5")
    settings = load_settings()
    assert settings.ip == FAKE_IP
    assert settings.timeout_s == 2.5


def test_reads_dotenv_in_working_directory(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text(f"EC20_STEER_IP={FAKE_IP}\n")
    assert load_settings().ip == FAKE_IP


def test_bad_port_names_the_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EC20_STEER_PORT", "70000")
    with pytest.raises(SettingsError) as info:
        load_settings()
    assert info.value.variables == ["EC20_STEER_PORT"]
    assert "70000" not in str(info.value)
