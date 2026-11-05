from __future__ import annotations

import httpx
import pytest

from conftest import finding, json_response, page
from defectdojo_community_mcp import server


@pytest.fixture(autouse=True)
def _reset_client():
    yield
    server.configure(None)  # type: ignore[arg-type]


def install(make_client, handler) -> None:
    server.configure(make_client(handler))


PRODUCTS = page([{"id": 1, "name": "svc-a"}, {"id": 2, "name": "svc-b"}])


def test_health_check_reports_product_count(make_client):
    def handler(request: httpx.Request) -> httpx.Response:
        return json_response({"count": 7, "results": []})

    install(make_client, handler)
    result = server.health_check()
    assert result["ok"] is True
    assert result["product_count"] == 7
    assert result["url"] == "https://defectdojo.example.com"


def test_list_products(make_client):
    def handler(request: httpx.Request) -> httpx.Response:
        return json_response(page([{"id": 1, "name": "svc-a", "findings_count": 3}]))

    install(make_client, handler)
    assert server.list_products() == [{"id": 1, "name": "svc-a", "findings": 3}]


def test_actionable_filters_are_applied(make_client):
    """Findings queries must exclude false positives, dupes and mitigated items."""
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/products/"):
            return json_response(PRODUCTS)
        captured.update(dict(request.url.params))
        return json_response(page([]))

    install(make_client, handler)
    server.list_critical_findings()

    assert captured["active"] == "true"
    assert captured["false_p"] == "false"
    assert captured["duplicate"] == "false"
    assert captured["risk_accepted"] == "false"
    assert captured["is_mitigated"] == "false"
    assert captured["severity"] == "Critical"


def test_include_duplicates_drops_the_duplicate_filter(make_client):
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/products/"):
            return json_response(PRODUCTS)
        captured.update(dict(request.url.params))
        return json_response(page([]))

    install(make_client, handler)
    server.list_critical_findings(include_duplicates=True)
    assert "duplicate" not in captured


def test_product_filter_is_case_insensitive(make_client):
    seen_product_ids: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/products/"):
            return json_response(PRODUCTS)
        seen_product_ids.append(request.url.params["test__engagement__product"])
        return json_response(page([]))

    install(make_client, handler)
    server.list_critical_findings(product="SVC-A")
    assert seen_product_ids == ["1"]


def test_unknown_product_returns_empty_without_querying_findings(make_client):
    findings_calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/products/"):
            return json_response(PRODUCTS)
        findings_calls["n"] += 1
        return json_response(page([]))

    install(make_client, handler)
    assert server.list_critical_findings(product="does-not-exist") == []
    assert findings_calls["n"] == 0


def test_findings_are_condensed_and_tagged_with_product(make_client):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/products/"):
            return json_response(page([{"id": 1, "name": "svc-a"}]))
        return json_response(page([finding(10, cve="CVE-2024-1", component="lib")]))

    install(make_client, handler)
    results = server.list_critical_findings()

    assert len(results) == 1
    assert results[0]["id"] == 10
    assert results[0]["product"] == "svc-a"
    assert results[0]["cve"] == ["CVE-2024-1"]
    assert results[0]["url"] == "https://defectdojo.example.com/finding/10"


def test_group_critical_by_vuln_spans_products(make_client):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/products/"):
            return json_response(PRODUCTS)
        product_id = request.url.params["test__engagement__product"]
        return json_response(page([finding(int(product_id), cve="CVE-2024-1")]))

    install(make_client, handler)
    groups = server.group_critical_by_vuln()

    assert len(groups) == 1
    assert groups[0]["vuln"] == "CVE-2024-1"
    assert groups[0]["products"] == ["svc-a", "svc-b"]


def test_list_findings_by_severity_normalizes_case(make_client):
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/products/"):
            return json_response(page([{"id": 1, "name": "svc-a"}]))
        captured.update(dict(request.url.params))
        return json_response(page([]))

    install(make_client, handler)
    server.list_findings_by_severity("high")
    assert captured["severity"] == "High"


def test_list_findings_by_severity_rejects_nonsense(make_client):
    def handler(request: httpx.Request) -> httpx.Response:
        return json_response(page([]))

    install(make_client, handler)
    with pytest.raises(ValueError):
        server.list_findings_by_severity("catastrophic")


def test_list_duplicate_findings_filters_on_duplicate_true(make_client):
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/products/"):
            return json_response(page([{"id": 1, "name": "svc-a"}]))
        captured.update(dict(request.url.params))
        return json_response(page([]))

    install(make_client, handler)
    server.list_duplicate_findings()
    assert captured["duplicate"] == "true"


def test_get_finding_attaches_url(make_client):
    def handler(request: httpx.Request) -> httpx.Response:
        return json_response({"id": 99, "title": "x"})

    install(make_client, handler)
    assert server.get_finding(99)["url"] == "https://defectdojo.example.com/finding/99"


def test_every_request_is_a_read(make_client):
    """The read-only guarantee, asserted rather than assumed."""
    methods: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        methods.append(request.method)
        if request.url.path.endswith("/products/"):
            return json_response(PRODUCTS)
        return json_response(page([finding(1, cve="CVE-2024-1")]))

    install(make_client, handler)
    server.health_check()
    server.list_products()
    server.list_critical_findings()
    server.list_findings_by_severity("Medium")
    server.group_critical_by_vuln()
    server.list_duplicate_findings()
    server.get_finding(1)

    assert methods, "expected at least one request"
    assert set(methods) == {"GET"}
