"""Configuration, loaded from the environment.

Deliberately lazy: importing this module never reads the environment and never
raises. Configuration is resolved when ``load_settings()`` is called, which is
what lets the test suite import the package without a live DefectDojo instance
and what lets ``--version`` work on a machine that has no token.
"""

from __future__ import annotations

import contextlib
import os
from collections.abc import Mapping
from dataclasses import dataclass

DEFAULT_TIMEOUT_SECONDS = 30.0

ENV_URL = "DEFECTDOJO_URL"
ENV_API_KEY = "DEFECTDOJO_API_KEY"
ENV_VERIFY_TLS = "DEFECTDOJO_VERIFY_TLS"
ENV_TIMEOUT = "DEFECTDOJO_TIMEOUT_SECONDS"


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or malformed."""


@dataclass(frozen=True)
class Settings:
    """Resolved server configuration."""

    url: str
    api_key: str
    verify_tls: bool = True
    timeout: float = DEFAULT_TIMEOUT_SECONDS

    @property
    def api_base(self) -> str:
        return f"{self.url}/api/v2"

    def finding_url(self, finding_id: object) -> str:
        """The human-facing DefectDojo URL for a finding."""
        return f"{self.url}/finding/{finding_id}"

    def auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Token {self.api_key}", "Accept": "application/json"}

    def __repr__(self) -> str:  # pragma: no cover - trivial
        # Never let the token reach a log line or a traceback.
        return (
            f"Settings(url={self.url!r}, api_key='***', "
            f"verify_tls={self.verify_tls!r}, timeout={self.timeout!r})"
        )


def load_dotenv_if_present(path: str | None = None) -> None:
    """Best-effort load of a local .env, so the token need not live in client config.

    python-dotenv is a declared dependency, but a missing or unreadable .env is
    not an error: the environment may well be populated by the MCP client.
    """
    try:
        from dotenv import load_dotenv
    except ImportError:  # pragma: no cover - dependency is declared
        return
    if path is None:
        path = os.path.join(os.getcwd(), ".env")
    with contextlib.suppress(OSError):  # pragma: no cover - defensive
        load_dotenv(path)


def _parse_bool(raw: str | None, *, default: bool) -> bool:
    if raw is None or raw == "":
        return default
    return raw.strip().lower() not in {"false", "0", "no", "off"}


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    """Build :class:`Settings` from a mapping (defaults to ``os.environ``).

    Raises :class:`ConfigError` with actionable text when required values are
    absent — this surfaces in the MCP client's logs, where a bare KeyError
    would be close to undiagnosable.
    """
    source: Mapping[str, str] = os.environ if env is None else env

    url = (source.get(ENV_URL) or "").strip().rstrip("/")
    api_key = (source.get(ENV_API_KEY) or "").strip()

    missing = [name for name, value in ((ENV_URL, url), (ENV_API_KEY, api_key)) if not value]
    if missing:
        raise ConfigError(
            f"{' and '.join(missing)} must be set. Export them in your shell or MCP "
            "client config, or copy .env.example to .env in the working directory. "
            "See README.md for setup."
        )

    if not url.startswith(("http://", "https://")):
        raise ConfigError(f"{ENV_URL} must start with http:// or https:// (got {url!r}).")

    raw_timeout = source.get(ENV_TIMEOUT)
    if raw_timeout:
        try:
            timeout = float(raw_timeout)
        except ValueError as exc:
            raise ConfigError(f"{ENV_TIMEOUT} must be a number (got {raw_timeout!r}).") from exc
        if timeout <= 0:
            raise ConfigError(f"{ENV_TIMEOUT} must be greater than 0 (got {timeout!r}).")
    else:
        timeout = DEFAULT_TIMEOUT_SECONDS

    return Settings(
        url=url,
        api_key=api_key,
        verify_tls=_parse_bool(source.get(ENV_VERIFY_TLS), default=True),
        timeout=timeout,
    )
