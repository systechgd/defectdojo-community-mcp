# DefectDojo Community MCP Server
#
# The server speaks MCP over stdio, so the container is run attached, not
# detached, and exposes no port:
#
#   docker run --rm -i \
#     -e DEFECTDOJO_URL=https://defectdojo.example.com \
#     -e DEFECTDOJO_API_KEY=... \
#     ghcr.io/systechgd/defectdojo-community-mcp:latest

FROM python:3.12-slim AS builder

WORKDIR /build

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

COPY pyproject.toml README.md LICENSE NOTICE ./
COPY src ./src

RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.12-slim

LABEL org.opencontainers.image.title="defectdojo-community-mcp" \
      org.opencontainers.image.description="Read-only MCP server for DefectDojo Community Edition" \
      org.opencontainers.image.source="https://github.com/systechgd/defectdojo-community-mcp" \
      org.opencontainers.image.licenses="Apache-2.0"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# A plain non-root user. The server needs no write access anywhere.
RUN useradd --system --uid 10001 --create-home --shell /usr/sbin/nologin app

COPY --from=builder /install /usr/local

USER app

WORKDIR /home/app

ENTRYPOINT ["defectdojo-community-mcp"]
