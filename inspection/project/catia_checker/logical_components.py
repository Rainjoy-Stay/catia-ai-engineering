"""Conservative recovery of geometry patches from flat STEP/IGES Faces."""

from __future__ import annotations

import hashlib
from collections import Counter
import math
from typing import Any, Iterable, Mapping


def _engineering_hypothesis(members: list[str], records: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    features = [records[item].get("surface_features") for item in members]
    features = [item for item in features if isinstance(item, dict)]
    types = Counter(str(item.get("surface_type") or "UNKNOWN") for item in features)
    cylinders = [item for item in features if item.get("surface_type") == "CYLINDER"]
    tori = [item for item in features if item.get("surface_type") == "TORUS"]
    radii = sorted(float(item["radius_mm"]) for item in cylinders if item.get("radius_mm") is not None)
    if tori:
        minor_radii = sorted(float(item["minor_radius_mm"]) for item in tori
                             if item.get("minor_radius_mm") is not None)
        return {"engineering_object_type": "PIPE_BEND_CANDIDATE", "confidence": 0.9,
                "representative_radius_mm": (minor_radii[len(minor_radii) // 2]
                                             if minor_radii else None),
                "basis": ["ANALYTIC_TORUS", "CONTINUOUS_FACE_PATCH"],
                "surface_type_counts": dict(types)}
    if cylinders:
        median = radii[len(radii) // 2] if radii else None
        return {"engineering_object_type": "TUBULAR_COMPONENT_CANDIDATE", "confidence": 0.82,
                "candidate_roles": ["PIPE", "NOZZLE", "VESSEL_SHELL"],
                "representative_radius_mm": median,
                "axis_origins_mm": [item["axis_origin_mm"] for item in cylinders
                                    if item.get("axis_origin_mm")],
                "axis_directions": [item["axis_direction"] for item in cylinders
                                    if item.get("axis_direction")],
                "basis": ["ANALYTIC_CYLINDER", "CONTINUOUS_FACE_PATCH"],
                "surface_type_counts": dict(types)}
    if types and set(types) == {"PLANE"}:
        return {"engineering_object_type": "PLANAR_BOUNDARY_CANDIDATE", "confidence": 0.7,
                "basis": ["ANALYTIC_PLANE"], "surface_type_counts": dict(types)}
    return {"engineering_object_type": "UNRESOLVED", "confidence": 0.0,
            "basis": ["INSUFFICIENT_ANALYTIC_FEATURES"], "surface_type_counts": dict(types)}


def recover_logical_components(shapes: Iterable[Mapping[str, Any]],
                               pair_facts: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Group only smooth, shared-boundary Faces; plain contact is insufficient."""
    face_records = {str(item["shape_id"]): dict(item) for item in shapes
                    if int(item.get("face_count") or 0) == 1}
    ids = sorted(face_records)
    parent = {item: item for item in ids}

    def find(item: str) -> str:
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    def union(first: str, second: str) -> None:
        a, b = find(first), find(second)
        if a != b:
            parent[b] = a

    accepted_edges = []
    unresolved_contacts = []
    for raw in pair_facts:
        first, second = str(raw.get("object_a")), str(raw.get("object_b"))
        if first not in face_records or second not in face_records:
            continue
        if raw.get("boundary_contact") and raw.get("continuous_surface_contact"):
            union(first, second)
            accepted_edges.append({"face_a": first, "face_b": second,
                                   "basis": "SHARED_BOUNDARY_AND_G1_NORMAL_CONTINUITY",
                                   "minimum_abs_normal_alignment": raw.get("minimum_abs_normal_alignment")})
        elif raw.get("boundary_contact"):
            unresolved_contacts.append({"face_a": first, "face_b": second,
                                        "reason": "CONTACT_WITHOUT_SMOOTH_CONTINUITY"})

    groups: dict[str, list[str]] = {}
    for item in ids:
        groups.setdefault(find(item), []).append(item)
    components = []
    face_to_component = {}
    for members in groups.values():
        members.sort()
        digest = hashlib.sha256("|".join(members).encode()).hexdigest()[:10].upper()
        component_id = f"LGC-{digest}"
        bounds = [face_records[item].get("bounds_mm") for item in members]
        bounds = [item for item in bounds if isinstance(item, dict)]
        combined = None if not bounds else {
            "min": [min(float(item["min"][axis]) for item in bounds) for axis in range(3)],
            "max": [max(float(item["max"][axis]) for item in bounds) for axis in range(3)],
        }
        for face_id in members:
            face_to_component[face_id] = component_id
        hypothesis = _engineering_hypothesis(members, face_records)
        components.append({"logical_component_id": component_id,
                           "geometry_role": "CONTINUOUS_FACE_PATCH",
                           "face_count": len(members), "face_ids": members,
                           "bounds_mm": combined,
                           **hypothesis,
                           "semantic_status": ("CANDIDATE" if hypothesis["confidence"] > 0
                                               else "REVIEW")})
    components.sort(key=lambda item: item["logical_component_id"])
    return {"schema_version": "logical-components.v1.0", "face_count": len(ids),
            "component_count": len(components), "components": components,
            "face_to_component": face_to_component,
            "accepted_continuity_edge_count": len(accepted_edges),
            "accepted_continuity_edges": accepted_edges,
            "unresolved_contact_count": len(unresolved_contacts),
            "unresolved_contacts": unresolved_contacts,
            "typed_candidate_count": sum(
                item["engineering_object_type"] != "UNRESOLVED" for item in components),
            "policy": "CONSERVATIVE_G1_FACE_PATCH_RECOVERY",
            "mesh_used": False}


def _parallel(first: list[float], second: list[float], degrees: float = 1.0) -> bool:
    return abs(sum(a * b for a, b in zip(first, second))) >= math.cos(math.radians(degrees))


def _line_distance(origin_a: list[float], direction: list[float], origin_b: list[float]) -> float:
    delta = [b - a for a, b in zip(origin_a, origin_b)]
    projection = sum(value * axis for value, axis in zip(delta, direction))
    radial = [value - projection * axis for value, axis in zip(delta, direction)]
    return math.sqrt(sum(value * value for value in radial))


def assemble_pipe_logical_components(logical: Mapping[str, Any],
                                     pair_facts: Iterable[Mapping[str, Any]], *,
                                     radius_tolerance_mm: float = 0.5,
                                     radius_relative_tolerance: float = 0.02) -> dict[str, Any]:
    """Join tubular patches using exact contact, radius and axis evidence."""
    facts = [dict(item) for item in pair_facts]
    components = {item["logical_component_id"]: dict(item)
                  for item in logical.get("components", [])}
    face_map = dict(logical.get("face_to_component") or {})
    eligible = {key for key, item in components.items()
                if item.get("engineering_object_type") in
                {"TUBULAR_COMPONENT_CANDIDATE", "PIPE_BEND_CANDIDATE"}}
    parent = {item: item for item in eligible}

    def find(item: str) -> str:
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    accepted, rejected = [], []
    contact_neighbors: dict[str, set[str]] = {}
    for fact in facts:
        if not (fact.get("boundary_contact") or fact.get("intersection_type") == "CONTACT"):
            continue
        first = face_map.get(str(fact.get("object_a")))
        second = face_map.get(str(fact.get("object_b")))
        if first and second and first != second:
            contact_neighbors.setdefault(first, set()).add(second)
            contact_neighbors.setdefault(second, set()).add(first)
    # A planar patch may be the trimmed transition between a straight cylinder
    # and a torus. Admit it only when it bridges exactly two radius-compatible
    # tubular candidates; arbitrary flanges and multi-way junctions stay out.
    for planar, neighbors in contact_neighbors.items():
        if components.get(planar, {}).get("engineering_object_type") != "PLANAR_BOUNDARY_CANDIDATE":
            continue
        tube_neighbors = sorted(item for item in neighbors if item in eligible)
        if len(tube_neighbors) != 2:
            continue
        first, second = tube_neighbors
        ra = components[first].get("representative_radius_mm")
        rb = components[second].get("representative_radius_mm")
        if ra is None or rb is None:
            continue
        limit = max(float(radius_tolerance_mm),
                    max(float(ra), float(rb)) * float(radius_relative_tolerance))
        if abs(float(ra) - float(rb)) > limit:
            continue
        parent[planar] = planar
        parent[find(first)] = planar
        parent[find(second)] = planar
        accepted.append({"component_a": first, "connector_component": planar,
                         "component_b": second,
                         "basis": "PLANAR_TRANSITION_BETWEEN_TWO_RADIUS_MATCHED_TUBULAR_PATCHES",
                         "radius_difference_mm": abs(float(ra) - float(rb))})
    for fact in facts:
        if not (fact.get("boundary_contact") or fact.get("intersection_type") == "CONTACT"):
            continue
        first = face_map.get(str(fact.get("object_a")))
        second = face_map.get(str(fact.get("object_b")))
        if not first or not second or first == second or first not in eligible or second not in eligible:
            continue
        a, b = components[first], components[second]
        ra, rb = a.get("representative_radius_mm"), b.get("representative_radius_mm")
        if ra is None or rb is None:
            rejected.append({"component_a": first, "component_b": second,
                             "reason": "MISSING_RADIUS"})
            continue
        radius_limit = max(float(radius_tolerance_mm),
                           max(float(ra), float(rb)) * float(radius_relative_tolerance))
        if abs(float(ra) - float(rb)) > radius_limit:
            rejected.append({"component_a": first, "component_b": second,
                             "reason": "RADIUS_MISMATCH"})
            continue
        bend_connection = "PIPE_BEND_CANDIDATE" in {
            a.get("engineering_object_type"), b.get("engineering_object_type")}
        axes_ok = bend_connection
        if not bend_connection:
            origins_a, origins_b = a.get("axis_origins_mm") or [], b.get("axis_origins_mm") or []
            directions_a, directions_b = a.get("axis_directions") or [], b.get("axis_directions") or []
            axes_ok = any(_parallel(da, db) and
                          _line_distance(oa, da, ob) <= radius_limit
                          for oa in origins_a for da in directions_a
                          for ob in origins_b for db in directions_b)
        if not axes_ok:
            rejected.append({"component_a": first, "component_b": second,
                             "reason": "AXIS_NOT_CONTINUOUS"})
            continue
        root_a, root_b = find(first), find(second)
        if root_a != root_b:
            parent[root_b] = root_a
        accepted.append({"component_a": first, "component_b": second,
                         "basis": "EXACT_CONTACT_RADIUS_AND_AXIS_CONTINUITY",
                         "radius_difference_mm": abs(float(ra) - float(rb))})
    groups: dict[str, list[str]] = {}
    for item in parent:
        groups.setdefault(find(item), []).append(item)
    runs = []
    for members in groups.values():
        members.sort()
        digest = hashlib.sha256("|".join(members).encode()).hexdigest()[:10].upper()
        has_bend = any(components[item]["engineering_object_type"] == "PIPE_BEND_CANDIDATE"
                       for item in members)
        confirmed = len(members) > 1
        runs.append({"logical_pipe_id": f"PIPE-LGC-{digest}",
                     "status": "CANDIDATE" if confirmed else "REVIEW",
                     "confidence": 0.88 if confirmed and has_bend else 0.82 if confirmed else 0.65,
                     "component_ids": members, "component_count": len(members),
                     "has_bend": has_bend,
                     "basis": ["ANALYTIC_RADIUS", "EXACT_BOUNDARY_CONTACT",
                               "AXIS_OR_BEND_CONTINUITY"] if confirmed else
                              ["ISOLATED_TUBULAR_PATCH"]})
    runs.sort(key=lambda item: item["logical_pipe_id"])
    return {"schema_version": "pipe-logical-components.v1.0",
            "pipe_candidate_count": len(runs), "joined_edge_count": len(accepted),
            "accepted_connections": accepted, "rejected_connection_count": len(rejected),
            "rejected_connections": rejected, "pipe_candidates": runs,
            "mesh_used": False}
