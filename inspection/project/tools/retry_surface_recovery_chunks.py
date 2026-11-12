"""Recover timeout work in checkpointed bounded chunks."""
import concurrent.futures
import json
from pathlib import Path
import subprocess
import sys
from tools.review_surface_recovery_pilot import ROOT,digest

def main():
    out=ROOT/'artifacts/step_surface_recovery_retry'; out.mkdir(exist_ok=True)
    previous=json.loads((ROOT/'artifacts/step_surface_recovery_remaining/surface_recovery_pilot.json').read_text(encoding='utf-8'))
    formal=ROOT/'artifacts/step_filter_local_evidence/turbine_source_evidence_filtered.json'; before=digest(formal)
    tasks=[]
    for r in previous['records']:
        if 'error' not in r: continue
        detail=ROOT/'artifacts/step_full_exterior_scan'/f"{r['solid_id']}.json"
        for start in range(0,r['expected_face_count'],100): tasks.append((detail,start,min(100,r['expected_face_count']-start)))
    def run(task):
        detail,start,count=task; target=out/f'{detail.stem}_{start:04d}.json'; error=None
        sha=digest(detail.with_suffix('.brep'))
        try:
            p=subprocess.run([sys.executable,str(ROOT/'tools/review_surface_recovery_pilot.py'),str(detail),str(target),str(start),str(count)],capture_output=True,text=True,timeout=40)
            if p.returncode: error=f'WORKER_EXIT_CODE_{p.returncode}: '+p.stderr[-1000:]
        except subprocess.TimeoutExpired: error='CHUNK_TIME_LIMIT_40_SECONDS'
        result=json.loads(target.read_text(encoding='utf-8')) if target.exists() else {'faces':[]}
        if len(result['faces'])!=count and not error: error='INCOMPLETE_CHUNK_OUTPUT'
        assert digest(detail.with_suffix('.brep'))==sha
        if result['faces']: assert result['input_brep_sha256']==sha
        return {**result,'solid_id':detail.stem,'start':start,'expected_faces':count,'worker_error':error}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool: records=list(pool.map(run,tasks))
    faces=[f for r in records for f in r['faces']]; ids=[f['face_id'] for f in faces]
    assert len(ids)==len(set(ids)) and digest(formal)==before
    types={}; reasons={}
    for f in faces:
        recovery=f['recovery']; reasons[recovery['reason']]=reasons.get(recovery['reason'],0)+1
        assert recovery['status']=='NOT_EVALUATED'
        if recovery['support_recovered']:
            kind=recovery['recovered_support']['surface_type']; types[kind]=types.get(kind,0)+1
    expected=sum(r['expected_faces'] for r in records)
    summary={'geometry_source':'ORIGINAL_STEP_CACHE_NOT_CATIA_REEXPORT','status':'NOT_EVALUATED',
        'expected_faces':expected,'processed_faces':len(faces),'deferred_faces':expected-len(faces),
        'worker_errors':sum(bool(r['worker_error']) for r in records),'recovered_types':types,'reason_counts':reasons,
        'formal_result_unchanged':True,'design_cavity_confirmed':False,'engineering_pipe_confirmed':False,'records':records}
    (out/'chunk_recovery_review.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    (out/'超时实体分批复核.md').write_text(f"# 超时实体分批复核\n\n复核原始 STEP 缓存中此前超时的两个实体，每批最多 100 张面，限时 40 秒，并逐面保存结果。\n\n计划 {expected} 张面，完成 {len(faces)} 张，剩余 {expected-len(faces)} 张仍未评估。恢复类型：{types}；原因统计：{reasons}。\n\n恢复结果须通过面身份、内核误差和独立投影采样检查；采样不是全域误差证明。所有结果仍为 NOT_EVALUATED，不表示 CATIA 导出模型有空腔，不确认壁厚、流道或管路用途。正式干涉结果未改动。\n",encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k!='records'},ensure_ascii=False))

if __name__=='__main__': main()
