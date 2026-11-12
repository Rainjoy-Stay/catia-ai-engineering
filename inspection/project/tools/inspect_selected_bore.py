import argparse
import json
from pathlib import Path
from OCP.BRep import BRep_Tool
from OCP.TopAbs import TopAbs_FACE, TopAbs_EDGE, TopAbs_VERTEX
from catia_checker.occt_brep import OCCTBRepModel
from standalone.step_pipe_semantics.bore_evidence import inspect_straight_bore
from standalone.step_pipe_semantics.bore_selection import select_straight_bore_review


def main():
    p=argparse.ArgumentParser(); p.add_argument('detail',type=Path); p.add_argument('output',type=Path)
    a=p.parse_args(); detail=json.loads(a.detail.read_text(encoding='utf-8'))
    selection=select_straight_bore_review(detail)
    if not selection['eligible']: raise ValueError('Ineligible selection')
    sid=detail['solid']['shape_id']; model=OCCTBRepModel(); model.load_brep(sid,a.detail.with_suffix('.brep'))
    tolerance=max(1e-7,*(BRep_Tool.MaxTolerance_s(model._shape(sid),k) for k in (TopAbs_FACE,TopAbs_EDGE,TopAbs_VERTEX)))
    if selection['inner_radius_mm']<=10*tolerance or selection['length_mm']<=10*tolerance:
        a.output.write_text(json.dumps({'status':'NOT_EVALUATED','exact_brep':False,
            'reason':'LOCAL_TOLERANCE_TOO_LARGE_FOR_WITNESS','classification_tolerance_mm':tolerance,
            'design_cavity_confirmed':False,'fluid_channel_confirmed':False}),encoding='utf-8')
        return
    evidence=inspect_straight_bore(model,sid,selection['centers_mm'],selection['inner_radius_mm'],selection['radial_search_outer_radius_mm'],tolerance)
    evidence['classification_tolerance_mm']=tolerance
    evidence['geometry_source']='ORIGINAL_STEP_ENTITY_CACHE_NOT_CATIA_REEXPORT'
    a.output.write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__': main()
