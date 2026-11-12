"""Pure orchestration for exact inspection of large multi-Body CATParts.

The caller supplies an exact B-Rep backend and its JSON manifest.  This module
never opens CATIA, exports a model, uses a mesh, or modifies source geometry.
"""

from __future__ import annotations

import hashlib
import math
from typing import Any, Callable, Mapping, Protocol, Sequence


class ExactBackend(Protocol):
    def distance(self, first_id: str, second_id: str) -> Mapping[str, Any]: ...
    def common_volume(self, first_id: str, second_id: str) -> Mapping[str, Any]: ...


def _bounds(record: Mapping[str, Any]) -> tuple[float, float, float, float, float, float] | None:
    value = record.get("bounds_mm")
    if not isinstance(value, Mapping):
        return None
    minimum, maximum = value.get("min"), value.get("max")
    if not (isinstance(minimum, Sequence) and isinstance(maximum, Sequence)
            and len(minimum) == len(maximum) == 3):
        return None
    result = tuple(float(item) for item in (*minimum, *maximum))
    if (not all(math.isfinite(item) for item in result)
            or any(result[index] > result[index + 3] for index in range(3))):
        return None
    return result


def build_spatial_candidates(shapes: Sequence[Mapping[str, Any]], *,
                             margin_mm: float = 0.0) -> dict[str, Any]:
    """Sweep X and test Y/Z AABB overlap without all-pairs exact evaluation."""
    margin = float(margin_mm)
    if not math.isfinite(margin) or margin < 0:
        raise ValueError("margin_mm must be finite and non-negative")
    admitted, skipped = [], []
    for record in shapes:
        shape_id = str(record.get("shape_id") or "")
        bounds = _bounds(record)
        if not shape_id or bounds is None:
            skipped.append({"shape_id": shape_id or None, "reason": "MISSING_VALID_BOUNDS"})
            continue
        admitted.append({"shape_id": shape_id, "bounds": bounds})
    admitted.sort(key=lambda item: (item["bounds"][0], item["shape_id"]))
    active, pairs = [], []
    for current in admitted:
        c = current["bounds"]
        active = [item for item in active if item["bounds"][3] + margin >= c[0]]
        for other in active:
            o = other["bounds"]
            if (o[4] + margin >= c[1] and c[4] + margin >= o[1]
                    and o[5] + margin >= c[2] and c[5] + margin >= o[2]):
                pairs.append(tuple(sorted((other["shape_id"], current["shape_id"]))))
        active.append(current)
    pairs = sorted(set(pairs))
    return {
        "method": "AABB_SWEEP_AND_PRUNE", "shape_count": len(admitted),
        "total_possible_pairs": len(admitted) * (len(admitted) - 1) // 2,
        "candidate_pair_count": len(pairs), "pairs": [list(pair) for pair in pairs],
        "skipped": skipped, "mesh_used": False,
    }


def _issue_id(first: str, second: str) -> str:
    pair = "|".join(sorted((first, second)))
    return "SINGLEPART-" + hashlib.sha256(pair.encode()).hexdigest()[:12].upper()


