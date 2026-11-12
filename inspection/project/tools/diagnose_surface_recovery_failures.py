"""Isolate native failures without changing source faces or formal results."""
import concurrent.futures
import json
import subprocess
import sys
from pathlib import Path
from tools.review_surface_recovery_pilot import ROOT,digest

def worker(sid,fid,output):
    from catia_checker.occt_brep import OCCTBRepModel
    from catia_checker.geometry_fingerprint import compare_geometry_features
    from standalone.step_pipe_semantics.surface_recovery import recover_surface_support
    def checkpoint(stage,**values):
        output.write_text(json.dumps({'solid_id':sid,'face_id':fid,'stage':stage,**values},ensure_ascii=False,indent=2),encoding='utf-8')
    path=ROOT/'artifacts/step_full_exterior_scan'/f'{sid}.json'
    saved=next(f for f in json.loads(path.read_text(encoding='utf-8'))['faces'] if f['shape_id']==fid)
    model=OCCTBRepModel(); checkpoint('LOAD_BREP')
    model.load_brep(sid,path.with_suffix('.brep')); model.solid_face_provenance(sid)
    checkpoint('DESCRIBE_FACE'); current=model.describe(fid)
    checkpoint('COMPARE_IDENTITY'); identity=compare_geometry_features(saved,current)
    if not identity['compatible']:
        checkpoint('IDENTITY_UNCONFIRMED',identity=identity); return
    def trace(frame,event,arg):
        if event=='line' and frame.f_code.co_filename.endswith('surface_recovery.py'):
            checkpoint('RECOVERY_LINE',line=frame.f_lineno,identity=identity)
        return trace
    sys.settrace(trace)
    try: result=recover_surface_support(model._shape(fid))
    except Exception as exc: result={'status':'NOT_EVALUATED','support_recovered':False,'reason':'RECOVERY_EXCEPTION','error':str(exc)}
    finally: sys.settrace(None)
    checkpoint('FINISHED',identity=identity,recovery=result)

def main():
    if len(sys.argv)>1:
        worker(sys.argv[1],sys.argv[2],Path(sys.argv[3])); return
    source=ROOT/'artifacts/step_surface_recovery_retry/chunk_recovery_review.json'
    data=json.loads(source.read_text(encoding='utf-8'))
    tasks=[(r['solid_id'],f['face_id']) for r in data['records'] for f in r['faces'] if f['recovery']['reason']=='WORKER_FAILURE_AT_FACE_CHECK']
    out=ROOT/'artifacts/step_surface_recovery_diagnostics'; out.mkdir(exist_ok=True)
    formal=ROOT/'artifacts/step_filter_local_evidence/turbine_source_evidence_filtered.json'; before=digest(formal)
    def run(task):
        sid,fid=task; target=out/(fid.replace('::','_')+'.json'); brep=ROOT/'artifacts/step_full_exterior_scan'/f'{sid}.brep'; sha=digest(brep)
        try:
            p=subprocess.run([sys.executable,__file__,sid,fid,str(target)],capture_output=True,text=True,timeout=30)
            exit_code=p.returncode; error=p.stderr[-1000:]
        except subprocess.TimeoutExpired: exit_code=None; error='TIME_LIMIT_30_SECONDS'
        checkpoint=json.loads(target.read_text(encoding='utf-8')) if target.exists() else {}
        assert digest(brep)==sha
        return {'solid_id':sid,'face_id':fid,'status':'NOT_EVALUATED','exit_code':exit_code,'error':error,'checkpoint':checkpoint}
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool: records=list(pool.map(run,tasks))
    assert digest(formal)==before
    summary={'status':'NOT_EVALUATED','formal_result_unchanged':True,'records':records}
    (out/'surface_failure_diagnostics.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['# 异常曲面隔离诊断','','仅检查原始 STEP 只读缓存，不修改几何或正式干涉结果。','']
    for r in records:
        c=r['checkpoint']; lines.append(f"- {r['face_id']}：进程退出码 {r['exit_code']}；最后阶段 {c.get('stage')}，代码行 {c.get('line')}。")
    lines+=['','最后阶段只定位中断位置，不证明几何损坏。所有曲面仍为 NOT_EVALUATED；不确认空腔、壁厚或管路用途。']
    (out/'异常曲面隔离诊断.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps(records,ensure_ascii=False))

if __name__=='__main__': main()
