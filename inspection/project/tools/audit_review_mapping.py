"""Diagnose rejected mappings without weakening identity or clearance rules."""
import json,sys
from pathlib import Path
from collections import Counter
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from catia_checker.geometry_fingerprint import compare_geometry_features
from catia_checker.occt_session_cache import atomic_json,digest
root=Path(sys.argv[1]).resolve()
objects=json.loads((root/'registry.json').read_text(encoding='utf-8'))['objects']
receipts=json.loads((root/'body-mapping.json').read_text(encoding='utf-8'))
review=json.loads((root/'shape-review/ten-pair-source-review.json').read_text(encoding='utf-8'))
rows=[]
for identifier in sorted({i for r in review['rows'] for i in r['pair']}):
    obj=objects[identifier]
    if obj.get('geometry_kind')!='SOLID':
        rows.append({'shape_id':identifier,'status':'ELEMENT_MAPPING_MISSING','reason':'仅有图形集级对应，需元素级识别'});continue
    candidates=[r for r in receipts if r.get('batch_id')==obj['batch_id'] and r.get('source_kind')=='BODY']
    scored=[]
    for r in candidates:
        check=compare_geometry_features(obj,r)
        scored.append({'source_body_index':r['source_body_index'],'source_body_name':r['source_body_name'],
                       'copied_label_match':r.get('batch_body_name')==obj.get('source_name'),**check})
    scored.sort(key=lambda r:(not r['copied_label_match'],r['score']))
    top=scored[:3]
    rows.append({'shape_id':identifier,'status':'EXISTING_VERIFIED' if obj.get('mapping_method') else 'REJECTED_MAPPING_AUDITED',
                 'candidates':top,'failed_checks':[c for c in top[0]['checks'] if not c['match']] if top else [],
                 'mapping_verified':bool(obj.get('mapping_method'))})
output={'rows':rows,'counts':dict(Counter(r['status'] for r in rows)),
        'registry_sha256':digest(root/'registry.json'),'receipts_sha256':digest(root/'body-mapping.json'),
        'tolerances_changed':False,'original_mapping_modified':False}
atomic_json(root/'shape-review/ten-pair-mapping-audit.json',output)
print(json.dumps(output,ensure_ascii=False))
