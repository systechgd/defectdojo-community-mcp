# Contributing

Thanks for considering a contribution. This is a small, focused project and that is
deliberate — the goal is a server an operator can read end to end before pointing it
at their vulnerability data.

## The one hard rule: this server stays read-only

Every tool issues `GET` requests only. No code path may perform `POST`, `PUT`,
`PATCH` or `DELETE` against DefectDojo.

This is a security property, not a feature gap. Operators grant this server a token
because they can verify it cannot mutate their findings. Pull requests that add write
operations will not be merged, however useful — a write-capable server belongs in a
separate, clearly-named project so operators can choose to grant read access without
granting write.

Changes that are welcome: new read-only queries, better grouping and summarisation,
performance on large instances, error handling, docs, tests, and packaging.

## Getting set up

```bash
git clone https://github.com/systechgd/defectdojo-mcp.git
cd defectdojo-mcp
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt   # Windows: .venv\Scripts\python.exe
cp .env.example .env    # point it at a DefectDojo instance you own
```

Confirm your environment works before changing anything:

```bash
.venv/bin/python -c "import json, server; print(json.dumps(server.health_check()))"
```

## Submitting a change

1. Open an issue first for anything beyond a bug fix or docs change, so we agree on
   the approach before you spend time on it.
2. Keep pull requests focused — one concern per PR.
3. Describe how you tested it. If you tested against a real DefectDojo instance, say
   which version; the API differs across releases.
4. Update the README if you add or change a tool.

### Code style

- Python 3.10+, type hints on public functions.
- Follow the existing shape: a thin `@mcp.tool()` function delegating to a helper.
- Docstrings are user-facing — the agent reads them to decide which tool to call, so
  write them for that reader.
- Keep returned payloads condensed. Instances with tens of thousands of findings are
  normal, and verbose responses exhaust an agent's context.
- No new runtime dependencies without a good reason; if you add one, declare it in
  `requirements.txt`.

### Things that will get a PR sent back

- Any write operation to DefectDojo (see above).
- Logging, printing, or returning the API token.
- Hard-coded URLs, hostnames, organisation names, product names, or tokens — real or
  placeholder. Configuration comes from the environment.
- Disabling TLS verification by default.
- Committing a `.env`, a certificate, or any real finding data.

## Reporting bugs

Include your Python version, DefectDojo version, the tool you called, and the full
error. Please redact URLs, tokens, and finding content.

For **security** vulnerabilities, do not open a public issue — follow
[SECURITY.md](SECURITY.md).

## Licensing of contributions

This project is licensed under [Apache-2.0](LICENSE). By submitting a contribution
you agree it is licensed under the same terms, per section 5 of that licence, and you
confirm you have the right to contribute it.
