"""
DefectDojo MCP server (read-only).

Exposes a DefectDojo instance's findings over the Model Context Protocol, so an
AI agent can triage critical and duplicate findings across every product and
summarise them into well-formed issues for whatever tracker you use.

Read-only by design: no tool here issues a POST, PUT, PATCH or DELETE, so it
cannot mutate DefectDojo. Configuration comes entirely from the environment:

    DEFECTDOJO_URL         base URL, e.g. https://defectdojo.example.com
    DEFECTDOJO_API_KEY     a DefectDojo API v2 token (never hard-code this)
    DEFECTDOJO_VERIFY_TLS  set to "false" to skip TLS verification (discouraged;
                           see SECURITY.md)

A "product" is whatever unit your scanners import under. CI pipelines commonly
import one product per source repository, so product names often match repo
names — but this server makes no assumption about that.
"""

from __future__ import annotations

import os
from typing import Any, Optional

import httpx
from mcp.server.fastmcp import FastMCP

# Load a local .env (next to this file) so the token need not live in the MCP client config.
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
except Exception:
    pass

DD_URL = os.environ.get("DEFECTDOJO_URL", "").rstrip("/")
DD_KEY = os.environ.get("DEFECTDOJO_API_KEY", "")
VERIFY_TLS = os.environ.get("DEFECTDOJO_VERIFY_TLS", "true").lower() != "false"

if not DD_URL or not DD_KEY:
    # Fail loudly at startup so misconfiguration is obvious in the MCP logs.
    raise RuntimeError(
        "DEFECTDOJO_URL and DEFECTDOJO_API_KEY must both be set. Export them in "
        "your shell or MCP client config, or copy .env.example to .env next to "
        "server.py. See README.md for setup."
    )

mcp = FastMCP("defectdojo")

_HEADERS = {"Authorization": f"Token {DD_KEY}", "Accept": "application/json"}

# Filters that define an "actionable" finding: real, open, not silenced.
_ACTIONABLE = {
    "active": "true",
    "false_p": "false",
    "duplicate": "false",
    "risk_accepted": "false",
    "out_of_scope": "false",
    "is_mitigated": "false",
}


def _client() -> httpx.Client:
    return httpx.Client(base_url=f"{DD_URL}/api/v2", headers=_HEADERS, timeout=30.0, verify=VERIFY_TLS)


def _get_all(path: str, params: dict[str, Any]) -> list[dict]:
    """GET a DefectDojo list endpoint, following pagination."""
    out: list[dict] = []
    params = {**params, "limit": 100, "offset": 0}
    with _client() as c:
        while True:
            r = c.get(path, params=params)
            r.raise_for_status()
            data = r.json()
            out.extend(data.get("results", []))
            if not data.get("next"):
                break
            params["offset"] += params["limit"]
    return out


def _products_by_id() -> dict[int, str]:
    return {p["id"]: p["name"] for p in _get_all("/products/", {})}


def _condense(f: dict, product_name: str) -> dict:
    """Trim a raw finding to the fields useful for triage + issue creation."""
    vuln_ids = [v.get("vulnerability_id") for v in (f.get("vulnerability_ids") or []) if v.get("vulnerability_id")]
    return {
        "id": f["id"],
        "title": f.get("title"),
        "severity": f.get("severity"),
        "product": product_name,
        "cve": vuln_ids or ([f["cve"]] if f.get("cve") else []),
        "cwe": f.get("cwe"),
        "component": f.get("component_name"),
        "component_version": f.get("component_version"),
        "file_path": f.get("file_path"),
        "line": f.get("line"),
        "found_by": f.get("found_by"),  # scanner test type ids
        "duplicate": f.get("duplicate"),
        "mitigation": (f.get("mitigation") or "")[:800],
        "url": f"{DD_URL}/finding/{f['id']}",
    }


def _vuln_key(f: dict) -> str:
    """A stable grouping key so the same vuln across products becomes ONE issue."""
    if f["cve"]:
        return f["cve"][0]
    if f.get("cwe"):
        return f"CWE-{f['cwe']}:{(f.get('title') or '').strip()}"
    return (f.get("title") or "").strip()


