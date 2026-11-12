"""Recover a circular-sweep centerline from antipodal B-spline seam edges.

This is intentionally conservative: it only evaluates a solid when two long
edges are paired by equal parameter ranges and both end separations agree with
the diameter derived from equal planar circular caps.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from OCP.BRep import BRep_Builder
from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.BRepTools import BRepTools
from OCP.GCPnts import GCPnts_AbscissaPoint
from OCP.TopAbs import TopAbs_EDGE
from OCP.TopExp import TopExp
from OCP.TopTools import TopTools_IndexedMapOfShape
from OCP.TopoDS import TopoDS, TopoDS_Shape
from OCP.gp import gp_Pnt, gp_Vec


def _distance(a, b):
    return math.dist((a.X(), a.Y(), a.Z()), (b.X(), b.Y(), b.Z()))


def evaluate(brep: Path, body_index: int, cap_area_mm2: float, standard: dict) -> dict:
    shape = TopoDS_Shape()
    if not BRepTools.Read_s(shape, str(brep.resolve()), BRep_Builder()):
        raise RuntimeError(f"Cannot read {brep}")
    edges = TopTools_IndexedMapOfShape()
    TopExp.MapShapes_s(shape, TopAbs_EDGE, edges)
    curves = []
    for i in range(1, edges.Extent() + 1):
        curve = BRepAdaptor_Curve(TopoDS.Edge_s(edges.FindKey(i)))
        first, last = curve.FirstParameter(), curve.LastParameter()
        curves.append((GCPnts_AbscissaPoint.Length_s(curve, first, last), curve, first, last))
    if len(curves) != 6:
        return {"body_index": body_index, "status": "NOT_EVALUATED", "reason": "EXPECTED_SIX_UNIQUE_EDGES"}
    (length_a, curve_a, first_a, last_a), (length_b, curve_b, first_b, last_b) = sorted(curves, reverse=True, key=lambda x: x[0])[:2]
    diameter = 2.0 * math.sqrt(cap_area_mm2 / math.pi)
    a0, a1 = curve_a.Value(first_a), curve_a.Value(last_a)
    b0, b1 = curve_b.Value(first_b), curve_b.Value(last_b)
    reverse_b = _distance(a0, b1) + _distance(a1, b0) < _distance(a0, b0) + _distance(a1, b1)
    end_separations = [_distance(a0, b1 if reverse_b else b0), _distance(a1, b0 if reverse_b else b1)]
    if max(abs(value - diameter) for value in end_separations) > max(0.01, 0.03 * diameter):
        return {"body_index": body_index, "status": "NOT_EVALUATED", "reason": "ANTIPODAL_EDGE_PAIR_NOT_CONFIRMED"}
    radii = []
    samples = 2001
    for index in range(1, samples - 1):
        fraction = index / (samples - 1)
        ua = first_a + (last_a - first_a) * fraction
        ub = (last_b - (last_b - first_b) * fraction) if reverse_b else (first_b + (last_b - first_b) * fraction)
        pa, da1, da2, pb, db1, db2 = gp_Pnt(), gp_Vec(), gp_Vec(), gp_Pnt(), gp_Vec(), gp_Vec()
        curve_a.D2(ua, pa, da1, da2)
        curve_b.D2(ub, pb, db1, db2)
        d1 = ((da1.X()+db1.X())/2, (da1.Y()+db1.Y())/2, (da1.Z()+db1.Z())/2)
        d2 = ((da2.X()+db2.X())/2, (da2.Y()+db2.Y())/2, (da2.Z()+db2.Z())/2)
        cross = (d1[1]*d2[2]-d1[2]*d2[1], d1[2]*d2[0]-d1[0]*d2[2], d1[0]*d2[1]-d1[1]*d2[0])
        denominator = math.sqrt(sum(value*value for value in cross))
        if denominator > 1e-12:
            radii.append(((sum(value*value for value in d1)) ** 1.5 / denominator, fraction))
    if not radii:
        return {"body_index": body_index, "status": "NOT_EVALUATED", "reason": "CENTERLINE_CURVATURE_UNAVAILABLE"}
    minimum_radius, location = min(radii)
    ratio = minimum_radius / diameter
    minimum = float(standard["minimum_bend_radius_ratio_r_over_d"])
    series = [float(x) for x in standard["standard_radius_ratios_r_over_d"]]
    preferred = [float(x) for x in standard["preferred_bend_radius_ratios_r_over_d"]]
    nearest = min(series, key=lambda value: abs(value-ratio))
    series_relative_error = abs(ratio-nearest)/nearest
    return {
        "body_index": body_index,
        "status": "PASS" if ratio >= minimum else "FAIL",
        "minimum_requirement": f"R/DN >= {minimum:g}",
        "nominal_outer_diameter_candidate_mm": diameter,
        "minimum_centerline_bend_radius_mm": minimum_radius,
        "minimum_radius_ratio_r_over_dn": ratio,
        "minimum_curvature_location_fraction": location,
        "centerline_length_estimate_mm": (length_a + length_b) / 2,
        "end_antipodal_separations_mm": end_separations,
        "nearest_standard_ratio": nearest,
        "within_standard_series_tolerance_2pct": series_relative_error <= 0.02,
        "preferred_ratio": any(abs(ratio-x)/x <= 0.02 for x in preferred),
        "series_review": "PASS_STANDARD_SERIES" if series_relative_error <= 0.02 else "REVIEW_NONSTANDARD_RATIO",
        "method": "MIDPOINT_OF_CONFIRMED_ANTIPODAL_BSPLINE_SEAM_EDGES_D2_CURVATURE",
        "engineering_pipe_confirmed": False,
        "design_cavity_confirmed": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--brep-dir", type=Path, required=True)
    parser.add_argument("--standard", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    standard = json.loads(args.standard.read_text(encoding="utf-8"))
    cap_areas = {840: 0.1772458945935533, 841: 0.1964}
    results = [evaluate(args.brep_dir / f"BODY_{body:06d}_SOLID_0001.brep", body, area, standard) for body, area in cap_areas.items()]
    payload = {
        "schema_version": "hb-4-55-2002-local-trial.v1",
        "standard_id": standard["standard_id"],
        "standard_document": standard["source"]["document"],
        "standard_document_sha256": standard["source"]["document_sha256"],
        "geometry_source": "CATIA_SINGLE_BODY_STEP_EXPORT_DERIVED_FROM_ACTIVE_IMPORTED_CATPART",
        "results": results,
        "overall_status": "FAIL" if any(x["status"] == "FAIL" for x in results) else ("NOT_EVALUATED" if any(x["status"] == "NOT_EVALUATED" for x in results) else "PASS"),
        "limitations": ["STEP has no confirmed cavity", "material, pressure, wall thickness and forming process are unavailable", "standard-series mismatch is retained for review rather than converted to a minimum-radius failure"],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
