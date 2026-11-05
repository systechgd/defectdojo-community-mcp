from __future__ import annotations

import pytest

from defectdojo_community_mcp.transform import (
    MITIGATION_MAX_CHARS,
    condense,
    group_by_vulnerability,
    normalize_severity,
    vulnerability_ids,
    vulnerability_key,
)

BASE = "https://dd.example.com"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("critical", "Critical"), ("CRITICAL", "Critical"), ("Info", "Info"), (" high ", "High")],
)
def test_normalize_severity(raw, expected):
    assert normalize_severity(raw) == expected


@pytest.mark.parametrize("raw", ["", "   ", "catastrophic"])
def test_normalize_severity_rejects_unknown(raw):
    with pytest.raises(ValueError):
        normalize_severity(raw)


def test_vulnerability_ids_prefers_modern_field():
    f = {"vulnerability_ids": [{"vulnerability_id": "CVE-2024-1"}], "cve": "CVE-2000-9"}
    assert vulnerability_ids(f) == ["CVE-2024-1"]


def test_vulnerability_ids_falls_back_to_legacy_cve():
    assert vulnerability_ids({"vulnerability_ids": [], "cve": "CVE-2000-9"}) == ["CVE-2000-9"]


def test_vulnerability_ids_empty_when_absent():
    assert vulnerability_ids({}) == []


def test_condense_builds_finding_url_and_trims_mitigation():
    out = condense(
        {"id": 42, "title": "x", "mitigation": "y" * (MITIGATION_MAX_CHARS + 500)},
        "my-product",
        BASE,
    )
    assert out["url"] == f"{BASE}/finding/42"
    assert out["product"] == "my-product"
    assert len(out["mitigation"]) == MITIGATION_MAX_CHARS


def test_condense_handles_null_mitigation():
    assert condense({"id": 1, "mitigation": None}, "p", BASE)["mitigation"] == ""


def test_vulnerability_key_prefers_cve():
    assert vulnerability_key({"cve": ["CVE-2024-1"], "cwe": 79, "title": "t"}) == "CVE-2024-1"


def test_vulnerability_key_falls_back_to_cwe_and_title():
    assert vulnerability_key({"cve": [], "cwe": 79, "title": "XSS"}) == "CWE-79:XSS"


def test_vulnerability_key_falls_back_to_title():
    assert vulnerability_key({"cve": [], "cwe": None, "title": "Odd one"}) == "Odd one"


def test_group_by_vulnerability_merges_same_cve_across_products():
    findings = [
        condense(
            {
                "id": 1,
                "title": "a",
                "severity": "Critical",
                "vulnerability_ids": [{"vulnerability_id": "CVE-2024-1"}],
            },
            "svc-a",
            BASE,
        ),
        condense(
            {
                "id": 2,
                "title": "a",
                "severity": "Critical",
                "vulnerability_ids": [{"vulnerability_id": "CVE-2024-1"}],
            },
            "svc-b",
            BASE,
        ),
        condense(
            {
                "id": 3,
                "title": "b",
                "severity": "Critical",
                "vulnerability_ids": [{"vulnerability_id": "CVE-2024-2"}],
            },
            "svc-a",
            BASE,
        ),
    ]

    groups = group_by_vulnerability(findings)

    assert [g["vuln"] for g in groups] == ["CVE-2024-1", "CVE-2024-2"]
    assert groups[0]["products"] == ["svc-a", "svc-b"]
    assert groups[0]["affected_product_count"] == 2
    assert len(groups[0]["findings"]) == 2
    assert groups[1]["affected_product_count"] == 1


def test_group_by_vulnerability_dedupes_products_within_a_group():
    findings = [
        condense(
            {
                "id": i,
                "title": "a",
                "severity": "Critical",
                "vulnerability_ids": [{"vulnerability_id": "CVE-2024-1"}],
            },
            "svc-a",
            BASE,
        )
        for i in (1, 2, 3)
    ]
    group = group_by_vulnerability(findings)[0]
    assert group["products"] == ["svc-a"]
    assert group["affected_product_count"] == 1
    # Every finding is still listed even though the product collapses to one.
    assert len(group["findings"]) == 3


def test_group_by_vulnerability_is_deterministic_for_equal_counts():
    findings = [
        condense(
            {
                "id": 1,
                "title": "b",
                "severity": "Critical",
                "vulnerability_ids": [{"vulnerability_id": "CVE-2024-2"}],
            },
            "svc",
            BASE,
        ),
        condense(
            {
                "id": 2,
                "title": "a",
                "severity": "Critical",
                "vulnerability_ids": [{"vulnerability_id": "CVE-2024-1"}],
            },
            "svc",
            BASE,
        ),
    ]
    assert [g["vuln"] for g in group_by_vulnerability(findings)] == ["CVE-2024-1", "CVE-2024-2"]


def test_group_by_vulnerability_empty_input():
    assert group_by_vulnerability([]) == []
