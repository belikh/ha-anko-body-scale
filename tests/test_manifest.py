"""Tests for manifest.json metadata."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_MANIFEST_PATH = (
    Path(__file__).resolve().parent.parent
    / "custom_components"
    / "anko_scale"
    / "manifest.json"
)

MANIFEST: dict[str, Any] = json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))


def test_domain_and_version() -> None:
    assert MANIFEST["domain"] == "anko_scale"
    assert MANIFEST["version"] == "1.2.1"
    assert MANIFEST["name"] == "ANKO Body Scale"


def test_ownership_and_docs_urls() -> None:
    assert MANIFEST["codeowners"] == ["@belikh"]
    assert MANIFEST["documentation"].startswith(
        "https://github.com/belikh/ha-anko-body-scale"
    )
    assert MANIFEST["issue_tracker"].startswith(
        "https://github.com/belikh/ha-anko-body-scale"
    )


def test_integration_character() -> None:
    assert MANIFEST["integration_type"] == "device"
    assert MANIFEST["iot_class"] == "local_push"
    assert MANIFEST["config_flow"] is True


def test_dependencies_and_bluetooth() -> None:
    assert MANIFEST["dependencies"] == ["bluetooth"]
    assert MANIFEST["bluetooth"] == [{"local_name": "IF_B7"}]
