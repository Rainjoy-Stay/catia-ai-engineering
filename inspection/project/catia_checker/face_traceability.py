"""Bind exact OCCT faces to a CATIA Body only after one-Body/one-Solid validation."""
from __future__ import annotations
from typing import Any


def bind_single_body_faces(manifest: dict[str, Any], body: dict[str, Any]) -> dict[str, Any]:
    roots = [x for x in manifest.get("shapes", []) if x.get("shape_id") == "STEP_ROOT"]
    solid_count = int(roots[0].get("solid_count") or 0) if len(roots) == 1 else 0
    faces = [dict(x) for x in manifest.get("shapes", [])
             if str(x.get("shape_id") or "").startswith("STEP_FACE_")]
    if solid_count != 1:
        return {"faces": [], "coverage_complete": False,
                "error": {"code": "BODY_SOLID_MAPPING_COUNT_MISMATCH",
                          "source_body_index": body.get("source_body_index"),
                          "expected_solid_count": 1, "actual_solid_count": solid_count}}
    for face in faces:
        face.update({"face_id": f"BODY_{int(body['source_body_index']):06d}::{face['shape_id']}",
                     "source_body_index": int(body["source_body_index"]),
                     "source_body_name": str(body["source_body_name"]),
                     "mapping_method": "SINGLE_BODY_EXPORT_ONE_SOLID_VERIFIED",
                     "exact_brep": True, "mesh_used": False})
    return {"faces": faces, "coverage_complete": True, "error": None}
