"""The one place ec20-voice-steer reads configuration. Values come from EC20_STEER_* variables or `.env`."""

from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from ec20_voice_steer.visca import PORT

ENV_PREFIX = "EC20_STEER_"


class Settings(BaseSettings):
    """Where the bench EC20 is. The address has no default on purpose: never guess which camera to move."""

    model_config = SettingsConfigDict(env_prefix=ENV_PREFIX, env_file=".env", extra="ignore", frozen=True)

    ip: str | None = None
    port: int = Field(default=PORT, ge=1, le=65535)
    timeout_s: float = Field(default=1.0, gt=0, le=10)


class SettingsError(Exception):
    """Settings are invalid. Carries variable names only, never the values."""

    def __init__(self, variables: list[str], reasons: list[str]) -> None:
        self.variables = variables
        lines = [f"  {name}: {reason}" for name, reason in zip(variables, reasons, strict=True)]
        super().__init__("ec20-voice-steer settings are invalid (set them in .env):\n" + "\n".join(lines))


def load_settings() -> Settings:
    """Load Settings, turning a validation error into a SettingsError that names the EC20_STEER_ variables."""
    try:
        return Settings()
    except ValidationError as exc:
        variables: list[str] = []
        reasons: list[str] = []
        for error in exc.errors(include_input=False, include_url=False):
            field = str(error["loc"][0]) if error["loc"] else "?"
            variables.append(ENV_PREFIX + field.upper())
            reasons.append(error["msg"])
        raise SettingsError(variables, reasons) from None
