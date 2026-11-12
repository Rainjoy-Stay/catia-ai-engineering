"""Separate invalid original transfers from valid overlap and timeout."""
import json,sys
from collections import Counter
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from catia_checker.occt_session_cache import atomic_json,digest
root=Path(sys.argv[1]).resolve();review=root/'shape-review'
summary=json.loads((review/'original-retry-batch/summary.json').read_text(encoding='utf-8'))
rows=[]
for item in summary['rows']:
    fact=item.get('facts',{});row={'pair':item['pair'],'original_labels':item['original_labels'],'screen_pass':item['screen_pass']}
    if item['status']!='ORIGINAL_RETRY_COMPLETED':category='TIMEOUT_OR_ERROR'
    elif fact.get('input_valid')!=[True,True]:category='INVALID_ORIGINAL_TRANSFER_INPUT'
    elif fact.get('common_valid') is not True:category='INVALID_COMMON'
    elif fact.get('common_solid_count')==0:category='VALID_NO_SOLID_INTERFERENCE'
    elif fact.get('common_volume_raw_mm3',0)>0:category='VALID_SOLID_OVERLAP_NEEDS_WITNESS'
    else:category='INCONSISTENT_COMMON_METRICS'
    row.update(category=category,input_valid=fact.get('input_valid'),common_valid=fact.get('common_valid'),
        common_solid_count=fact.get('common_solid_count'),common_volume_mm3=fact.get('common_volume_raw_mm3'))
    errors=[]
    for label in item['original_labels']:
        path=review/f'original-{label}/audit.json'
        if path.exists():
            audit=json.loads(path.read_text(encoding='utf-8'))
            if audit.get('valid') is False:errors.append({'label':label,'error_counts':audit['error_counts'],
                'audit_sha256':digest(path),'raw_step_intrinsic_invalidity_proven':False})
    row['invalid_input_diagnostics']=errors;rows.append(row)
result={'geometry_fingerprint':summary['geometry_fingerprint'],'source_step_sha256':summary['source_step_sha256'],
    'batch_summary_sha256':digest(review/'original-retry-batch/summary.json'),
    'counts':dict(Counter(r['category'] for r in rows)),
    'invalid_labels':dict(Counter(e['label'] for r in rows for e in r['invalid_input_diagnostics'])),
    'rows':rows,'source_modified':False,'automatic_new_passes':0,
    'limitation':'OCCT transfer/check failure does not prove the raw STEP itself is invalid'}
atomic_json(review/'original-retry-triage.json',result)
print(json.dumps({'counts':result['counts'],'invalid_labels':result['invalid_labels'],
    'valid_overlap':[r for r in rows if r['category']=='VALID_SOLID_OVERLAP_NEEDS_WITNESS']},ensure_ascii=True))
