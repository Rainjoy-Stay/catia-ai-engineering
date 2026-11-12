"""Conservative engineering-object classification from validated evidence."""

from __future__ import annotations

from typing import Any, Iterable, Mapping


OBJECT_TYPES = {"PIPE", "FITTING", "FLANGE", "CLAMP", "BRACKET",
                "CASE_STRUCTURE", "OTHER", "UNKNOWN"}


def _deterministic_interface_type(body: Mapping[str, Any]) -> tuple[str, float, list[str]] | None:
    """Recognize only strong, name-independent flange/fitting geometry."""
    statistics = body.get("surface_statistics") or {}
    counts = statistics.get("surface_type_counts") or {}
    bounds = body.get("reference_bounds_mm")
    if not bounds:
        return None
    dimensions = sorted(abs(float(bounds[index + 3]) - float(bounds[index])) for index in range(3))
    if not dimensions[-1]:
        return None
    disk_thickness_ratio = dimensions[0] / dimensions[-1]
    disk_diameter_similarity = dimensions[1] / dimensions[-1]
    if (counts.get("PLANE", 0) >= 2 and counts.get("CYLINDER", 0) >= 1 and
            counts.get("CONE", 0) >= 1 and disk_thickness_ratio <= 0.5 and
            disk_diameter_similarity >= 0.8):
        return "FLANGE", 0.9, [
            f"disk_thickness_ratio={disk_thickness_ratio:.6g}",
            f"disk_diameter_similarity={disk_diameter_similarity:.6g}",
            f"plane_faces={counts.get('PLANE', 0)}",
            f"cylindrical_faces={counts.get('CYLINDER', 0)}",
            f"conical_faces={counts.get('CONE', 0)}",
        ]
    if counts.get("TORUS", 0) >= 1 and counts.get("PLANE", 0) >= 2:
        return "FITTING", 0.92, [
            f"toroidal_faces={counts.get('TORUS', 0)}",
            f"terminal_planar_faces={counts.get('PLANE', 0)}",
        ]
    return None


def classify_engineering_objects(bodies: Iterable[Mapping[str, Any]],
                                 pipe_scores: Mapping[str, Mapping[str, Any]],
                                 support_relationships: Iterable[Mapping[str, Any]],
                                 connection_relationships: Iterable[Mapping[str, Any]] = ()) -> list[dict[str, Any]]:
    supports = list(support_relationships)
    connected_interface_ids = set()
    for edge in connection_relationships:
        if edge.get("relationship_type") not in {"DIRECT_INTERFACE", "CONNECTED"}:
            continue
        connected_interface_ids.update((edge.get("source_object_id"), edge.get("target_object_id")))
    pipe_ids = {body_id for body_id, score in pipe_scores.items()
                if score.get("candidate_type") == "PIPE"}
    connected_interface_ids -= pipe_ids
    results = []
    for body in bodies:
        body_id = body["source_id"]
        pipe = pipe_scores.get(body_id, {})
        support_evidence = [item for item in supports if item["support_body_id"] == body_id]
        if pipe.get("candidate_type") == "PIPE":
            object_type, confidence, source = "PIPE", pipe.get("confidence", 0.0), pipe.get("classifier")
            evidence = list(pipe.get("evidence", ()))
            uncertainty = list(pipe.get("uncertainty", ()))
        elif support_evidence:
            confidence = max(float(item["confidence"]) for item in support_evidence)
            types = {item.get("object_type_candidate") for item in support_evidence}
            object_type = "CLAMP" if "CLAMP" in types else "BRACKET" if types == {"BRACKET"} else "UNKNOWN"
            source = "DETERMINISTIC_GEOMETRY_V0.5"
            evidence = [item["evidence"] for item in support_evidence]
            uncertainty = ["Clamp-like support geometry found; load path to a bracket is not yet proven"]
        elif body_id in connected_interface_ids and (interface := _deterministic_interface_type(body)):
            object_type, confidence, evidence = interface
            source = "DETERMINISTIC_INTERFACE_GEOMETRY_V1.2"
            uncertainty = []
        else:
            object_type, confidence, source = "UNKNOWN", 0.0, "CONSERVATIVE_FALLBACK"
            evidence, uncertainty = [], ["No qualified PIPE or mid-span enclosure evidence"]
        results.append({
            "object_id": body_id, "source_body_ids": [body_id], "object_type": object_type,
            "confidence": confidence, "classification_source": source,
            "evidence": evidence, "uncertainty": uncertainty,
            "metadata": {"product_name": body.get("product_name"),
                         "source_name": body.get("source_name")}, "verified": False,
        })
    return results
