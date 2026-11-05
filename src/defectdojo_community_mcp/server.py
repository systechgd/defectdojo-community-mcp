"""MCP tool definitions for DefectDojo Community Edition.

Read-only by design: every tool below performs GET requests only, and the
client class underneath exposes no mutating method.

A "product" is whatever unit your scanners import under. CI pipelines commonly
import one product per source repository, so product names often match repo
names — but this server makes no assumption about that.
"""

from __future__ import annotations

import argparse

try:
    # mcp >= 2.0 renamed FastMCP to MCPServer. The tool() decorator and run()
    # signatures are compatible, so both SDK generations are supported rather
    # than pinning users to an old one.
    from mcp.server.mcpserver import MCPServer as _Server
except ImportError:  # pragma: no cover - depends on installed SDK version
    from mcp.server.fastmcp import FastMCP as _Server

from . import __version__
from .client import DefectDojoClient
from .config import ConfigError, Settings, load_dotenv_if_present, load_settings
from .transform import (
    ACTIONABLE_FILTERS,
    condense,
    group_by_vulnerability,
    normalize_severity,
)

SERVER_NAME = "defectdojo-community"

mcp = _Server(SERVER_NAME)

_client: DefectDojoClient | None = None


def configure(client: DefectDojoClient) -> None:
    """Install the client the tools use. Called at startup, and by tests."""
    global _client
    _client = client


def get_client() -> DefectDojoClient:
    """Return the configured client, building one from the environment if needed.

    Resolving lazily (rather than at import) keeps the module importable without
    a token, which is what allows ``--version``, ``--help`` and the test suite
    to run on a machine with no DefectDojo instance.
    """
    global _client
    if _client is None:
        load_dotenv_if_present()
        _client = DefectDojoClient(load_settings())
    return _client


def _settings() -> Settings:
    return get_client().settings


def _resolve_product_id(products: dict[int, str], product: str) -> int | None:
    lookup = {name.lower(): pid for pid, name in products.items()}
    return lookup.get(product.strip().lower())


def _fetch_findings(
    severity: str,
    product: str | None,
    include_duplicates: bool,
) -> list[dict]:
    client = get_client()
    base_url = client.settings.url
    products = client.products_by_id()

    filters = dict(ACTIONABLE_FILTERS)
    if include_duplicates:
        filters.pop("duplicate", None)
    filters["severity"] = severity

    if product:
        product_id = _resolve_product_id(products, product)
        if product_id is None:
            return []
        targets = [(product_id, products[product_id])]
    else:
        targets = list(products.items())

    results: list[dict] = []
    for product_id, product_name in targets:
        raw = client.get_all(
            "/findings/", {**filters, "test__engagement__product": product_id}
        )
        results.extend(condense(f, product_name, base_url) for f in raw)
    return results


# ───────────────────────────────── MCP tools ─────────────────────────────────


@mcp.tool()
def health_check() -> dict:
    """Verify connectivity and auth to DefectDojo. Returns the instance URL and product count."""
    client = get_client()
    payload = client.get("/products/", {"limit": 1})
    return {
        "ok": True,
        "url": client.settings.url,
        "product_count": payload.get("count"),
        "server_version": __version__,
    }


@mcp.tool()
def list_products() -> list[dict]:
    """List all DefectDojo products (each product is typically one repo or service)."""
    return [
        {"id": p["id"], "name": p["name"], "findings": p.get("findings_count")}
        for p in get_client().iter_all("/products/")
    ]


@mcp.tool()
def list_critical_findings(
    product: str | None = None, include_duplicates: bool = False
) -> list[dict]:
    """List actionable CRITICAL findings (active, not false-positive/risk-accepted/mitigated).

    Optionally scope to one product. Set include_duplicates=True to also see duplicates.
    """
    return _fetch_findings("Critical", product, include_duplicates)


@mcp.tool()
def list_findings_by_severity(
    severity: str,
    product: str | None = None,
    include_duplicates: bool = False,
) -> list[dict]:
    """List actionable findings of a given severity (Critical, High, Medium, Low or Info)."""
    return _fetch_findings(normalize_severity(severity), product, include_duplicates)


@mcp.tool()
def group_critical_by_vuln() -> list[dict]:
    """Group actionable CRITICAL findings across every product by unique vulnerability.

    Keyed on CVE where present, else CWE plus title. Useful for filing one tracker
    issue per vulnerability that lists every affected product. Widest blast radius first.
    """
    return group_by_vulnerability(_fetch_findings("Critical", None, include_duplicates=False))


@mcp.tool()
def list_duplicate_findings(product: str | None = None) -> list[dict]:
    """List findings DefectDojo has marked as duplicates, optionally scoped to one product."""
    client = get_client()
    base_url = client.settings.url
    products = client.products_by_id()
    filters = {"duplicate": "true", "active": "true"}

    if product:
        product_id = _resolve_product_id(products, product)
        if product_id is None:
            return []
        targets = [(product_id, products[product_id])]
    else:
        targets = list(products.items())

    out: list[dict] = []
    for product_id, product_name in targets:
        raw = client.get_all(
            "/findings/", {**filters, "test__engagement__product": product_id}
        )
        out.extend(condense(f, product_name, base_url) for f in raw)
    return out


@mcp.tool()
def get_finding(finding_id: int) -> dict:
    """Full detail for one finding: description, mitigation, references, CWE/CVE and location."""
    client = get_client()
    finding = client.get(f"/findings/{finding_id}/")
    finding["url"] = client.settings.finding_url(finding_id)
    return finding


# ──────────────────────────────── entry point ────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="defectdojo-community-mcp",
        description="Read-only MCP server for DefectDojo Community Edition.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify configuration and connectivity, print the result, and exit.",
    )
    args = parser.parse_args(argv)

    if args.check:
        try:
            result = health_check()
        except ConfigError as exc:
            print(f"configuration error: {exc}")
            return 2
        except Exception as exc:
            print(f"connection failed: {type(exc).__name__}: {exc}")
            return 1
        print(f"ok: {result['url']} reachable, {result['product_count']} product(s) visible")
        return 0

    try:
        get_client()
    except ConfigError as exc:
        # Printed rather than raised: this is the first thing a misconfigured
        # user sees in their MCP client log, and a traceback helps nobody.
        print(f"configuration error: {exc}")
        return 2

    mcp.run()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
