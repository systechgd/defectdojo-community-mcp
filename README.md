# DefectDojo MCP Server

[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-read--only-6E56CF.svg)](https://modelcontextprotocol.io)

A **read-only** [Model Context Protocol](https://modelcontextprotocol.io) server for
[DefectDojo](https://www.defectdojo.org/). It exposes your DefectDojo findings to an
MCP-capable AI agent so the agent can triage vulnerabilities across every product and
draft self-contained issues for your tracker — without the developers who fix them
needing DefectDojo logins.

> **Unofficial project.** This is an independent, community-maintained server. It is
> not affiliated with, endorsed by, or sponsored by DefectDojo or OWASP. See
> [Trademarks](#trademarks).

## Why

DefectDojo is excellent at aggregating scanner output and poor at telling a developer
what to do on Monday morning. A security pipeline can easily produce hundreds of
findings in which a dozen dependency bumps resolve most of them.

This server gives an agent exactly the read access it needs to do that reduction:
pull the actionable findings, group them by the underlying vulnerability, and write a
fix-oriented summary.

```
Security scanners ──import──▶ DefectDojo ──API v2──▶ this MCP server ──▶ AI agent
(Trivy, Dependency-Check,     (findings)             (read-only)            │
 SonarQube, gitleaks, …)                                                   ▼
                                                        triaged, self-contained
                                                        issues in your tracker
```

## Safety model

**Read-only by construction.** Every tool in this server issues `GET` requests only —
there is no code path that performs `POST`, `PUT`, `PATCH` or `DELETE`. It cannot
create, edit, close, or risk-accept a finding, and it cannot change DefectDojo
configuration. The worst an agent can do through this server is read.

Pair it with a DefectDojo token belonging to a **read-only user** for defence in
depth. See [SECURITY.md](SECURITY.md).

## Requirements

- Python 3.10 or newer
- A DefectDojo instance (community edition is fine) reachable over HTTPS
- A DefectDojo **API v2** token

## Install

```bash
git clone https://github.com/systechgd/defectdojo-mcp.git
cd defectdojo-mcp

python -m venv .venv
# Linux / macOS
.venv/bin/python -m pip install -r requirements.txt
# Windows
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Configure

The server reads its configuration from the environment. Create a `.env` beside
`server.py` so the token never has to sit in your MCP client config:

```bash
cp .env.example .env
```

```ini
DEFECTDOJO_URL=https://defectdojo.example.com
DEFECTDOJO_API_KEY=your-defectdojo-api-v2-token
# DEFECTDOJO_VERIFY_TLS=false   # only for self-signed certs -- see SECURITY.md
```

| Variable | Required | Default | Description |
|---|---|---|---|
| `DEFECTDOJO_URL` | yes | — | Base URL of your DefectDojo instance |
| `DEFECTDOJO_API_KEY` | yes | — | API v2 token (DefectDojo → user menu → **API v2 Key**) |
| `DEFECTDOJO_VERIFY_TLS` | no | `true` | Set to `false` to skip TLS verification. **Discouraged.** |

`.env` is git-ignored. Never commit it.

### Verify before wiring up an agent

```bash
.venv/bin/python -c "import json, server; print(json.dumps(server.health_check()))"
# => {"ok": true, "url": "https://...", "product_count": 23}
```

If this fails, the agent will fail too — fix it here first, where the error is readable.

## Register with an MCP client

Add the server to your client's `mcpServers` configuration using **absolute paths**:

```json
{
  "mcpServers": {
    "defectdojo": {
      "command": "/absolute/path/to/defectdojo-mcp/.venv/bin/python",
      "args": ["/absolute/path/to/defectdojo-mcp/server.py"]
    }
  }
}
```

On Windows, use `.venv\\Scripts\\python.exe`. Common config locations:

| Client | Path |
|---|---|
| Claude Code (global) | `~/.claude.json` |
| Claude Code (project) | `.mcp.json` in the project root |
| Claude Desktop | `claude_desktop_config.json` |

No token belongs in this file — it is loaded from `.env`. Restart the client afterwards.

## Tools

| Tool | Description |
|---|---|
| `health_check()` | Verify connectivity and auth; returns the reachable product count |
| `list_products()` | All products visible to the token |
| `list_critical_findings(product?, include_duplicates?)` | Actionable critical findings |
| `list_findings_by_severity(severity, product?, include_duplicates?)` | Any severity: `Critical`, `High`, `Medium`, `Low`, `Info` |
| `group_critical_by_vuln()` | One entry per unique vulnerability (CVE, else CWE+title) with every affected product |
| `list_duplicate_findings(product?)` | Findings DefectDojo has flagged as duplicates |
| `get_finding(finding_id)` | Full detail: description, mitigation, references, CWE/CVE, location |

**"Actionable"** means `active` and **not** false-positive, risk-accepted,
out-of-scope, mitigated, or duplicate — i.e. findings a human still owes work on.
Results are condensed to the fields that matter for triage, to keep agent context
small on large instances.

### A note on products

A *product* is whatever unit your scanners import under. Many CI pipelines import one
product per source repository, so product names often match repo names — but this
server makes no assumption about that and simply reports what your instance contains.

## Usage

Fleet-wide view of what actually needs fixing:

> Run `health_check`, then `group_critical_by_vuln` — show me the unique critical
> vulnerabilities and which products each one affects.

Per-product triage into a single tracker issue:

> Pull every severity for `payments-api` and draft a self-contained security issue:
> findings grouped by severity, plus a "how to fix" section grouped by dependency.

Confirm a remediation landed:

> Check `payments-api` — are Critical and High cleared now?

### A workflow that works well

1. **One issue per product**, self-contained: embed each finding's CVE (linked to
   NVD), the affected component and its fix version, and the CWE. Group the fix
   guidance *by dependency* — a single framework or BOM bump frequently clears most
   of the list. Developers then never need DefectDojo access.
2. Developer applies the bumps, pipeline re-scans and re-imports to DefectDojo.
3. Ask the agent to re-check through this server; close the issue when Critical and
   High are clear.

## Contributing

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) and note
the project's hard constraint: **this server stays read-only.** Pull requests adding
write operations to DefectDojo will not be merged — that belongs in a separate,
clearly-named server so operators can grant read access without granting write.

To report a security issue, see [SECURITY.md](SECURITY.md) — please do not open a
public issue.

## License

Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE) and
[NOTICE](NOTICE).

## Trademarks

"DefectDojo" and "OWASP" are trademarks of their respective owners. This project is
not affiliated with, endorsed by, or sponsored by either. Those names are used solely
to describe interoperability with that software, as permitted by nominative fair use.
