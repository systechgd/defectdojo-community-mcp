"""Backwards-compatible entry point.

The implementation moved into ``src/defectdojo_community_mcp/`` in v0.1.0.
This shim stays so MCP client configs that point at ``server.py`` keep working.

Prefer the installed console script:

    defectdojo-community-mcp

or the module form:

    python -m defectdojo_community_mcp
"""

from __future__ import annotations

import os
import sys

# Support running this file directly from a source checkout, without installing.
_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if os.path.isdir(_SRC) and _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from defectdojo_community_mcp.server import main, mcp  # noqa: E402

__all__ = ["main", "mcp"]

if __name__ == "__main__":
    raise SystemExit(main())
