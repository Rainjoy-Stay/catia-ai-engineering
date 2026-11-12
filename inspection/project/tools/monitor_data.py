"""Read-only dashboard projection; screening never rewrites formal findings."""
import json
import threading
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path


_json_cache={}
_json_lock=threading.Lock()
_review_lock=threading.Lock()

def revoke_attribution(directory, pair, geometry_fingerprint):
    if not isinstance(pair,list) or len(pair)!=2 or not all(isinstance(x,str) for x in pair):
        raise ValueError('Exact two-object pair required')
    path=Path(directory)/'attribution-review.json'
    with _review_lock:
        value=json.loads(path.read_text(encoding='utf-8'))
        if value['geometry_fingerprint']!=geometry_fingerprint:raise ValueError('Model fingerprint mismatch')
        row=next((x for x in value['rows'] if sorted(x['pair'])==sorted(pair)),None)
        if row is None:raise ValueError('Pair outside original review scope')
        if not row.get('excluded'):return {'revoked':False,'already_pending':True}
        row.setdefault('revocation_history',[]).append({'at':datetime.now(timezone.utc).isoformat(),
            'previous_attribution':row['attribution_result'],'certificate_preserved':row.get('exclusion_gate')})
        row.update(excluded=False,attribution_result='CAUSE_UNKNOWN',confirmed_actionable_interference=False)
        value['automatic_exclusions']=sum(bool(x.get('excluded')) for x in value['rows'])
        value['unresolved_count']=sum(not x.get('excluded') and not x.get('confirmed_actionable_interference') for x in value['rows'])
        fd,name=tempfile.mkstemp(dir=path.parent,prefix='attribution-',suffix='.pending')
        try:
            with os.fdopen(fd,'w',encoding='utf-8') as stream:json.dump(value,stream,ensure_ascii=False)
            os.replace(name,path)
        finally:
            Path(name).unlink(missing_ok=True)
    return {'revoked':True}
def read_json(path, default=None):
    try:
        file=Path(path);stamp=(file.stat().st_mtime_ns,file.stat().st_size);key=str(file.resolve())
        with _json_lock:
            cached=_json_cache.get(key)
            if cached and cached[0]==stamp:return cached[1]
            value=json.loads(file.read_text(encoding='utf-8'))
            if len(_json_cache)>24:_json_cache.clear()
            _json_cache[key]=(stamp,value)
            return value
    except (OSError, ValueError, TypeError): return default


def dashboard_data(directory, checkpoint, report, events):
    result=read_json(report,{}) or {}
    saved=read_json(checkpoint,{}) or {}
    plan=result.get('large_single_part_analysis',{}).get('batch_plan',{})
    registry=read_json(Path(directory)/'registry.json',{}) or {}
    objects=dict(registry.get('objects',{}))
    for item in plan.get('shapes',[]):
        objects.setdefault(item['shape_id'],{k:item.get(k) for k in ('source_body_name','source_body_index','mapping_method','source_name','geometry_kind','source_path','surface_area_mm2','solid_count')})
        objects[item['shape_id']].setdefault('source_name',item.get('source_name'))
    bodies=registry.get('catia_bodies',[])
    if not bodies:
        baseline=read_json(Path(__file__).resolve().parents[3]/'output/full_all_features_before_optimized_test_manifest.json',{}) or {}
        for part in baseline.get('parts',{}).values():
            bodies.extend({'source_body_index':i,'source_body_name':b['name']} for i,b in enumerate(part.get('bodies',[]),1))
    candidates=registry.get('candidates') or plan.get('broad_phase',{}).get('pairs',[])
    facts={tuple(sorted(x['pair'])):x['fact'] for x in saved.get('completed_pairs',[])}
    formal={}
    for finding in result.get('findings',[]):
        meta=finding.get('metadata',{})
        key=tuple(sorted((meta.get('geometry_object_a') or finding.get('object_a',''),
                          meta.get('geometry_object_b') or finding.get('object_b',''))))
        formal[key]=finding
    active={}
    for event in events:
        stage=event.get('stage','')
        if stage.startswith('EXACT_PAIR_') and stage.endswith('_START'):
            active[(stage.removesuffix('_START'),event.get('index'))]=event
        elif stage.startswith('EXACT_PAIR_') and stage.endswith('_COMPLETE'):
            active.pop((stage.removesuffix('_COMPLETE'),event.get('index')),None)
    rows=[]
    attribution=read_json(Path(directory)/'attribution-review.json',{}) or {}
    if attribution.get('geometry_fingerprint') != saved.get('geometry_fingerprint'):
        attribution={}
    reviewed={tuple(sorted(x['pair'])):x for x in attribution.get('rows',[])}
    for pair in candidates or facts:
        key=tuple(sorted(pair));fact=facts.get(key);f=formal.get(key,{})
        rows.append({'pair':list(key),'fact':fact,'formal_status':f.get('status','NOT_EVALUATED'),
                     'attribution_review':reviewed.get(key),
                     'reason':f.get('metadata',{}).get('step_interference_filter',{}).get('reason') or
                              ('等待精确计算' if fact is None else '正式判定尚未闭合')})
    return {'objects':objects,'catia_bodies':bodies,'catia_geometry':registry.get('catia_geometry',[]),'rows':rows,'active_pairs':list(active.values()),
            'attribution_summary':{k:v for k,v in attribution.items() if k!='rows'},
            'mapping_errors':registry.get('mapping_errors',[]),'checkpoint_count':len(facts),
            'candidate_count':len(candidates),'screening_policy':{'name':'记录的几何判定','volume_mm3':1e-6,
            'contact_allowed':False,'approved':False,'note':'仅几何预筛；不证明 BREP 有效性或工程合规，不改写正式判定'}}
