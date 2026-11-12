"""Bounded original-source retry; retains the legacy checkpoint unchanged."""
import json,subprocess,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from catia_checker.occt_session_cache import atomic_json,digest
root=Path(sys.argv[1]).resolve();review=root/'shape-review';tools=Path(__file__).resolve().parent
queue=json.loads((review/'original-retry-queue.json').read_text(encoding='utf-8'))
output=review/'original-retry-pilot';output.mkdir(exist_ok=True);rows=[]
for index,item in enumerate([r for r in queue['rows'] if r['status']=='ORIGINAL_SOLID_RETRY_READY' and r['already_cached_originals']==2][:2]):
    row={'pair':item['pair'],'original_labels':item['original_labels'],'screen_pass':False}
    start=time.monotonic();path=output/f'pair-{index:03d}.json'
    try:
        for label in item['original_labels']:
            audit=json.loads((review/f'original-{label}/audit.json').read_text(encoding='utf-8'))
            if audit.get('actual_target_label',audit.get('step_entity'))!=label:raise ValueError('Original label mismatch')
        subprocess.run([sys.executable,str(tools/'review_shape_candidates.py'),str(root),'--worker',
            *[str(review/f'original-{label}/target.brep') for label in item['original_labels']],str(path)],
            timeout=30,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        facts=json.loads(path.read_text(encoding='utf-8'))
        row.update(status='ORIGINAL_RETRY_COMPLETED',facts=facts,result_sha256=digest(path))
        if facts.get('input_valid')==[True,True] and facts.get('common_valid') is True and facts.get('common_solid_count')==0:
            row.update(screen_pass=True,reason='原始有效实体求交无公共实体；仅实体干涉预筛通过，不评价最小间隙')
        else:row['reason']='保留重叠或无效几何待复核'
    except subprocess.TimeoutExpired:row.update(status='ORIGINAL_RETRY_TIMEOUT',reason='30秒边界达到，未自动放行')
    except Exception as exc:row.update(status='ORIGINAL_RETRY_ERROR',reason=str(exc))
    row['elapsed_seconds']=time.monotonic()-start;rows.append(row)
    atomic_json(output/'summary.json',{'baseline':'ORIGINAL_STEP','geometry_fingerprint':queue['geometry_fingerprint'],
        'rows':rows,'source_modified':False,'legacy_checkpoint_modified':False})
    print(json.dumps({'pair':row['pair'],'status':row['status'],'screen_pass':row['screen_pass'],'elapsed_seconds':row['elapsed_seconds']},ensure_ascii=True),flush=True)
