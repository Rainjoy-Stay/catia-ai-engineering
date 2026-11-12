"""Snapshot-local identity, instance coordinates, coverage and grounded queries.

Input is a normalized observation, not an assertion that CATIA was fully read.
Missing transforms, missing children and unsupported geometry remain unknown.
"""
from __future__ import annotations

import hashlib
import json
import math
from copy import deepcopy
from typing import Any

IDENTITY = [1., 0., 0., 0., 0., 1., 0., 0., 0., 0., 1., 0., 0., 0., 0., 1.]
SCHEMA = "catia-understanding.snapshot.v1"


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    allow_nan=False).encode("utf-8")).hexdigest()


def matrix(value: Any) -> list[float] | None:
    if value is None:
        return None
    if not isinstance(value, (list, tuple)) or len(value) != 16:
        raise ValueError("Transform must be a row-major 4x4 matrix")
    values = [float(x) for x in value]
    if not all(math.isfinite(x) for x in values):
        raise ValueError("Non-finite transform")
    if any(abs(a-b) > 1e-9 for a, b in zip(values[12:], [0, 0, 0, 1])):
        raise ValueError("Transform must be affine")
    # CATIA assembly placement must be rigid, with no scale or reflection.
    axes = [[values[r*4+c] for r in range(3)] for c in range(3)]
    for i in range(3):
        for j in range(3):
            if abs(sum(a*b for a, b in zip(axes[i], axes[j])) - (i == j)) > 1e-6:
                raise ValueError("Transform must be rigid")
    a, b, c = axes
    determinant = (a[0]*(b[1]*c[2]-b[2]*c[1]) - b[0]*(a[1]*c[2]-a[2]*c[1])
                   + c[0]*(a[1]*b[2]-a[2]*b[1]))
    if abs(determinant-1) > 1e-6:
        raise ValueError("Transform must preserve orientation")
    return values


def compose(parent: list[float] | None, local: list[float] | None) -> list[float] | None:
    if parent is None or local is None:
        return None
    return [sum(parent[r*4+k]*local[k*4+c] for k in range(4))
            for r in range(4) for c in range(4)]


def transform_point(snapshot: dict, object_id: str, point_mm: list[float]) -> dict:
    if len(point_mm) != 3 or not all(math.isfinite(float(x)) for x in point_mm):
        raise ValueError("point_mm must contain three finite millimetre coordinates")
    obj = snapshot["objects"][object_id]
    m = obj.get("world_transform")
    result = None if m is None else [sum(m[r*4+c]*float(point_mm[c]) for c in range(3))
                                    + m[r*4+3] for r in range(3)]
    return {"status": "KNOWN" if m is not None else "UNKNOWN",
            "snapshot_id": snapshot["snapshot_id"], "object_id": object_id,
            "coordinate_frame": "ROOT_PRODUCT", "unit": "mm", "point": result,
            "method": "RIGID_TRANSFORM_COMPOSITION", "evidence_refs": obj["evidence_refs"],
            "limitation": None if m is not None else "Instance transform chain is incomplete"}


