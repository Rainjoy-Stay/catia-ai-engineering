"""Convert CATIA manifest output to the V0.1 unified geometry model."""

from __future__ import annotations

import hashlib
from typing import Any, Mapping

from .base import AdapterCapabilities
from ..domain import (
    Body, ClosureState, Component, GeometryCapability, GeometryKind, GeometryState,
    ModelSource, Transform, UnifiedGeometryModel,
)
from ..semantic_level import evaluate_semantic_level
from ..features.basic import normalize_basic_features
from ..features.surfaces import summarize_surfaces


class CATIAManifestAdapter:
    """Read-only structure adapter; optional geometry is keyed by source path."""

    capabilities = AdapterCapabilities(structure=True)

    @staticmethod
    def _id(prefix: str, value: str) -> str:
        digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:16].upper()
        return f"{prefix}_{digest}"

    def adapt(self, source: Mapping[str, Any], *,
              geometry: Mapping[str, Any] | None = None) -> UnifiedGeometryModel:
        if not source.get("active_document") or not source.get("assembly"):
            raise ValueError("CATIA manifest requires active_document and assembly")
        geometry = dict(geometry or {})
        parts = source.get("parts", {})
        components: dict[str, Component] = {}
        bodies: dict[str, Body] = {}

        def visit(node: Mapping[str, Any], parent_id: str | None, path: str) -> str:
            name = str(node.get("name") or "UNNAMED")
            node_path = f"{path}/{name}" if path else name
            component_id = self._id("COMP", node_path)
            child_ids = tuple(visit(child, component_id, node_path)
                              for child in node.get("children", ()) or ())
            part_key = node.get("part_key")
            body_ids: list[str] = []
            part = parts.get(part_key, {}) if part_key else {}
            for index, record in enumerate(part.get("bodies", ()) or (), 1):
                body_name = str(record.get("name") or f"Body.{index}")
                source_path = f"{node_path}/{body_name}"
                body_id = self._id("BODY", source_path)
                measure = dict(geometry.get(source_path, {}))
                capabilities = tuple(GeometryCapability(item) for item in
                                     measure.pop("capabilities", ["STRUCTURE_ONLY"]))
                raw_faces = measure.pop("faces", None)
                normalized = normalize_basic_features(measure) if measure else {}
                if raw_faces is not None:
                    normalized["surface_statistics"] = summarize_surfaces(raw_faces)
                requested_state = measure.pop("geometry_state", None) if measure else None
                if requested_state:
                    geometry_state = GeometryState(requested_state)
                elif normalized:
                    geometry_state = GeometryState.AVAILABLE
                else:
                    geometry_state = GeometryState.UNAVAILABLE
                body = Body(
                    body_id=body_id, source_id=f"{part_key or name}#{index}",
                    source_name=body_name, source_path=source_path,
                    parent_component_id=component_id,
                    geometry_kind=GeometryKind(measure.pop("geometry_kind", "UNKNOWN")),
                    closure_state=ClosureState(measure.pop("closure_state", "UNKNOWN")),
                    geometry_state=geometry_state,
                    geometry_signature=measure.pop("geometry_signature", None),
                    capabilities=capabilities, geometry_features=normalized,
                    metadata={"part_key": part_key, "shape_count": len(record.get("shapes", ()))},
                    limitations=(() if normalized else ("body geometry measurements were not supplied",)),
                )
                bodies[body_id] = body
                body_ids.append(body_id)
            components[component_id] = Component(
                component_id=component_id, source_name=name,
                parent_component_id=parent_id, child_component_ids=child_ids,
                body_ids=tuple(body_ids), local_transform=Transform(),
                metadata={"part_key": part_key, "part_number": node.get("part_number")},
            )
            return component_id

        root_id = visit(source["assembly"], None, "")
        evaluation = evaluate_semantic_level(source)
        document = str(source["active_document"])
        model_id = self._id("MODEL", f"{document}|{root_id}")
        limitations = list(evaluation.limitations)
        if not geometry:
            limitations.append("adapter received structure only; exact geometry was not supplied")
        return UnifiedGeometryModel(
            model_id=model_id,
            source=ModelSource(adapter="CATIA_MANIFEST", document=document,
                               metadata={"document_type": source.get("document_type")}),
            semantic_level=evaluation.level, semantic_score=evaluation.score,
            root_component_id=root_id, components=components, bodies=bodies,
            limitations=tuple(limitations),
        )

    def adapt_body_batch(self, source: Mapping[str, Any],
                         batch: Mapping[str, Any]) -> UnifiedGeometryModel:
        """Attach one exact CATPart Body batch after strict scope validation."""
        if batch.get("schema_version") != "catia.body-geometry.v0.1":
            raise ValueError("Unsupported CATIA Body geometry batch schema")
        if str(batch.get("measurement_scope", "")).upper() != "BODY":
            raise ValueError("CATIA geometry batch must have BODY scope")
        if str(batch.get("document")) != str(source.get("active_document")):
            raise ValueError("CATIA geometry batch document does not match manifest")
        if source.get("document_type") != "CATPart":
            raise ValueError("A single Body batch can only be attached to a CATPart manifest")
        records = batch.get("bodies", ())
        names = [str(item.get("body_name", "")) for item in records]
        if any(not name for name in names) or len(names) != len(set(names)):
            raise ValueError("CATIA geometry batch Body names must be non-empty and unique")
        root_name = str(source.get("assembly", {}).get("name") or source["active_document"])
        geometry = {f"{root_name}/{name}": dict(record)
                    for name, record in zip(names, records)}
        return self.adapt(source, geometry=geometry)
