"""Deduplicate unfinished/error pairs and gate their original-source trace."""
import json,re,sys
from collections import Counter
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from catia_checker.source_provenance import trace_identity
from catia_checker.occt_session_cache import atomic_json,digest
root=Path(sys.argv[1]).resolve()
load=lambda name:json.loads((root/name).read_text(encoding='utf-8'))
report=load('check-raw.json');checkpoint=load('checkpoint.json')
analysis=report['large_single_part_analysis']['analysis']
registry=load('registry.json')['objects'];receipts=load('body-mapping.json')
complete={tuple(sorted(r['pair'])) for r in checkpoint['completed_pairs']}
queue={};non_pair_errors=[]
for pair in analysis['broad_phase']['pairs']:
    key=tuple(sorted(pair))
    if key not in complete:queue[key]={'pair':list(key),'causes':['NOT_COMPLETED']}
for error in analysis['errors']:
    if not error.get('object_a') or not error.get('object_b'):
        non_pair_errors.append(error);continue
    key=tuple(sorted((error['object_a'],error['object_b'])))
    row=queue.setdefault(key,{'pair':list(key),'causes':[]})
    if error['code'] not in row['causes']:row['causes'].append(error['code'])
for row in queue.values():
    traces=[trace_identity(i,registry,receipts) for i in row['pair']]
    row['source_traces']=traces
    labels=[]
    for identifier,trace in zip(row['pair'],traces):
        match=re.search(r'#(\d+)$',trace.get('source_body_name',''))
        if registry[identifier]['geometry_kind']!='SOLID' or not trace['source_identity_traced'] or not match:break
        labels.append(int(match[1]))
    row['status']='ORIGINAL_SOLID_RETRY_READY' if len(labels)==2 else 'SOURCE_ELEMENT_MAPPING_REQUIRED'
    row['original_labels']=labels if len(labels)==2 else []
    row['already_cached_originals']=sum((root/f'shape-review/original-{n}/target.brep').exists() for n in labels)
    row['screen_pass']=False
rows=sorted(queue.values(),key=lambda r:(r['status']!='ORIGINAL_SOLID_RETRY_READY',-r['already_cached_originals'],r['pair']))
result={'baseline':'ORIGINAL_STEP','geometry_fingerprint':checkpoint['geometry_fingerprint'],
    'checkpoint_sha256':digest(root/'checkpoint.json'),'report_sha256':digest(root/'check-raw.json'),
    'counts':dict(Counter(r['status'] for r in rows)), 'causes':dict(Counter(c for r in rows for c in r['causes'])),
    'rows':rows,'non_pair_errors':non_pair_errors,'source_modified':False,'automatic_passes':0}
atomic_json(root/'shape-review/original-retry-queue.json',result)
print(json.dumps({'counts':result['counts'],'causes':result['causes'],'first_ready':rows[:3]},ensure_ascii=True))
