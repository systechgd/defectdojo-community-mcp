"""Allow ``python -m defectdojo_community_mcp``."""

from __future__ import annotations

from .server import main

if __name__ == "__main__":
    raise SystemExit(main())
