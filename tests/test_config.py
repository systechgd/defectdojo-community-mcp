from __future__ import annotations

import pytest

from defectdojo_community_mcp.config import ConfigError, Settings, load_settings


def test_loads_from_mapping():
    settings = load_settings(
        {"DEFECTDOJO_URL": "https://dd.example.com", "DEFECTDOJO_API_KEY": "abc123"}
    )
    assert settings.url == "https://dd.example.com"
    assert settings.api_key == "abc123"
    assert settings.verify_tls is True
    assert settings.api_base == "https://dd.example.com/api/v2"


def test_strips_trailing_slash():
    settings = load_settings(
        {"DEFECTDOJO_URL": "https://dd.example.com/", "DEFECTDOJO_API_KEY": "k"}
    )
    assert settings.url == "https://dd.example.com"
    assert settings.api_base == "https://dd.example.com/api/v2"


@pytest.mark.parametrize(
    "env",
    [
        {},
        {"DEFECTDOJO_URL": "https://dd.example.com"},
        {"DEFECTDOJO_API_KEY": "k"},
        {"DEFECTDOJO_URL": "  ", "DEFECTDOJO_API_KEY": "k"},
    ],
)
def test_missing_required_values_raise(env):
    with pytest.raises(ConfigError) as excinfo:
        load_settings(env)
    # The message must name what to set; this is the only diagnostic a
    # misconfigured MCP user gets.
    assert "DEFECTDOJO_" in str(excinfo.value)


def test_rejects_url_without_scheme():
    with pytest.raises(ConfigError, match="http"):
        load_settings({"DEFECTDOJO_URL": "dd.example.com", "DEFECTDOJO_API_KEY": "k"})


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("false", False), ("FALSE", False), ("0", False), ("no", False), ("off", False),
     ("true", True), ("", True), ("anything-else", True)],
)
def test_verify_tls_parsing(raw, expected):
    settings = load_settings(
        {
            "DEFECTDOJO_URL": "https://dd.example.com",
            "DEFECTDOJO_API_KEY": "k",
            "DEFECTDOJO_VERIFY_TLS": raw,
        }
    )
    assert settings.verify_tls is expected


def test_invalid_timeout_rejected():
    with pytest.raises(ConfigError, match="must be a number"):
        load_settings(
            {
                "DEFECTDOJO_URL": "https://dd.example.com",
                "DEFECTDOJO_API_KEY": "k",
                "DEFECTDOJO_TIMEOUT_SECONDS": "soon",
            }
        )


def test_repr_does_not_leak_the_token():
    settings = Settings(url="https://dd.example.com", api_key="super-secret-token")
    assert "super-secret-token" not in repr(settings)


def test_auth_header_format():
    settings = Settings(url="https://dd.example.com", api_key="k")
    assert settings.auth_headers()["Authorization"] == "Token k"
