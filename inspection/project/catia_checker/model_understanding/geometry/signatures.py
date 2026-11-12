"""Deterministic dumb-model body signatures independent of STEP entity numbers."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping


def body_geometry_signature(body: Mapping[str, Any]) -> str:
    bounds = body.get("reference_bounds_mm")
    dimensions = sorted(round(float(bounds[i + 3] - bounds[i]), 4) for i in range(3)) if bounds else []
    tubular = body.get("tubular_features", {})
    payload = {
        "geometry_kind": body.get("geometry_kind"),
        "closure_state": body.get("closure_state"),
        "dimensions_mm_sorted": dimensions,
        "surface_type_counts": body.get("surface_statistics", {}).get("surface_type_counts", {}),
        "radius_clusters_mm": sorted(round(float(item["radius"]), 4)
                                     for item in tubular.get("radius_clusters", ())),
        "face_count": len(body.get("face_ids", ())),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def stable_body_id(body: Mapping[str, Any]) -> str:
    product = str(body.get("product_name") or "UNNAMED").strip().casefold()
    matrix = (body.get("assembly_transform") or {}).get("matrix")
    placement = ([round(float(value), 6) for row in matrix for value in row] if matrix else "LOCAL")
    digest = hashlib.sha256(f"{product}|{body_geometry_signature(body)}|{placement}".encode("utf-8")).hexdigest()[:16]
    return f"BODY_{digest.upper()}"
