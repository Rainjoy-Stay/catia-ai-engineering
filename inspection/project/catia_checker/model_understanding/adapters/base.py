"""Adapter contract separating source access from engineering classification."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from ..domain import UnifiedGeometryModel


@dataclass(frozen=True)
class AdapterCapabilities:
    structure: bool = True
    transforms: bool = False
    exact_brep: bool = False
    tessellation: bool = False
    surface_types: bool = False


class ModelAdapter(Protocol):
    capabilities: AdapterCapabilities

    def adapt(self, source: Mapping[str, Any], *,
              geometry: Mapping[str, Any] | None = None) -> UnifiedGeometryModel: ...