def analyze_large_single_part(backend: ExactBackend, manifest: Mapping[str, Any], *,
                              broad_phase_margin_mm: float = 0.0,
                              contact_tolerance_mm: float = 1e-5,
                              interference_volume_tolerance_mm3: float = 1e-6,
                              clearance_review_mm: float = 0.0,
                              max_exact_pairs: int = 10000,
                              progress: Callable[[dict[str, Any]], None] | None = None,
                              progress_interval: int = 100) -> dict[str, Any]:
    """Inspect internal solid pairs using exact distance and common volume."""
    tolerances = (contact_tolerance_mm, interference_volume_tolerance_mm3,
                  clearance_review_mm)
    if any(not math.isfinite(float(value)) or float(value) < 0 for value in tolerances):
        raise ValueError("tolerances must be finite and non-negative")
    if isinstance(max_exact_pairs, bool) or max_exact_pairs < 1:
        raise ValueError("max_exact_pairs must be a positive integer")
    if isinstance(progress_interval, bool) or progress_interval < 1:
        raise ValueError("progress_interval must be a positive integer")
    root_id = str(manifest.get("root_shape_id") or "")
    shapes = [dict(item) for item in manifest.get("shapes", [])
              if isinstance(item, Mapping) and str(item.get("shape_id")) != root_id]
    solids = [item for item in shapes if int(item.get("solid_count") or 0) > 0]
    health = [{"shape_id": item.get("shape_id"), "status": "REVIEW",
               "code": "INVALID_BREP"}
              for item in shapes if item.get("valid") is False]
    health.extend({"shape_id": item.get("shape_id"), "status": "REVIEW",
                   "code": "OPEN_SHELL_OR_SURFACE"}
                  for item in shapes if int(item.get("solid_count") or 0) == 0)
    physical=[item for item in shapes if int(item.get('solid_count') or 0)>0 or item.get('geometry_kind') in ('SHELL','FACE','SURFACE') or int(item.get('face_count') or 0)>0]
    by_id={str(item['shape_id']):item for item in physical}
    broad = build_spatial_candidates(physical, margin_mm=broad_phase_margin_mm)
    selected = broad["pairs"][:max_exact_pairs]
    if progress:
        progress({"stage": "BROAD_PHASE_COMPLETE", "candidate_pairs": len(selected),
                  "candidate_pairs_total": broad["candidate_pair_count"]})
    findings, errors = [], []
    for index, (first, second) in enumerate(selected, 1):
        if progress:
            progress({"stage":"EXACT_PAIR_START","index":index,"total":len(selected),
                      "object_a":first,"object_b":second})
        try:
            distance = dict(backend.distance(first, second))
            gap = float(distance["minimum_distance_mm"])
            non_solid=any(int(by_id[name].get('solid_count') or 0)==0 for name in (first,second))
            if non_solid:
                surface=dict(backend.surface_pair_fact(first,second,
                    entity_a=by_id[first],entity_b=by_id[second]))
                code=('SURFACE_INTERSECTION' if surface.get('surface_intersection') else
                      'SURFACE_CONTACT' if gap<=contact_tolerance_mm else
                      'LOW_CLEARANCE' if clearance_review_mm>0 and gap<clearance_review_mm else 'SURFACE_CLEAR')
                findings.append({'issue_id':_issue_id(first,second),'object_a':first,'object_b':second,
                    'disposition':'PASS' if code=='SURFACE_CLEAR' else 'REVIEW','code':code,
                    'minimum_distance_mm':gap,'intersection_volume_mm3':None,
                    'distance_evidence':distance,'surface_evidence':surface,
                    'exact_brep':True,'mesh_used':False})
                if progress and (index % progress_interval==0 or index==len(selected)):
                    progress({'stage':'EXACT_PAIRS','completed':index,'total':len(selected),'errors':len(errors)})
                continue
            if gap > contact_tolerance_mm:
                common = {
                    "intersection_volume_mm3": 0.0,
                    "method": "DERIVED_ZERO_FROM_EXACT_POSITIVE_DISTANCE",
                    "exact_brep": True,
                    "boolean_computed": False,
                    "minimum_distance_mm": gap,
                    "distance_threshold_mm": contact_tolerance_mm,
                }
            else:
                common = dict(backend.common_volume(first, second))
                common.setdefault("boolean_computed", True)
            volume = float(common["intersection_volume_mm3"])
            if volume > interference_volume_tolerance_mm3:
                disposition, code = "FAIL", "INTERNAL_SOLID_INTERFERENCE"
            elif gap <= contact_tolerance_mm:
                disposition, code = "REVIEW", "SOLID_CONTACT"
            elif clearance_review_mm > 0 and gap < clearance_review_mm:
                disposition, code = "REVIEW", "LOW_CLEARANCE"
            else:
                disposition, code = "PASS", "CLEAR"
            findings.append({
                "issue_id": _issue_id(first, second), "object_a": first,
                "object_b": second, "disposition": disposition, "code": code,
                "minimum_distance_mm": gap, "intersection_volume_mm3": volume,
                "distance_evidence": distance, "common_volume_evidence": common,
                "exact_brep": True, "mesh_used": False,
            })
        except Exception as exc:
            errors.append({"object_a": first, "object_b": second,
                           "code": "EXACT_PAIR_TIMEOUT" if isinstance(exc,TimeoutError) else "EXACT_PAIR_EVALUATION_FAILED",
                           "error_type": type(exc).__name__})
        if progress and (index % progress_interval == 0 or index == len(selected)):
            progress({"stage": "EXACT_PAIRS", "completed": index,
                      "total": len(selected), "errors": len(errors)})
    truncated = broad["candidate_pair_count"] > len(selected)
    counts = {status: sum(item["disposition"] == status for item in findings)
              for status in ("PASS", "FAIL", "REVIEW")}
    return {
        "schema_version": "large-single-part-analysis.v1.0",
        "source_file": manifest.get("source_file"),
        "shape_count": len(shapes), "solid_count": len(solids),
        "shell_or_surface_count": len(shapes) - len(solids),
        "health_findings": health, "broad_phase": broad,
        "exact_pair_count": len(selected), "findings": findings,
        "disposition_counts": counts, "errors": errors,
        "truncated": truncated, "coverage_complete": not truncated and not errors and not broad['skipped'],
        "geometry_authority": "OCCT_EXACT_BREP", "mesh_used": False,
        "source_modified": False,
    }
