# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.1] - 2026-11-05

Distribution release. No functional change to the server itself.

### Added

- Published to PyPI as
  [`defectdojo-community-mcp`](https://pypi.org/project/defectdojo-community-mcp/)
  and to GHCR as `ghcr.io/systechgd/defectdojo-community-mcp` (linux/amd64 and
  linux/arm64, with a signed build provenance attestation).
- Release workflow publishing both on a `v*` tag. PyPI uses Trusted Publishing
  over OIDC, so no API token is stored in the repository.
- `server.json` and an MCP Registry publish step, listing both the PyPI package
  and the container image.
- Tests guarding metadata drift: the version in `pyproject.toml`,
  `__init__.py` and `server.json` must agree, the OCI identifier must carry
  this version, and both registry ownership markers must be present.

### Changed

- README carries an `mcp-name` marker and the image carries an
  `io.modelcontextprotocol.server.name` label. These are how the MCP Registry
  proves ownership of the published artifacts.

### Note

0.1.0 shipped to PyPI before the `mcp-name` marker existed, and a PyPI version
can never be reuploaded — hence this release rather than a correction in place.

## [0.1.0] - 2026-11-05

First public release.

### Added

- Seven read-only MCP tools: `health_check`, `list_products`,
  `list_critical_findings`, `list_findings_by_severity`,
  `group_critical_by_vuln`, `list_duplicate_findings` and `get_finding`.
- Installable package with a `defectdojo-community-mcp` console script and a
  `python -m defectdojo_community_mcp` module entry point.
- `--check` flag that verifies configuration and connectivity, then exits —
  so setup can be confirmed without wiring up an MCP client first.
- Test suite (57 tests) running against `httpx.MockTransport`; no network or
  live DefectDojo instance required. Includes a test asserting that every
  request the tools issue is a `GET`.
- GitHub Actions CI: lint, tests on Python 3.10–3.13, both MCP SDK
  generations, distribution build, and a Docker build that fails if the image
  runs as root.
- Dockerfile (multi-stage, non-root uid 10001).
- `DEFECTDOJO_TIMEOUT_SECONDS` to override the 30-second HTTP timeout.

### Changed

- **Project renamed** to DefectDojo **Community** MCP Server. DefectDojo Pro
  ships its own built-in MCP server; this project exists for Community
  Edition, which does not. The distribution name is
  `defectdojo-community-mcp` (`defectdojo-mcp` on PyPI is an unrelated
  third-party project).
- Restructured from a single `server.py` into a `src/` layout
  (`config`, `client`, `transform`, `server`). `server.py` remains at the
  repository root as a thin shim so existing MCP client configs that point at
  it keep working.
- Configuration is now resolved lazily instead of at import time. Importing
  the package no longer raises when `DEFECTDOJO_URL` / `DEFECTDOJO_API_KEY`
  are unset, which is what makes `--version`, `--help` and the tests runnable
  without a live instance.
- `Settings.__repr__` masks the API token, so it cannot reach a log line or a
  traceback.
- Severity input is normalised and validated. Previously `"critical"` was
  passed through to DefectDojo's case-sensitive filter and silently returned
  nothing; unknown severities now raise with the list of valid values.
- `group_critical_by_vuln` output is now deterministic: groups with equal
  product counts are ordered by vulnerability key rather than dict order.

### Fixed

- **Import failure on current MCP SDKs.** `mcp` 2.0 renamed `FastMCP` to
  `MCPServer`, so the previous code could not start against a fresh install.
  Both SDK generations are now supported and both are covered in CI.
- `python-dotenv` was imported but never declared as a dependency, so `.env`
  loading silently did nothing for anyone installing from a clean environment.
- Pagination could loop indefinitely on a malformed `next` link; it is now
  bounded.

### Security

- Read-only is enforced structurally: the client class exposes no method
  capable of issuing POST, PUT, PATCH or DELETE, and a test asserts it.

[Unreleased]: https://github.com/systechgd/defectdojo-community-mcp/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/systechgd/defectdojo-community-mcp/releases/tag/v0.1.1
[0.1.0]: https://github.com/systechgd/defectdojo-community-mcp/releases/tag/v0.1.0
