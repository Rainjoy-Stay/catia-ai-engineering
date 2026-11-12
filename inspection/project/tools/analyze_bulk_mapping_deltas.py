"""Diagnose nearest geometry deltas without accepting uncertain mappings."""
import argparse
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'project'))
from catia_checker.occt_brep import OCCTBRepModel
from catia_checker.geometry_fingerprint import match_geometry_records

parser=argparse.ArgumentParser();parser.add_argument('directory',type=Path);args=parser.parse_args()
audit=json.loads((args.directory/'benchmark.json').read_text(encoding='utf-8'))
result=[]; geometry_cases=[]
for case in audit['cases']:
    model=OCCTBRepModel();manifest=model.load_step(case['step_path'],lightweight=True)
    geometry_cases.append(manifest['shapes'][1:])
    records=case['mapping'];rows=[]
    for shape in manifest['shapes'][1:]:
        candidates=sorted(records,key=lambda r:max(abs(a-b) for a,b in zip(shape['centroid_mm'],r['centroid_mm'])))
        nearest=candidates[0]
        rows.append({'shape_id':shape['shape_id'],'order_based_label':shape.get('source_name'),
            'nearest_body_index':nearest['source_body_index'],
            'centroid_delta_mm':max(abs(a-b) for a,b in zip(shape['centroid_mm'],nearest['centroid_mm'])),
            'second_centroid_delta_mm':max(abs(a-b) for a,b in zip(shape['centroid_mm'],candidates[1]['centroid_mm'])),
            'relative_volume_delta':abs(shape['volume_mm3']-nearest['volume_mm3'])/max(shape['volume_mm3'],nearest['volume_mm3'],1e-12),
            'relative_area_delta':abs(shape['surface_area_mm2']-nearest['surface_area_mm2'])/max(shape['surface_area_mm2'],nearest['surface_area_mm2'],1e-12),
            'mapping_accepted':False})
    result.append({'mode':case['mode'],'rows':rows})
(args.directory/'mapping-delta-diagnostics.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
comparison=match_geometry_records(geometry_cases[1],geometry_cases[0],source_id='shape_id',target_id='shape_id')
(args.directory/'individual-vs-bulk-geometry.json').write_text(json.dumps(comparison,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'individual_vs_bulk_geometry_matches':comparison['matched_count'],'complete':comparison['is_complete']}))
for case in result:
    print(json.dumps({'mode':case['mode'],'largest_centroid_deltas':sorted(case['rows'],key=lambda r:r['centroid_delta_mm'],reverse=True)[:4]}))
