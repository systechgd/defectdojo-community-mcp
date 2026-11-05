from __future__ import annotations

import httpx
import pytest

from conftest import json_response, page


def test_sends_token_auth_header(make_client):
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return json_response(page([]))

    make_client(handler).get_all("/products/")
    assert seen[0].headers["Authorization"] == "Token test-token"
    assert seen[0].headers["Accept"] == "application/json"


def test_requests_hit_the_api_v2_base_path(make_client):
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return json_response(page([]))

    make_client(handler).get_all("/products/")
    assert seen[0].startswith("https://defectdojo.example.com/api/v2/products/")


def test_pagination_follows_next_and_advances_offset(make_client):
    offsets: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        offset = request.url.params.get("offset")
        offsets.append(offset)
        if offset == "0":
            return json_response(page([{"id": 1}], next_url="?offset=100", count=2))
        return json_response(page([{"id": 2}], next_url=None, count=2))

    results = make_client(handler).get_all("/findings/")

    assert [r["id"] for r in results] == [1, 2]
    assert offsets == ["0", "100"]


def test_pagination_stops_when_next_is_null(make_client):
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return json_response(page([{"id": 1}], next_url=None))

    make_client(handler).get_all("/findings/")
    assert calls["n"] == 1


def test_http_error_propagates(make_client):
    def handler(request: httpx.Request) -> httpx.Response:
        return json_response({"detail": "Invalid token."}, status_code=401)

    with pytest.raises(httpx.HTTPStatusError):
        make_client(handler).get_all("/products/")


def test_products_by_id_maps_id_to_name(make_client):
    def handler(request: httpx.Request) -> httpx.Response:
        return json_response(page([{"id": 1, "name": "svc-a"}, {"id": 2, "name": "svc-b"}]))

    assert make_client(handler).products_by_id() == {1: "svc-a", 2: "svc-b"}


def test_iter_all_is_lazy(make_client):
    """The generator must not fire a request until it is consumed."""
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return json_response(page([{"id": 1}]))

    iterator = make_client(handler).iter_all("/products/")
    assert calls["n"] == 0
    next(iterator)
    assert calls["n"] == 1
