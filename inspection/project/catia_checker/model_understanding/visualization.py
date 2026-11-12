"""Build a CAD-neutral V0.8 overlay specification from recognized geometry."""

from __future__ import annotations

from typing import Any, Mapping


def build_overlay_spec(features: Mapping[str, Mapping[str, Any]],
                       relationships: list[Mapping[str, Any]]) -> dict[str, Any]:
    centerlines, terminals = [], []
    for object_id, value in features.items():
        confidence = value.get("classification_confidence")
        for index, segment in enumerate(value.get("centerline_segments_world", ())):
            if segment.get("start_mm") and segment.get("end_mm"):
                centerlines.append({"object_id": object_id, "segment_index": index,
                                    "start_mm": segment["start_mm"], "end_mm": segment["end_mm"],
                                    "primitive_type": segment["primitive_type"],
                                    "confidence": confidence})
        for index, terminal in enumerate(value.get("terminal_candidates", ())):
            if terminal.get("coordinate_space") == "WORLD":
                terminals.append({"object_id": object_id, "terminal_index": index,
                                  "position_mm": terminal["position_mm"],
                                  "direction": terminal.get("direction"),
                                  "confidence": confidence})
    relation_records = [{
        "source_object_id": item.get("pipe_body_id", item.get("clamp_body_id")),
        "target_object_id": item.get("support_body_id"),
        "relationship_type": item.get("relationship_type"),
        "confidence": item.get("confidence"), "evidence": item.get("evidence"),
        "review_required": float(item.get("confidence", 0.0)) < 0.85,
    } for item in relationships]
    return {
        "schema_version": "catia-overlay.v0.8", "coordinate_space": "WORLD_MM",
        "layers": {"centerlines": centerlines, "terminals": terminals,
                   "relationships": relation_records},
        "display_policy": {
            "source_model_modified": False,
            "overlay_is_separate_component": True,
            "low_confidence_relationships_require_review_label": True,
        },
    }
