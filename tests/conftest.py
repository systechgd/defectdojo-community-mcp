"""Shared fixtures.

Every test runs against an in-process ``httpx.MockTransport``; nothing here
touches a real DefectDojo instance or the network.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from defectdojo_community_mcp.client import DefectDojoClient
from defectdojo_community_mcp.config import Settings

BASE_URL = "https://defectdojo.example.com"


@pytest.fixture
def settings() -> Settings:
    return Settings(url=BASE_URL, api_key="test-token", verify_tls=True, timeout=5.0)


Handler = Callable[[httpx.Request], httpx.Response]


@pytest.fixture
def make_client(settings: Settings) -> Callable[[Handler], DefectDojoClient]:
    def _build(handler: Handler) -> DefectDojoClient:
        return DefectDojoClient(settings, transport=httpx.MockTransport(handler))

    return _build


def json_response(payload: Any, status_code: int = 200) -> httpx.Response:
    return httpx.Response(
        status_code,
        content=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )


def page(results: list[dict], next_url: str | None = None, count: int | None = None) -> dict:
    return {
        "count": len(results) if count is None else count,
        "next": next_url,
        "results": results,
    }


def finding(
    finding_id: int,
    *,
    title: str = "Example vulnerability",
    severity: str = "Critical",
    cve: str | None = None,
    cwe: int | None = None,
    component: str | None = None,
    **extra: Any,
) -> dict:
    payload: dict[str, Any] = {
        "id": finding_id,
        "title": title,
        "severity": severity,
        "component_name": component,
        "cwe": cwe,
        "vulnerability_ids": [{"vulnerability_id": cve}] if cve else [],
    }
    payload.update(extra)
    return payload
