"""Bounded read-only worker for one retained single-Body geometry cache."""
import argparse
import json
from pathlib import Path
from collections import Counter
from catia_checker.occt_brep import OCCTBRepModel
from standalone.step_pipe_semantics import straight_candidate, bend_candidate


def main():
    p=argparse.ArgumentParser(); p.add_argument('cache',type=Path)
    p.add_argument('solid_id'); p.add_argument('output',type=Path); a=p.parse_args()
    model=OCCTBRepModel(); model.load_brep(a.solid_id,a.cache)
    solid=model.describe(a.solid_id)
    provenance=model.solid_face_provenance(a.solid_id)
    faces=[model.describe(f) for f in provenance['face_ids']]
    straight=straight_candidate(solid,faces); bend=bend_candidate(solid,faces)
    candidate=straight if straight['geometry_kind']!='UNDETERMINED' else bend
    result={'solid':solid,'face_provenance':provenance,'faces':faces,'candidate':candidate,
            'recognition_reasons':{'straight':straight['reason'],'bend':bend['reason']},
            'surface_type_counts':dict(Counter((f.get('surface_features') or {}).get('surface_type','UNKNOWN') for f in faces))}
    a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__': main()
