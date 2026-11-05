"""Pure transforms over DefectDojo payloads.

Everything here is a plain function of its arguments with no I/O, which is what
makes the interesting logic — grouping the same vulnerability across products —
testable without a DefectDojo instance.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

MITIGATION_MAX_CHARS = 800

SEVERITIES = ("Critical", "High", "Medium", "Low", "Info")

# Filters describing an "actionable" finding: real, open, and not silenced.
ACTIONABLE_FILTERS: dict[str, str] = {
    "active": "true",
    "false_p": "false",
    "duplicate": "false",
    "risk_accepted": "false",
    "out_of_scope": "false",
    "is_mitigated": "false",
}


def normalize_severity(severity: str) -> str:
    """Map user input to DefectDojo's exact casing.

    DefectDojo's severity filter is case-sensitive, so ``critical`` silently
    returns nothing rather than erroring. Raising here turns a confusing empty
    result into a clear message.
    """
    if not severity or not severity.strip():
        raise ValueError(f"severity is required; one of {', '.join(SEVERITIES)}")

    candidate = severity.strip().lower()
    for known in SEVERITIES:
        if known.lower() == candidate:
            return known
    raise ValueError(
        f"unknown severity {severity!r}; expected one of {', '.join(SEVERITIES)}"
    )


def vulnerability_ids(finding: dict) -> list[str]:
    """CVE-style identifiers, preferring the modern field over the legacy one."""
    ids = [
        entry.get("vulnerability_id")
        for entry in (finding.get("vulnerability_ids") or [])
        if entry.get("vulnerability_id")
    ]
    if ids:
        return ids
    legacy = finding.get("cve")
    return [legacy] if legacy else []


def condense(finding: dict, product_name: str | None, base_url: str) -> dict:
    """Trim a raw finding to the fields useful for triage and issue creation."""
    mitigation = finding.get("mitigation") or ""
    return {
        "id": finding["id"],
        "title": finding.get("title"),
        "severity": finding.get("severity"),
        "product": product_name,
        "cve": vulnerability_ids(finding),
        "cwe": finding.get("cwe"),
        "component": finding.get("component_name"),
        "component_version": finding.get("component_version"),
        "file_path": finding.get("file_path"),
        "line": finding.get("line"),
        "found_by": finding.get("found_by"),
        "duplicate": finding.get("duplicate"),
        "mitigation": mitigation[:MITIGATION_MAX_CHARS],
        "url": f"{base_url}/finding/{finding['id']}",
    }


def vulnerability_key(condensed: dict) -> str:
    """A stable grouping key, so one vulnerability across products is one group.

    Prefers a CVE; falls back to CWE plus title; finally the title alone.
    """
    cves = condensed.get("cve") or []
    if cves:
        return cves[0]
    title = (condensed.get("title") or "").strip()
    cwe = condensed.get("cwe")
    if cwe:
        return f"CWE-{cwe}:{title}"
    return title


def group_by_vulnerability(findings: Iterable[dict]) -> list[dict]:
    """Group condensed findings by vulnerability, widest blast radius first."""
    groups: dict[str, dict[str, Any]] = {}

    for finding in findings:
        key = vulnerability_key(finding)
        group = groups.get(key)
        if group is None:
            group = {
                "vuln": key,
                "severity": finding.get("severity"),
                "cve": finding.get("cve"),
                "cwe": finding.get("cwe"),
                "title": finding.get("title"),
                "products": set(),
                "findings": [],
            }
            groups[key] = group

        if finding.get("product") is not None:
            group["products"].add(finding["product"])
        group["findings"].append(
            {
                "id": finding.get("id"),
                "product": finding.get("product"),
                "url": finding.get("url"),
                "component": finding.get("component"),
                "file_path": finding.get("file_path"),
            }
        )

    result = []
    for group in groups.values():
        group["products"] = sorted(group["products"])
        group["affected_product_count"] = len(group["products"])
        result.append(group)

    # Sort by blast radius, then by key so the order is deterministic for equal counts.
    result.sort(key=lambda g: (-g["affected_product_count"], g["vuln"]))
    return result
