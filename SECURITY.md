# Security Policy

This project is a security tool that holds a credential to a system of record for
vulnerabilities. It is worth being careful with. This document covers how to report a
vulnerability in the server itself, and how to deploy it safely.

## Reporting a vulnerability

**Please do not open a public issue for a security vulnerability.**

Report it privately through GitHub's
[private vulnerability reporting](https://github.com/systechgd/defectdojo-mcp/security/advisories/new)
on this repository. If that is unavailable to you, open a public issue containing only
"security report, please provide a private contact" and nothing further.

Please include:

- the affected version or commit,
- what an attacker can achieve,
- reproduction steps or a proof of concept,
- your assessment of impact.

**What to expect:** acknowledgement within 5 working days, an initial assessment
within 10, and coordinated disclosure once a fix is available. This is a volunteer
project with no paid on-call rotation — if you have had no reply in 10 working days,
please ping the report.

I will credit you in the release notes and advisory unless you ask me not to.

## Supported versions

This project is pre-1.0. Only the latest release on the `main` branch receives
security fixes. There are no long-term support branches.

## Deploying this safely

### Use a read-only DefectDojo token

The server is read-only by construction — every tool issues `GET` requests only, and
no code path performs `POST`, `PUT`, `PATCH` or `DELETE`. Treat that as the inner
layer of defence, not the only one.

Create a dedicated DefectDojo user with read-only permissions and scope it to the
products the agent needs, then issue the API token from that account. If the server,
the client, or the agent is ever compromised, the blast radius is bounded by the
token's permissions rather than by this code being correct.

### Treat the API token as a secret

- Keep it in `.env` (git-ignored) or inject it from your platform's secret store.
- Do not put it in your MCP client configuration file, shell history, or CI logs —
  client configs are frequently committed to dotfile repositories.
- Rotate it if it is ever written to a log, a terminal transcript, or a shared
  screen.
- The server never logs the token and sends it only to `DEFECTDOJO_URL`.

### `DEFECTDOJO_VERIFY_TLS=false` is dangerous

This escape hatch exists for DefectDojo instances behind a self-signed certificate.
Setting it disables TLS certificate verification, which means an attacker positioned
on the network path can impersonate your DefectDojo instance and **capture your API
token**.

Prefer, in order:

1. a certificate from a public CA (ACME/Let's Encrypt),
2. an internal CA whose root you install in your OS or Python trust store,
3. `DEFECTDOJO_VERIFY_TLS=false` — only on a trusted network segment, never across
   the public internet.

### Understand what the agent will see

Findings include descriptions, file paths, component versions, and sometimes
secret-scanner output. When you connect this server to a hosted AI model, that data
is sent to the model provider as part of the conversation. Confirm it is consistent
with your organisation's data-handling policy — and remember that gitleaks-style
findings may quote the secret itself.

### Prompt-injection exposure

Finding titles, descriptions, and mitigation text originate from scanners and from
the upstream code and dependencies they scanned — not from you. An agent that reads
them is reading untrusted input, and a crafted dependency description could attempt
to steer it.

Because this server cannot write to DefectDojo, injection cannot be laundered into a
state change *here*. The risk lies in the agent's **other** tools. Do not pair this
server with write-capable or destructive tools under autonomous execution; keep a
human in the loop for actions taken off the back of finding text.

## Scope

In scope: the code in this repository — credential handling, TLS behaviour, data
leakage between products, and any path that would let a caller mutate DefectDojo.

Out of scope: vulnerabilities in DefectDojo itself (report those to the
[DefectDojo project](https://github.com/DefectDojo/django-DefectDojo/security)),
in the `mcp`, `httpx`, or `python-dotenv` dependencies (report upstream), and
findings that require an attacker to already control the machine running the server.