def build_snapshot(observation: dict) -> dict:
    """Normalize observation while preserving every unknown and failed branch.

    Definition keys identify one reference within this observation only. Object IDs
    use instance ordinal paths within a content-addressed snapshot, not persistent
    CATIA names. Unknown units cannot be relabelled millimetres.
    """
    data = deepcopy(observation)
    if data.get("schema_version") != "catia-understanding.observation.v1":
        raise ValueError("Unsupported observation schema")
    if data.get("length_unit") != "mm":
        raise ValueError("Observation must explicitly normalize length to mm")
    if not isinstance(data.get("definitions"), dict) or not isinstance(data.get("root"), dict):
        raise ValueError("Observation requires definitions and root")
    sid = "SNAP_" + digest(data)[:24]
    objects, evidence, edges, issues = {}, {}, [], []
    coverage = {"occurrences_seen": 0, "child_collections_read": 0,
                "child_collections_unknown": 0, "children_expected_known": 0,
                "children_returned": 0, "children_missing": 0,
                "transforms_known": 0, "transforms_unknown": 0,
                "definitions_loaded": 0, "definitions_unavailable": 0,
                "occurrences_reference_unresolved": 0, "read_error_count": 0}
    definitions = {}
    for key, definition in data["definitions"].items():
        did = "DEF_" + digest(key)[:20]
        definitions[key] = did
        eid = "EVID_" + did
        evidence[eid] = {"source": data["source"], "record": f"definitions/{key}",
                         "method": definition.get("method", "OBSERVATION"),
                         "representation": "CATIA_STRUCTURE", "snapshot_id": sid}
        state = definition.get("read_status", "UNKNOWN")
        objects[did] = {"id": did, "kind": "PART_DEFINITION", "name": definition.get("name"),
                        "source_key": key, "read_status": state,
                        "bodies": definition.get("bodies", []),
                        "read_errors": definition.get("read_errors", []),
                        "bodies_expected": definition.get("bodies_expected"),
                        "hybrid_body_count": definition.get("hybrid_body_count"),
                        "geometry_scope": definition.get("geometry_scope", "NOT_READ"),
                        "evidence_refs": [eid]}
        coverage["definitions_loaded" if state == "READ" else "definitions_unavailable"] += 1
        coverage["read_error_count"] += len(definition.get("read_errors", [])) + sum(
            len(body.get("read_errors", [])) for body in definition.get("bodies", []))
    active_nodes: set[int] = set()

    def visit(node: dict, path: str, parent: str | None, parent_world: list | None,
              names: list[str]) -> str:
        if id(node) in active_nodes:
            raise ValueError("Observation contains a cyclic occurrence tree")
        active_nodes.add(id(node))
        oid, eid = "OCC_" + path.replace("/", "_"), "EVID_OCC_" + path.replace("/", "_")
        name = str(node.get("name", "UNNAMED"))
        local = matrix(node.get("local_transform"))
        if parent is None:
            # The root product defines the frame; this is not a guessed placement.
            local = list(IDENTITY)
        world = compose(parent_world, local)
        coverage["occurrences_seen"] += 1
        coverage["read_error_count"] += len(node.get("read_errors", []))
        if any(e.get("field") == "ReferenceProduct.Parent" for e in node.get("read_errors", [])):
            coverage["occurrences_reference_unresolved"] += 1
        coverage["transforms_known" if world is not None else "transforms_unknown"] += 1
        evidence[eid] = {"source": data["source"], "record": "root/"+path,
                         "method": node.get("method", "OBSERVATION"),
                         "snapshot_id": sid, "representation": "CATIA_STRUCTURE"}
        source_key = node.get("definition_key")
        definition_id = definitions.get(source_key)
        if source_key and definition_id is None:
            issues.append({"object_id": oid, "reason": "MISSING_DEFINITION_RECORD"})
        obj = {"id": oid, "kind": "OCCURRENCE", "name": name,
               "instance_path": names+[name], "ordinal_path": path, "parent_id": parent,
               "definition_id": definition_id, "local_transform": local, "world_transform": world,
               "transform_status": "KNOWN" if world is not None else "UNKNOWN",
               "read_errors": node.get("read_errors", []), "evidence_refs": [eid],
               "children": [], "part_number": node.get("part_number")}
        objects[oid] = obj
        if parent:
            edges.append({"type": "CONTAINS", "source": parent, "target": oid, "evidence_refs": [eid]})
        if definition_id:
            edges.append({"type": "INSTANCE_OF", "source": oid, "target": definition_id,
                          "evidence_refs": [eid]})
        children = node.get("children")
        expected = node.get("children_expected")
        count_known = isinstance(expected, int) and not isinstance(expected, bool) and expected >= 0
        returned = len(children) if isinstance(children, list) else 0
        coverage["children_returned"] += returned
        complete = count_known and isinstance(children, list) and expected == returned
        coverage["child_collections_read" if complete else "child_collections_unknown"] += 1
        obj["children_complete"] = complete
        if count_known:
            coverage["children_expected_known"] += expected
            coverage["children_missing"] += max(0, expected-returned)
        if not complete:
            issues.append({"object_id": oid, "reason": "CHILD_COLLECTION_INCOMPLETE_OR_UNKNOWN",
                           "expected": expected, "returned": returned})
        if isinstance(children, list):
            for index, child in enumerate(children, 1):
                # Original collection index is needed when a COM Item read failed.
                ordinal = child.get("collection_index", index)
                if not isinstance(ordinal, int) or isinstance(ordinal, bool) or ordinal < 1:
                    raise ValueError("Invalid collection index")
                child_id = "OCC_" + (path+"/"+str(ordinal)).replace("/", "_")
                if child_id in objects:
                    raise ValueError("Duplicate occurrence collection index")
                obj["children"].append(visit(child, path+"/"+str(ordinal), oid, world, names+[name]))
        active_nodes.remove(id(node))
        return oid

    root = visit(data["root"], "0", None, list(IDENTITY), [])
    coverage["read_error_count"] += len(data.get("source_state", {}).get("errors", []))
    return {"schema_version": SCHEMA, "snapshot_id": sid, "source": data["source"],
            "knowledge_level": "STRUCTURAL_BASELINE_ONLY",
            "identity_scope": "SNAPSHOT_LOCAL_ONLY", "length_unit": "mm",
            "coordinate_frame": "ROOT_PRODUCT", "root_id": root,
            "objects": objects, "relationships": edges, "evidence": evidence,
            "coverage": coverage, "issues": issues,
            "capabilities": {"structure": True, "instance_transforms": True,
                             "native_face_adjacency": False, "engineering_semantics": False},
            "limitations": ["Names and shape do not establish engineering function",
                            "Geometry and face/edge topology have not been read by this entrypoint",
                            "Snapshot IDs are not persistent CATIA topology references"],
            "source_state": data.get("source_state", {}),
            "read_scope": data.get("scope", {"status": "NOT_DECLARED"})}


