"""Thin read-only HTTP client for the DefectDojo API v2.

Read-only is enforced structurally, not by convention: this class exposes no
method that can issue a POST, PUT, PATCH or DELETE. Adding one would be a
breaking change to the project's stated security model (see SECURITY.md).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import httpx

from .config import Settings

PAGE_SIZE = 100

# A hard stop so a malformed ``next`` link cannot spin forever against a live
# instance. 1000 pages at 100 per page is far beyond any realistic triage run.
MAX_PAGES = 1000


class DefectDojoClient:
    """Paginating, read-only client.

    ``transport`` exists so tests can inject ``httpx.MockTransport``; production
    callers leave it as ``None``.
    """

    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None) -> None:
        self._settings = settings
        self._transport = transport

    @property
    def settings(self) -> Settings:
        return self._settings

    def _open(self) -> httpx.Client:
        kwargs: dict[str, Any] = {
            "base_url": self._settings.api_base,
            "headers": self._settings.auth_headers(),
            "timeout": self._settings.timeout,
        }
        if self._transport is None:
            # verify= and a custom transport are mutually exclusive in httpx.
            kwargs["verify"] = self._settings.verify_tls
        else:
            kwargs["transport"] = self._transport
        return httpx.Client(**kwargs)

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict:
        """GET a single DefectDojo object."""
        with self._open() as client:
            response = client.get(path, params=params or {})
            response.raise_for_status()
            return response.json()

    def iter_all(self, path: str, params: dict[str, Any] | None = None) -> Iterator[dict]:
        """Yield every result from a list endpoint, following pagination."""
        query: dict[str, Any] = {**(params or {}), "limit": PAGE_SIZE, "offset": 0}
        pages = 0
        with self._open() as client:
            while True:
                response = client.get(path, params=query)
                response.raise_for_status()
                payload = response.json()
                yield from payload.get("results", [])

                pages += 1
                if not payload.get("next") or pages >= MAX_PAGES:
                    break
                query["offset"] += PAGE_SIZE

    def get_all(self, path: str, params: dict[str, Any] | None = None) -> list[dict]:
        """Eager form of :meth:`iter_all`."""
        return list(self.iter_all(path, params))

    def products_by_id(self) -> dict[int, str]:
        return {p["id"]: p["name"] for p in self.iter_all("/products/")}
