"""Stable domain objects for geometry extracted from weak-semantic models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Mapping


MODEL_UNDERSTANDING_SCHEMA_VERSION = "model-understanding.v0.1"


class SemanticLevel(str, Enum):
    RICH = "RICH"
    SEMI = "SEMI"
    DUMB = "DUMB"


class GeometryKind(str, Enum):
    SOLID = "SOLID"
    SHELL = "SHELL"
    SURFACE = "SURFACE"
    MIXED = "MIXED"
    UNKNOWN = "UNKNOWN"


class ClosureState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    MIXED = "MIXED"
    UNKNOWN = "UNKNOWN"


class GeometryCapability(str, Enum):
    EXACT_BREP = "EXACT_BREP"
    TESSELLATED = "TESSELLATED"
    STRUCTURE_ONLY = "STRUCTURE_ONLY"


class GeometryState(str, Enum):
    AVAILABLE = "AVAILABLE"
    EMPTY = "EMPTY"
    UNAVAILABLE = "UNAVAILABLE"
    PARTIAL = "PARTIAL"


@dataclass(frozen=True)
class Transform:
    """Row-major 4x4 local-to-parent transform."""

    matrix: tuple[float, ...] = (
        1.0, 0.0, 0.0, 0.0,
        0.0, 1.0, 0.0, 0.0,
        0.0, 0.0, 1.0, 0.0,
        0.0, 0.0, 0.0, 1.0,
    )

    def __post_init__(self) -> None:
        values = tuple(float(value) for value in self.matrix)
        if len(values) != 16:
            raise ValueError("Transform.matrix must contain 16 values")
        object.__setattr__(self, "matrix", values)


@dataclass(frozen=True)
class ModelSource:
    adapter: str
    document: str
    full_path: str | None = None
    source_format: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.adapter.strip() or not self.document.strip():
            raise ValueError("ModelSource adapter and document must not be empty")
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True)
class Component:
    component_id: str
    source_name: str
    parent_component_id: str | None
    child_component_ids: tuple[str, ...] = ()
    body_ids: tuple[str, ...] = ()
    local_transform: Transform = field(default_factory=Transform)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.component_id or not self.source_name:
            raise ValueError("Component id and source name must not be empty")
        object.__setattr__(self, "child_component_ids", tuple(self.child_component_ids))
        object.__setattr__(self, "body_ids", tuple(self.body_ids))
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True)
class Body:
    body_id: str
    source_id: str
    source_name: str
    source_path: str
    parent_component_id: str
    geometry_kind: GeometryKind = GeometryKind.UNKNOWN
    closure_state: ClosureState = ClosureState.UNKNOWN
    geometry_state: GeometryState = GeometryState.UNAVAILABLE
    local_transform: Transform = field(default_factory=Transform)
    world_transform: Transform = field(default_factory=Transform)
    geometry_signature: str | None = None
    capabilities: tuple[GeometryCapability, ...] = (GeometryCapability.STRUCTURE_ONLY,)
    geometry_features: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("body_id", "source_id", "source_name", "source_path", "parent_component_id"):
            if not str(getattr(self, name)).strip():
                raise ValueError(f"Body.{name} must not be empty")
        object.__setattr__(self, "capabilities", tuple(self.capabilities))
        object.__setattr__(self, "geometry_features", dict(self.geometry_features))
        object.__setattr__(self, "metadata", dict(self.metadata))
        object.__setattr__(self, "limitations", tuple(self.limitations))


@dataclass(frozen=True)
class UnifiedGeometryModel:
    model_id: str
    source: ModelSource
    semantic_level: SemanticLevel
    semantic_score: float
    root_component_id: str
    components: Mapping[str, Component]
    bodies: Mapping[str, Body]
    units: str = "mm"
    limitations: tuple[str, ...] = ()
    schema_version: str = MODEL_UNDERSTANDING_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.model_id or not self.root_component_id:
            raise ValueError("Model and root component ids must not be empty")
        if not 0.0 <= float(self.semantic_score) <= 1.0:
            raise ValueError("semantic_score must be between 0 and 1")
        if self.units != "mm":
            raise ValueError("Unified geometry uses millimetres internally")
        components, bodies = dict(self.components), dict(self.bodies)
        if self.root_component_id not in components:
            raise ValueError("root_component_id is not present in components")
        if any(body.parent_component_id not in components for body in bodies.values()):
            raise ValueError("Every body must reference an existing component")
        object.__setattr__(self, "components", components)
        object.__setattr__(self, "bodies", bodies)
        object.__setattr__(self, "limitations", tuple(self.limitations))

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["semantic_level"] = self.semantic_level.value
        for body in value["bodies"].values():
            body["geometry_kind"] = body["geometry_kind"].value
            body["closure_state"] = body["closure_state"].value
            body["geometry_state"] = body["geometry_state"].value
            body["capabilities"] = [item.value for item in body["capabilities"]]
        return value
