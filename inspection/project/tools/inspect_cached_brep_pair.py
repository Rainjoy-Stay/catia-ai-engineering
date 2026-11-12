"""Compute one exact pair from two independent OCCT BREP cache files."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
PROJECT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(PROJECT))
from catia_checker.occt_brep import OCCTBRepModel


def inspect_pair(model: OCCTBRepModel, *, first_id: str = "A", second_id: str = "B",
                 common_volume_distance_threshold_mm: float = 0.0) -> dict:
    """Evaluate a pair without running a Boolean common for a proven positive gap."""
    distance = model.distance(first_id, second_id)
    gap = float(distance["minimum_distance_mm"])
    threshold = max(0.0, float(common_volume_distance_threshold_mm))
    # Volume is undefined for a free surface/open shell. Never fabricate zero
    # overlap and allow it to masquerade as a solid-volume screening pass.
    from catia_checker.occt_brep import _count, TopAbs_SOLID
    kinds=['SOLID' if not isinstance(model,OCCTBRepModel) or _count(model._shape(identifier),TopAbs_SOLID)>0 else 'SURFACE'
           for identifier in (first_id,second_id)]
    if 'SURFACE' in kinds:
        surface=({**distance,'surface_intersection':False,'boundary_contact':False,
                  'method':'DERIVED_DISJOINT_FROM_EXACT_POSITIVE_DISTANCE','section_computed':False}
                 if gap>threshold else model.surface_pair_fact(first_id,second_id,
                    entity_a={'geometry_kind':kinds[0]},entity_b={'geometry_kind':kinds[1]}))
        return {'distance':distance,'surface':surface,'common':{
            'intersection_volume_mm3':None,'applicable':False,'exact_brep':True,
            'method':'NOT_APPLICABLE_NON_SOLID'},'geometry_kinds':kinds}
    if gap > threshold:
        common = {
            "intersection_volume_mm3": 0.0,
            "method": "DERIVED_ZERO_FROM_EXACT_POSITIVE_DISTANCE",
            "exact_brep": True,
            "boolean_computed": False,
            "minimum_distance_mm": gap,
            "distance_threshold_mm": threshold,
        }
    else:
        common = dict(model.common_volume(first_id, second_id))
        common["boolean_computed"] = True
    return {"distance": distance, "common": common}


def main()->int:
    p=argparse.ArgumentParser(); p.add_argument("first",type=Path); p.add_argument("second",type=Path); p.add_argument("--output",type=Path,required=True)
    p.add_argument("--common-volume-distance-threshold-mm",type=float,default=0.0); a=p.parse_args()
    model=OCCTBRepModel(); model.load_brep("A",a.first); model.load_brep("B",a.second)
    result=inspect_pair(model,common_volume_distance_threshold_mm=a.common_volume_distance_threshold_mm)
    a.output.write_text(json.dumps(result,ensure_ascii=False),encoding="utf-8"); return 0
if __name__=="__main__": raise SystemExit(main())
