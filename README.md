# DefectDojo Community MCP Server

[![CI](https://github.com/systechgd/defectdojo-community-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/systechgd/defectdojo-community-mcp/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)

A **read-only** [Model Context Protocol](https://modelcontextprotocol.io) server for
**DefectDojo Community Edition** — so an AI assistant can read your vulnerability
findings, group the same vulnerability across every product, and draft issues for
whatever tracker you use.

> **Unofficial.** This is an independent open-source project. It is not affiliated
> with, endorsed by, or supported by DefectDojo Inc. or OWASP. "DefectDojo" is used
> only to describe what this server connects to.

---

## Do you actually need this?

**If you run DefectDojo Pro, you probably don't.** Pro has a built-in MCP server —
use that instead; it is maintained by the vendor and more capable.

| | **DefectDojo Pro (built-in)** | **This project** |
|---|---|---|
| Edition | Pro only — [AI features are Pro-only](https://docs.defectdojo.com/metrics_reports/ai/mcp_server_pro/) | Community Edition (works with Pro too) |
| Requires | DefectDojo v2.51.2+, enabled by a superuser | Any version with API v2 |
| Runs | Inside your instance, at `/mcp` | On your machine, as a local MCP process |
| Transport | Streamable HTTP | stdio |
| Tools | 18 in the read-only `core` toolset | 7 |
| Writes | None in `core`; available in Pro add-on toolsets (`hierarchy`, `reporting`, `dashboards`, `psirt`) | **Never** — see [Safety model](#safety-model) |

This project exists because Community Edition has no MCP server at all. It talks to
the ordinary REST API v2 with a normal API token, so it needs nothing enabled
server-side and no particular DefectDojo version.

> Not to be confused with the unrelated [`defectdojo-mcp`](https://pypi.org/project/defectdojo-mcp/)
> package on PyPI, which is a different third-party project. This one is
> `defectdojo-community-mcp`.

---

## Tools

| Tool | What it does |
|---|---|
| `health_check` | Verify connectivity and auth; returns the instance URL and product count |
| `list_products` | Every product, with its findings count |
| `list_critical_findings` | Actionable criticals, optionally scoped to one product |
| `list_findings_by_severity` | The same, for any severity |
| `group_critical_by_vuln` | **The useful one.** Groups criticals across all products by CVE (else CWE+title), widest blast radius first |
| `list_duplicate_findings` | Findings DefectDojo marked as duplicates |
| `get_finding` | Full detail for one finding |

"Actionable" means `active` and not false-positive, duplicate, risk-accepted,
out-of-scope or mitigated — the set actually worth someone's time.

`group_critical_by_vuln` is the reason this exists. A monorepo-shaped scanner
setup reports the same upstream CVE once per product; this collapses them into one
group per vulnerability listing every affected product, which maps cleanly onto one
tracker issue.

---

## Install

Requires Python 3.10+.

```bash
pip install defectdojo-community-mcp
```

Or from source:

```bash
git clone https://github.com/systechgd/defectdojo-community-mcp.git
cd defectdojo-community-mcp
pip install -e .
```

---

## Configure

Two environment variables are required.

| Variable | Required | Default | Notes |
|---|---|---|---|
| `DEFECTDOJO_URL` | yes | — | Base URL, e.g. `https://defectdojo.example.com`. No trailing `/api/v2`. |
| `DEFECTDOJO_API_KEY` | yes | — | API v2 token. See below for scoping it down. |
| `DEFECTDOJO_VERIFY_TLS` | no | `true` | `false` disables certificate verification. See [SECURITY.md](SECURITY.md). |
| `DEFECTDOJO_TIMEOUT_SECONDS` | no | `30` | Per-request HTTP timeout. |

Get a token from **DefectDojo → your user → API v2 Key**.

**Create a dedicated read-only user for it.** The token inherits that user's
permissions, and nothing in this server needs write access. If the token leaks, a
read-only one cannot be used to alter your findings.

Check it works before wiring up a client:

```bash
defectdojo-community-mcp --check
# ok: https://defectdojo.example.com reachable, 23 product(s) visible
```

---

## Connect an MCP client

### Claude Code

```bash
claude mcp add defectdojo \
  --env DEFECTDOJO_URL=https://defectdojo.example.com \
  --env DEFECTDOJO_API_KEY=your-token \
  -- defectdojo-community-mcp
```

### Claude Desktop / generic JSON config

```json
{
  "mcpServers": {
    "defectdojo": {
      "command": "defectdojo-community-mcp",
      "env": {
        "DEFECTDOJO_URL": "https://defectdojo.example.com",
        "DEFECTDOJO_API_KEY": "your-token"
      }
    }
  }
}
```

If the console script is not on your `PATH`, use
`"command": "python", "args": ["-m", "defectdojo_community_mcp"]`.

### Docker

The server speaks MCP over stdio, so run it attached (`-i`), not detached:

```json
{
  "mcpServers": {
    "defectdojo": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "-e", "DEFECTDOJO_URL",
        "-e", "DEFECTDOJO_API_KEY",
        "ghcr.io/systechgd/defectdojo-community-mcp:latest"
      ]
    }
  }
}
```

---

## Example

> Group every critical finding by vulnerability and show me the ones affecting
> more than three services.

The assistant calls `group_critical_by_vuln` and gets back, per vulnerability, the
CVE, title, affected product list and a direct DefectDojo URL per finding — enough
to write one issue covering all of them, instead of twelve near-identical ones.

---

## Safety model

**Read-only is a design invariant, not a default.**

- No tool issues a `POST`, `PUT`, `PATCH` or `DELETE`.
- The HTTP client class exposes no method capable of doing so, so a mutating tool
  cannot be added by accident — only by deliberately changing that class.
- A test asserts that every request made by every tool is a `GET`.

Adding write support would be a breaking change to this guarantee. If it ever
happens it will be a **separate server**, so operators can keep granting read
without granting write.

Findings data is attacker-influenced — scanner output can contain text from
dependency metadata, file paths and commit messages. Treat tool results as data,
never as instructions. See [SECURITY.md](SECURITY.md) for the full threat model and
how to report a vulnerability.

---

## Development

```bash
git clone https://github.com/systechgd/defectdojo-community-mcp.git
cd defectdojo-community-mcp
python -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

pytest          # 57 tests, no network or live instance needed
ruff check .
```

The test suite runs entirely against `httpx.MockTransport`. CI additionally runs the
suite on Python 3.10–3.13 and against both MCP SDK generations (`mcp<2`, which has
`FastMCP`, and `mcp>=2`, which renamed it to `MCPServer`).

See [CONTRIBUTING.md](CONTRIBUTING.md) and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

---

## License

[Apache-2.0](LICENSE). See [NOTICE](NOTICE).
