"""Complete all-pairs analysis of a fresh spatially coherent 10-20 Body sample."""
import concurrent.futures
from collections import Counter
import json
import math
import subprocess
import sys
from pathlib import Path
from tools.review_surface_recovery_pilot import ROOT,digest

def worker(request_path,output):
    from catia_checker.occt_brep import OCCTBRepModel
    from standalone.step_interference_filter import classify
    request=json.loads(request_path.read_text(encoding='utf-8')); model=OCCTBRepModel(); entities=[]
    for body in request['bodies']:
        record=body['records'][0]; sid=record['solid']['shape_id']; cache=Path(record['cache_file'])
        assert digest(cache)==record['cache_sha256']; model.load_brep(sid,cache)
        actual=model.describe(sid)
        entities.append({**actual,'body_key':request['baseline_sha256']+'::BODY_'+str(body['source_body_index'])})
    a,b=entities; distance=model.distance(a['shape_id'],b['shape_id'])
    overlap=model.local_overlap_evidence(a['shape_id'],b['shape_id'])
    fact={'minimum_distance_mm':distance['minimum_distance_mm'],'intersection_volume_mm3':max(0,overlap['volume_mm3']),'exact_brep':True}
    result={'body_a':request['bodies'][0]['source_body_index'],'body_b':request['bodies'][1]['source_body_index'],
        'fact':fact,'distance_evidence':distance,'overlap_evidence':overlap,'decision':classify(fact,a,b)}
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')

def box_gap(a,b):
    return math.sqrt(sum(max(0,a['min'][i]-b['max'][i],b['min'][i]-a['max'][i])**2 for i in range(3)))

def main():
    if len(sys.argv)==3: worker(Path(sys.argv[1]),Path(sys.argv[2])); return
    out=ROOT/'artifacts/spatial_local_15'; scan=json.loads((out/'exterior_scan/batch_exterior_scan.json').read_text(encoding='utf-8'))
    bodies=scan['records']; assert 10<=len(bodies)<=20 and scan['worker_errors']==0
    assert all(b['solid_count']==1 and b['records'][0]['solid']['valid'] for b in bodies)
    baseline_sha=digest(out/'baseline_manifest.json'); formal=ROOT/'artifacts/step_filter_local_evidence/turbine_source_evidence_filtered.json'; before=digest(formal)
    bounds=[b['records'][0]['solid']['bounds_mm'] for b in bodies]
    adjacency=[(i,j) for i in range(len(bodies)) for j in range(i+1,len(bodies)) if box_gap(bounds[i],bounds[j])<=5]
    connected={0}
    while True:
        previous=len(connected)
        for i,j in adjacency:
            if i in connected or j in connected: connected.update([i,j])
        if len(connected)==previous: break
    assert len(connected)==len(bodies),'Selected sample is not one spatial neighborhood'
    lo=[min(b['min'][i] for b in bounds) for i in range(3)]; hi=[max(b['max'][i] for b in bounds) for i in range(3)]
    pairs=out/'pairs'; pairs.mkdir(exist_ok=True); tasks=[]
    for i,a in enumerate(bodies):
        for b in bodies[i+1:]:
            stem=f"BODY_{a['source_body_index']}_{b['source_body_index']}"; request=pairs/(stem+'.input.json'); target=pairs/(stem+'.result.json')
            request.write_text(json.dumps({'bodies':[a,b],'baseline_sha256':baseline_sha},ensure_ascii=False),encoding='utf-8'); tasks.append((a['source_body_index'],b['source_body_index'],request,target))
    def run(task):
        a,b,request,target=task
        try:
            p=subprocess.run([sys.executable,__file__,str(request),str(target)],capture_output=True,text=True,timeout=30)
            if p.returncode: raise RuntimeError(f'EXIT_{p.returncode}: {p.stderr[-500:]}')
            return json.loads(target.read_text(encoding='utf-8'))
        except Exception as exc: return {'body_a':a,'body_b':b,'error':str(exc),'decision':{'status':'NOT_EVALUATED','category':'UNDETERMINED','reason':'EXACT_PAIR_NOT_COMPLETED'}}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool: records=list(pool.map(run,tasks))
    assert len(records)==len(bodies)*(len(bodies)-1)//2 and digest(formal)==before
    positive=[r for r in records if r.get('fact',{}).get('intersection_volume_mm3',0)>0]
    result={'scope':'ONE_SPATIAL_NEIGHBORHOOD_NOT_FULL_ENGINE','status':'NOT_EVALUATED',
        'body_count':len(bodies),'body_indices':[b['source_body_index'] for b in bodies],
        'bounds_mm':{'min':lo,'max':hi},'size_mm':[hi[i]-lo[i] for i in range(3)],
        'spatial_connectivity_verified':True,'neighbor_box_gap_limit_mm':5,'pair_count':len(records),
        'pair_errors':sum('error' in r for r in records),'positive_volume_overlap_pairs':len(positive),
        'robust_interior_overlap_pairs':sum(r['overlap_evidence']['robust_interior_witness_found'] for r in positive),
        'decision_counts':dict(Counter(r['decision']['status'] for r in records)),
        'category_counts':dict(Counter(r['decision']['category'] for r in records)),
        'geometry_counts':scan['geometry_counts'],'formal_result_unchanged':True,'records':records}
    (out/'local_analysis.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['# 空间相邻局部模型完整分析','',f"选择 {len(bodies)} 个 Body：{result['body_indices']}。",'',
        f"实际范围（mm）：{lo} 至 {hi}；尺寸约 "+' × '.join(f'{v:.3f}' for v in result['size_mm'])+' mm。',
        '选取依据是实际空间位置；邻接包围盒间隙不超过 5 mm 的图为一个连通区域，未按 Body 编号连续取样。','',
        f"重新逐 Body 导出并验证来源，本组全部为有效单 Solid。完整检查 {len(records)} 对，未完成 {result['pair_errors']} 对。",
        f"精确正体积重叠 {len(positive)} 对，其中 {result['robust_interior_overlap_pairs']} 对找到带局部余量的内部公共点。判定统计：{result['decision_counts']}；分类：{result['category_counts']}。",'',
        '有公共体积证明几何重叠，不直接证明非设计性穿模。接触、共面及用途不明的重叠均保留 NOT_EVALUATED；分离实体对的 PASS 只覆盖该对精确干涉几何，不是模型或管路整体通过。','',
        '| Body 对 | 公共体积 mm³ | 最小距离 mm | 内部余量证据 | 裁决 |', '|---|---:|---:|---|---|']
    for r in positive:
        lines.append(f"| {r['body_a']} / {r['body_b']} | {r['fact']['intersection_volume_mm3']:.9g} | {r['fact']['minimum_distance_mm']:.9g} | {r['overlap_evidence']['robust_interior_witness_found']} | {r['decision']['status']} |")
    lines+=['',f"外形候选统计：{scan['geometry_counts']}。候选仅为外形，实心杆等也可满足；不认定空腔、壁厚、流道、开口、正常管路连接或弯曲半径合规。",'',
        '保留 STEP、BREP、Face 来源、每对原始距离与公共体积、重叠包围盒及内部采样证据。正式全模型的 23 项待评估裁决未改写。边界外对象未检查，本局部结论不能外推全模型。']
    (out/'局部完整分析报告.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='records'},ensure_ascii=False))

if __name__=='__main__': main()
