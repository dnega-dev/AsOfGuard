"""Access to packaged synthetic trace fixtures."""

from __future__ import annotations

from importlib import resources
from typing import Dict, List

from .models import Trace
from .parser import loads_trace


FIXTURE_PACKAGE = "asof_guard.fixtures"


def fixture_names() -> List[str]:
    """List available packaged fixture names without the ``.jsonl`` suffix."""

    root = resources.files(FIXTURE_PACKAGE)
    return sorted(item.name[:-6] for item in root.iterdir() if item.name.endswith(".jsonl"))


def fixture_text(name: str) -> str:
    """Return a packaged fixture as JSONL text."""

    normalized = name[:-6] if name.endswith(".jsonl") else name
    if not normalized or "/" in normalized or "\\" in normalized or normalized in {".", ".."}:
        raise KeyError(name)
    candidate = resources.files(FIXTURE_PACKAGE).joinpath(normalized + ".jsonl")
    if not candidate.is_file():
        raise KeyError(name)
    return candidate.read_text(encoding="utf-8")


def load_fixture(name: str) -> Trace:
    """Parse a packaged fixture by name."""

    normalized = name[:-6] if name.endswith(".jsonl") else name
    return loads_trace(fixture_text(normalized), source=f"fixture:{normalized}")


def fixture_catalog() -> List[Dict[str, object]]:
    """Return fixture metadata and expected rule codes from trace headers."""

    entries: List[Dict[str, object]] = []
    for name in fixture_names():
        trace = load_fixture(name)
        entries.append(
            {
                "name": name,
                "trace_id": trace.id,
                "expected_status": trace.expectations.get("status"),
                "expected_codes": trace.expectations.get("codes", []),
                "description": trace.expectations.get("description", ""),
            }
        )
    return entries
