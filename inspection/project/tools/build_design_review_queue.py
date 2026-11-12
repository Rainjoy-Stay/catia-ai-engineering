"""Build a bounded, model-bound queue of original overlap witnesses."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from catia_checker.occt_session_cache import atomic_json,digest
root=Path(sys.argv[1]).resolve();review=root/'shape-review'
certificate=json.loads((review/'ten-evidence-certificates.json').read_text(encoding='utf-8'))
rows=[]
for index in range(4,10):
    row=certificate['rows'][index]
    original=json.loads((review/f'original-pair-{index:02d}.json').read_text(encoding='utf-8'))
    local=json.loads((review/f'local-penetration-pair-{index:02d}.json').read_text(encoding='utf-8'))
    points=[w['point_mm'] for region in local['rows'] for w in region['interior_witnesses']
        if all(w['input_states'].get(k,'').endswith('TopAbs_IN') for k in ('OA','OB'))]
    rows.append({'pair':row['pair'],'original_common_volume_mm3':original['common_volume_raw_mm3'],
        'original_valid':original['input_valid']==[True,True] and original['common_valid'] is True,
        'original_internal_points_mm':points,'formal_verdict_modified':False,
        'reason':'原始双方内部点证明局部重叠；微小体积不代表设计不合格，需判定是否为允许配合'})
result={'geometry_fingerprint':certificate['geometry_fingerprint'],'rows':rows,
    'source_step_sha256':certificate['source_step_sha256'],
    'certificate_sha256':digest(review/'ten-evidence-certificates.json')}
atomic_json(review/'design-review-queue.json',result)
print(json.dumps(result,ensure_ascii=False))
