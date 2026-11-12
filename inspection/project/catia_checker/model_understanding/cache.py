"""Small JSON cache keyed by intrinsic geometry signatures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class GeometryFeatureCache:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.entries: dict[str, dict[str, Any]] = {}
        if self.path.exists():
            value = json.loads(self.path.read_text(encoding="utf-8"))
            if value.get("schema_version") != "geometry-cache.v0.7":
                raise ValueError("unsupported geometry cache schema")
            self.entries = dict(value.get("entries", {}))

    def get(self, signature: str) -> dict[str, Any] | None:
        value = self.entries.get(signature)
        return dict(value) if value is not None else None

    def put(self, signature: str, features: dict[str, Any]) -> None:
        self.entries[signature] = dict(features)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"schema_version": "geometry-cache.v0.7",
                                         "entries": self.entries}, indent=2,
                                        ensure_ascii=False), encoding="utf-8")


def changed_signatures(previous: dict[str, str], current: dict[str, str]) -> dict[str, list[str]]:
    return {
        "added": sorted(set(current) - set(previous)),
        "removed": sorted(set(previous) - set(current)),
        "changed": sorted(key for key in set(previous) & set(current)
                          if previous[key] != current[key]),
        "unchanged": sorted(key for key in set(previous) & set(current)
                            if previous[key] == current[key]),
    }