def _fetch_findings(severity: str, product_name: Optional[str], include_duplicates: bool) -> list[dict]:
    prods = _products_by_id()
    name_to_id = {n.lower(): i for i, n in prods.items()}
    filters = dict(_ACTIONABLE)
    if include_duplicates:
        filters.pop("duplicate")
    filters["severity"] = severity

    targets: list[tuple[int, str]]
    if product_name:
        pid = name_to_id.get(product_name.lower())
        if pid is None:
            return []
        targets = [(pid, prods[pid])]
    else:
        targets = list(prods.items())

    results: list[dict] = []
    for pid, pname in targets:
        raw = _get_all("/findings/", {**filters, "test__engagement__product": pid})
        results.extend(_condense(f, pname) for f in raw)
    return results


# ─────────────────────────────── MCP tools ───────────────────────────────

@mcp.tool()
def health_check() -> dict:
    """Verify connectivity + auth to DefectDojo. Returns the DD version/product count."""
    with _client() as c:
        r = c.get("/products/", params={"limit": 1})
        r.raise_for_status()
        return {"ok": True, "url": DD_URL, "product_count": r.json().get("count")}


@mcp.tool()
def list_products() -> list[dict]:
    """List all DefectDojo products (each product == a repo/service)."""
    return [{"id": p["id"], "name": p["name"], "findings": p.get("findings_count")}
            for p in _get_all("/products/", {})]


@mcp.tool()
def list_critical_findings(product: Optional[str] = None, include_duplicates: bool = False) -> list[dict]:
    """
    List actionable CRITICAL findings (active, not false-positive/risk-accepted/mitigated).
    Optionally scope to one product (repo name). Set include_duplicates=True to also see dupes.
    """
    return _fetch_findings("Critical", product, include_duplicates)


@mcp.tool()
def list_findings_by_severity(severity: str, product: Optional[str] = None,
                              include_duplicates: bool = False) -> list[dict]:
    """List actionable findings of a given severity (Critical|High|Medium|Low|Info)."""
    sev = severity.capitalize()
    return _fetch_findings(sev, product, include_duplicates)


@mcp.tool()
def group_critical_by_vuln() -> list[dict]:
    """
    Group all actionable CRITICAL findings across every product by unique vulnerability
    (CVE, else CWE+title). Useful for filing ONE tracker issue per vulnerability that
    lists every affected product. Returns [{vuln, severity, cve, cwe, title, products, findings}].
    """
    findings = _fetch_findings("Critical", None, include_duplicates=False)
    groups: dict[str, dict] = {}
    for f in findings:
        k = _vuln_key(f)
        g = groups.setdefault(k, {
            "vuln": k, "severity": f["severity"], "cve": f["cve"],
            "cwe": f.get("cwe"), "title": f.get("title"),
            "products": set(), "findings": [],
        })
        g["products"].add(f["product"])
        g["findings"].append({"id": f["id"], "product": f["product"], "url": f["url"],
                              "component": f["component"], "file_path": f["file_path"]})
    result = []
    for g in groups.values():
        g["products"] = sorted(g["products"])
        g["affected_product_count"] = len(g["products"])
        result.append(g)
    result.sort(key=lambda x: x["affected_product_count"], reverse=True)
    return result


@mcp.tool()
def list_duplicate_findings(product: Optional[str] = None) -> list[dict]:
    """List findings DefectDojo has marked as duplicates (optionally scoped to one product)."""
    prods = _products_by_id()
    name_to_id = {n.lower(): i for i, n in prods.items()}
    filters = {"duplicate": "true", "active": "true"}
    if product:
        pid = name_to_id.get(product.lower())
        if pid is None:
            return []
        raw = _get_all("/findings/", {**filters, "test__engagement__product": pid})
        return [_condense(f, prods[pid]) for f in raw]
    out = []
    for pid, pname in prods.items():
        raw = _get_all("/findings/", {**filters, "test__engagement__product": pid})
        out.extend(_condense(f, pname) for f in raw)
    return out


@mcp.tool()
def get_finding(finding_id: int) -> dict:
    """Full detail for one finding: description, mitigation, references, CWE/CVE, location."""
    with _client() as c:
        r = c.get(f"/findings/{finding_id}/")
        r.raise_for_status()
        f = r.json()
    f["url"] = f"{DD_URL}/finding/{finding_id}"
    return f


if __name__ == "__main__":
    mcp.run()
