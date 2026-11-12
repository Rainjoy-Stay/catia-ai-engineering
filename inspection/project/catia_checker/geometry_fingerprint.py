"""Conservative multi-feature geometry fingerprints and one-to-one mapping."""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Mapping, Sequence


DEFAULT_TOLERANCES = {
    "relative_volume": 1e-5,
    "relative_area": 1e-5,
    "centroid_mm": 1e-4,
    "bounds_mm": 1e-4,
}


def _vector(value: Any, count: int) -> list[float] | None:
    if not isinstance(value, (list, tuple)) or len(value) != count:
        return None
    result = [float(item) for item in value]
    return result if all(math.isfinite(item) for item in result) else None


def canonical_geometry_features(record: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize CATIA/OCCT Body, Solid, or Face measurements."""
    bounds = record.get("bounds_mm") or record.get("bounding_box_mm")
    if isinstance(bounds, Mapping):
        lower, upper = _vector(bounds.get("min"), 3), _vector(bounds.get("max"), 3)
        bounds6 = lower + upper if lower and upper else None
    else:
        bounds6 = _vector(bounds, 6)
    result: dict[str, Any] = {}
    for output, keys in {
        "volume_mm3": ("volume_mm3",),
        "area_mm2": ("surface_area_mm2", "area_mm2"),
    }.items():
        for key in keys:
            if record.get(key) is not None:
                value = float(record[key])
                if math.isfinite(value) and value >= 0:
                    result[output] = value
                break
    centroid = _vector(record.get("centroid_mm") or record.get("center_of_gravity_mm"), 3)
    if centroid is not None and record.get('centroid_verified') is not False:
        result["centroid_mm"] = centroid
    if bounds6 is not None:
        result["bounds_mm"] = bounds6
        result["dimensions_mm"] = [bounds6[i + 3] - bounds6[i] for i in range(3)]
    for key in ("face_count", "edge_count", "vertex_count"):
        if record.get(key) is not None:
            result[key] = int(record[key])
    surface_counts = record.get("surface_type_counts")
    if isinstance(surface_counts, Mapping):
        result["surface_type_counts"] = {str(k): int(v) for k, v in sorted(surface_counts.items())}
    return result


def geometry_fingerprint(record: Mapping[str, Any]) -> str:
    features = canonical_geometry_features(record)
    rounded = {}
    for key, value in features.items():
        if isinstance(value, list):
            rounded[key] = [round(float(item), 6) for item in value]
        elif isinstance(value, float):
            rounded[key] = round(value, 6)
        else:
            rounded[key] = value
    return hashlib.sha256(json.dumps(rounded, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _relative_delta(a: float, b: float) -> float:
    return abs(a - b) / max(abs(a), abs(b), 1e-12)


def compare_geometry_features(first: Mapping[str, Any], second: Mapping[str, Any],
                              tolerances: Mapping[str, float] | None = None) -> dict[str, Any]:
    limits = {**DEFAULT_TOLERANCES, **dict(tolerances or {})}
    a, b = canonical_geometry_features(first), canonical_geometry_features(second)
    checks, score = [], 0.0
    for key, tolerance_key in (("volume_mm3", "relative_volume"), ("area_mm2", "relative_area")):
        if key in a and key in b:
            delta = _relative_delta(a[key], b[key]); limit = float(limits[tolerance_key])
            checks.append({"feature": key, "delta": delta, "limit": limit, "match": delta <= limit})
            score += delta / max(limit, 1e-15)
    for key, tolerance_key in (("centroid_mm", "centroid_mm"), ("dimensions_mm", "bounds_mm"),
                                ("bounds_mm", "bounds_mm")):
        if key in a and key in b:
            delta = max(abs(x - y) for x, y in zip(a[key], b[key])); limit = float(limits[tolerance_key])
            checks.append({"feature": key, "delta": delta, "limit": limit, "match": delta <= limit})
            score += delta / max(limit, 1e-15)
    for key in ("face_count", "edge_count", "vertex_count", "surface_type_counts"):
        if key in a and key in b:
            equal = a[key] == b[key]
            checks.append({"feature": key, "delta": 0 if equal else 1, "limit": 0, "match": equal})
            score += 0 if equal else 1e6
    spatial = any(item['feature'] in ('centroid_mm', 'bounds_mm') for item in checks)
    return {"compatible": len(checks) >= 2 and spatial and all(item["match"] for item in checks),
            "score": score, "checks": checks, "compared_feature_count": len(checks)}


def match_geometry_records(sources: Sequence[Mapping[str, Any]],
                           targets: Sequence[Mapping[str, Any]], *,
                           source_id: str = "shape_id", target_id: str = "body_index",
                           tolerances: Mapping[str, float] | None = None) -> dict[str, Any]:
    """Return only unambiguous one-to-one matches; repeated geometry stays unresolved."""
    candidates: dict[str, list[dict[str, Any]]] = {}
    target_lookup = {str(item[target_id]): item for item in targets}
    for source in sources:
        sid = str(source[source_id]); options = []
        for target in targets:
            result = compare_geometry_features(source, target, tolerances)
            if result["compatible"]:
                options.append({"target_id": str(target[target_id]), **result})
        candidates[sid] = sorted(options, key=lambda item: (item["score"], item["target_id"]))
    assigned, used = [], set()
    pending = {str(item[source_id]): item for item in sources}
    changed = True
    while changed:
        changed = False
        for sid in list(pending):
            available = [item for item in candidates[sid] if item["target_id"] not in used]
            if len(available) == 1:
                contenders = [other for other in pending if any(
                    option['target_id'] == available[0]['target_id']
                    for option in candidates[other] if option['target_id'] not in used)]
                if len(contenders) != 1:
                    continue
                selected = available[0]; used.add(selected["target_id"]); pending.pop(sid)
                assigned.append({"source_id": sid, "target_id": selected["target_id"],
                                 "score": selected["score"], "checks": selected["checks"],
                                 "mapping_method": "MULTI_FEATURE_EXACT_ONE_TO_ONE"})
                changed = True
    unresolved = []
    for sid in pending:
        available = [item["target_id"] for item in candidates[sid] if item["target_id"] not in used]
        unresolved.append({"source_id": sid, "candidate_target_ids": available,
                           "reason": "NO_COMPATIBLE_TARGET" if not available else "AMBIGUOUS_REPEATED_GEOMETRY"})
    return {"matches": sorted(assigned, key=lambda item: item["source_id"]),
            "unresolved": unresolved, "is_complete": not unresolved,
            "source_count": len(sources), "target_count": len(targets),
            "matched_count": len(assigned), "target_records": target_lookup}


def match_geometry_records_with_labels(
        sources: Sequence[Mapping[str, Any]], targets: Sequence[Mapping[str, Any]], *,
        source_id: str = "shape_id", target_id: str = "body_index",
        source_label: str = "source_name", target_label: str = "source_body_name",
        label_volume_tolerance: float = 1e-3,
        tolerances: Mapping[str, float] | None = None) -> dict[str, Any]:
    """Use labels only as candidates; verify complete geometry including location.

    Equal-volume repeated solids exposed unsafe legacy label assignments.
    Missing or conflicting spatial evidence must stay unresolved.
    """
    source_labels: dict[str, list[Mapping[str, Any]]] = {}
    target_labels: dict[str, list[Mapping[str, Any]]] = {}
    for item in sources:
        label = str(item.get(source_label) or "").strip()
        if label: source_labels.setdefault(label, []).append(item)
    for item in targets:
        label = str(item.get(target_label) or "").strip()
        if label: target_labels.setdefault(label, []).append(item)
    matches, used_sources, used_targets = [], set(), set()
    rejected_labels = []
    for label in sorted(set(source_labels) & set(target_labels)):
        left, right = source_labels[label], target_labels[label]
        if len(left) != 1 or len(right) != 1:
            rejected_labels.append({"label": label, "reason": "NON_UNIQUE_LABEL"})
            continue
        source, target = left[0], right[0]
        a = canonical_geometry_features(source).get("volume_mm3")
        b = canonical_geometry_features(target).get("volume_mm3")
        if a is None or b is None or _relative_delta(a, b) > label_volume_tolerance:
            rejected_labels.append({"label": label, "reason": "VOLUME_VERIFICATION_FAILED",
                                    "source_volume_mm3": a, "target_volume_mm3": b})
            continue
        sid, tid = str(source[source_id]), str(target[target_id])
        comparison = compare_geometry_features(source, target, tolerances)
        if not comparison['compatible']:
            rejected_labels.append({'label': label, 'reason': 'SPATIAL_MULTI_FEATURE_VERIFICATION_FAILED',
                                    'comparison': comparison})
            continue
        target_options = [item for item in targets
                          if compare_geometry_features(source, item, tolerances)['compatible']]
        source_options = [item for item in sources
                          if compare_geometry_features(item, target, tolerances)['compatible']]
        if len(target_options) != 1 or len(source_options) != 1:
            rejected_labels.append({'label': label, 'reason': 'AMBIGUOUS_GEOMETRY_DESPITE_LABEL'})
            continue
        used_sources.add(sid); used_targets.add(tid)
        matches.append({"source_id": sid, "target_id": tid,
                        "score": _relative_delta(a, b),
                        "checks": [{"feature": "stable_source_label", "match": True,
                                    "value": label},
                                   {"feature": "volume_mm3", "match": True,
                                    "delta": _relative_delta(a, b),
                                    "limit": label_volume_tolerance}] + comparison['checks'],
                        "mapping_method": "STABLE_SOURCE_LABEL_SPATIAL_MULTI_FEATURE_VERIFIED"})
    remaining_sources = [item for item in sources if str(item[source_id]) not in used_sources]
    remaining_targets = [item for item in targets if str(item[target_id]) not in used_targets]
    geometric = match_geometry_records(remaining_sources, remaining_targets,
                                       source_id=source_id, target_id=target_id,
                                       tolerances=tolerances)
    matches.extend(geometric["matches"])
    unresolved = geometric["unresolved"]
    return {"matches": sorted(matches, key=lambda item: item["source_id"]),
            "unresolved": unresolved, "is_complete": not unresolved,
            "source_count": len(sources), "target_count": len(targets),
            "matched_count": len(matches), "rejected_labels": rejected_labels,
            "target_records": {str(item[target_id]): item for item in targets}}
