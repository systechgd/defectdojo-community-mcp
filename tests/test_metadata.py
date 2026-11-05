"""Guards against metadata drift between the files that declare a version.

The version is stated in three places (pyproject.toml, __init__.py and
server.json) and the MCP Registry rejects a publish whose ownership markers do
not match server.json exactly. Both are cheap to get wrong by hand and
expensive to notice later, since a mismatched PyPI version cannot be
reuploaded.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

import defectdojo_community_mcp

ROOT = Path(__file__).resolve().parent.parent

PYPROJECT = ROOT / "pyproject.toml"
SERVER_JSON = ROOT / "server.json"
README = ROOT / "README.md"
DOCKERFILE = ROOT / "Dockerfile"

# Only present in a source checkout; skip when running against an installed wheel.
needs_checkout = pytest.mark.skipif(
    not PYPROJECT.is_file(), reason="not running from a source checkout"
)


def _pyproject_version() -> str:
    text = PYPROJECT.read_text(encoding="utf-8")
    match = re.search(r'^version = "([^"]+)"', text, re.M)
    assert match, "no version in pyproject.toml"
    return match.group(1)


def _server_json() -> dict:
    return json.loads(SERVER_JSON.read_text(encoding="utf-8"))


@needs_checkout
def test_package_version_matches_pyproject():
    assert defectdojo_community_mcp.__version__ == _pyproject_version()


@needs_checkout
def test_server_json_version_matches_package():
    assert _server_json()["version"] == defectdojo_community_mcp.__version__


@needs_checkout
def test_server_json_package_versions_match():
    for package in _server_json()["packages"]:
        if "version" not in package:
            continue
        assert package["version"] == defectdojo_community_mcp.__version__, (
            f"{package['registryType']} package version is out of step"
        )


@needs_checkout
def test_oci_package_has_no_version_field():
    """The registry rejects it, even though the JSON schema permits it.

    OCI packages must carry the version in the identifier tag instead. This is
    a server-side rule the 2025-12-11 schema does not encode, so validating
    against the schema alone will not catch a regression here.
    """
    oci = next(p for p in _server_json()["packages"] if p["registryType"] == "oci")
    assert "version" not in oci


@needs_checkout
def test_oci_identifier_is_tagged_with_this_version():
    oci = next(p for p in _server_json()["packages"] if p["registryType"] == "oci")
    assert oci["identifier"].endswith(f":{defectdojo_community_mcp.__version__}")


@needs_checkout
def test_readme_carries_the_registry_ownership_marker():
    """The MCP Registry reads this out of the PyPI long description."""
    name = _server_json()["name"]
    assert f"mcp-name: {name}" in README.read_text(encoding="utf-8")


@needs_checkout
def test_dockerfile_carries_the_registry_ownership_label():
    name = _server_json()["name"]
    expected = f'LABEL io.modelcontextprotocol.server.name="{name}"'
    assert expected in DOCKERFILE.read_text(encoding="utf-8")