def find_objects(snapshot: dict, text: str) -> dict:
    """Return candidates, never silently resolve duplicate names."""
    candidates = [o for o in snapshot["objects"].values() if o["kind"] == "OCCURRENCE"
                  and (text == o["id"] or text.casefold() in str(o["name"]).casefold()
                       or text.casefold() in str(o.get("part_number") or "").casefold())]
    return {"snapshot_id": snapshot["snapshot_id"], "query": text,
            "status": "UNIQUE" if len(candidates) == 1 else "AMBIGUOUS" if candidates else "NOT_FOUND",
            "candidates": [{k: o[k] for k in ("id", "name", "instance_path", "definition_id",
                                                "transform_status", "evidence_refs")} for o in candidates]}


def describe(snapshot: dict, object_id: str) -> dict:
    obj = snapshot["objects"][object_id]
    return {"snapshot_id": snapshot["snapshot_id"], "object": deepcopy(obj),
            "relationships": [e for e in snapshot["relationships"] if object_id in (e["source"], e["target"])],
            "evidence": {key: snapshot["evidence"][key] for key in obj["evidence_refs"]},
            "unknown": ["engineering_role", "system_membership", "contact", "native_face_adjacency"]}


def compare_snapshots(before: dict, after: dict) -> dict:
    """No guessed cross-version matching: changed snapshots invalidate old evidence."""
    same = before["snapshot_id"] == after["snapshot_id"]
    return {"before": before["snapshot_id"], "after": after["snapshot_id"],
            "status": "IDENTICAL" if same else "CHANGED_REQUIRES_REBINDING",
            "old_evidence_valid_for_after": same, "cross_version_object_mapping": "NOT_ESTABLISHED",
            "comparison_scope": "CAPTURED_STRUCTURE_AND_TRANSFORMS_ONLY",
            "geometry_change_detection": "UNAVAILABLE_GEOMETRY_NOT_CAPTURED"}
