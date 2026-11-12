"""Bounded, read-only BSpline recovery pilot with replay identity checks."""
import concurrent.futures
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def worker(detail_path,output,start=0,limit=None):
    from catia_checker.occt_brep import OCCTBRepModel
    from catia_checker.geometry_fingerprint import compare_geometry_features
    from standalone.step_pipe_semantics.surface_recovery import recover_surface_support
    detail=json.loads(detail_path.read_text(encoding='utf-8'))
    sid=detail['solid']['shape_id']; model=OCCTBRepModel()
    model.load_brep(sid,detail_path.with_suffix('.brep')); model.solid_face_provenance(sid)
    records=[]
    faces=[f for f in detail['faces'] if (f.get('surface_features') or {}).get('surface_type')=='BSPLINE']
    selected=faces[start:] if limit is None else faces[start:start+limit]
    input_sha=digest(detail_path.with_suffix('.brep'))
    from standalone.step_pipe_semantics.surface_quarantine import matches_quarantine
    quarantine_path=ROOT/'artifacts/step_surface_recovery_diagnostics/quarantine.json'
    quarantine=json.loads(quarantine_path.read_text(encoding='utf-8')) if quarantine_path.exists() else []
    def save():
        temporary=output.with_suffix('.tmp')
        temporary.write_text(json.dumps({'solid_id':sid,'start':start,'expected_faces':len(selected),
            'input_brep_sha256':input_sha,'faces':records},ensure_ascii=False),encoding='utf-8')
        temporary.replace(output)
    save()
    for face in selected:
        fid=face['shape_id']; identity=compare_geometry_features(face,model.describe(fid))
        result={'status':'NOT_EVALUATED','support_recovered':False,'reason':'FACE_CACHE_IDENTITY_UNCONFIRMED'}
        if identity['compatible']:
            if matches_quarantine(fid,input_sha,quarantine):
                result={**result,'reason':'NATIVE_ANALYTICAL_CONVERSION_QUARANTINED',
                        'design_cavity_confirmed':False,'engineering_pipe_confirmed':False}
            else:
                try: result=recover_surface_support(model._shape(fid))
                except Exception as exc: result={**result,'reason':'RECOVERY_EXCEPTION','error':str(exc)}
        records.append({'face_id':fid,'identity_check':identity,'recovery':result})
        save()

def main():
    remaining='--remaining' in sys.argv
    if len(sys.argv)>1 and not remaining:
        worker(Path(sys.argv[1]),Path(sys.argv[2]),int(sys.argv[3]) if len(sys.argv)>3 else 0,
               int(sys.argv[4]) if len(sys.argv)>4 else None); return
    source=ROOT/'artifacts/step_full_exterior_scan'; out=ROOT/'artifacts/step_surface_recovery_pilot'
    if remaining: out=ROOT/'artifacts/step_surface_recovery_remaining'
    out.mkdir(exist_ok=True)
    formal=ROOT/'artifacts/step_filter_local_evidence/turbine_source_evidence_filtered.json'
    before=digest(formal); candidates=[]
    for path in source.glob('EXTERIOR_SOURCE_SOLID_*.json'):
        if not path.with_suffix('.brep').exists(): continue
        detail=json.loads(path.read_text(encoding='utf-8'))
        count=sum((f.get('surface_features') or {}).get('surface_type')=='BSPLINE' for f in detail['faces'])
        if count: candidates.append((count,path))
    selected=sorted(candidates)[12:] if remaining else sorted(candidates)[:12]
    def run(item):
        count,path=item; target=out/(path.stem+'.recovery.json'); previous=digest(path.with_suffix('.brep'))
        try:
            p=subprocess.run([sys.executable,__file__,str(path),str(target)],capture_output=True,text=True,timeout=60)
            if p.returncode: raise RuntimeError(p.stderr[-2000:])
            result=json.loads(target.read_text(encoding='utf-8'))
            assert digest(path.with_suffix('.brep'))==previous
            assert len(result['faces'])==count
            return result
        except Exception as exc: return {'solid_id':path.stem,'expected_face_count':count,'error':str(exc),'faces':[]}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool: records=list(pool.map(run,selected))
    faces=[f for r in records for f in r['faces']]; recovered=[f for f in faces if f['recovery']['support_recovered']]
    types={}
    for f in recovered:
        kind=f['recovery']['recovered_support']['surface_type']; types[kind]=types.get(kind,0)+1
    assert digest(formal)==before
    reasons={}
    for f in faces:
        reason=f['recovery']['reason']; reasons[reason]=reasons.get(reason,0)+1
    summary={'geometry_source':'ORIGINAL_STEP_CACHE_NOT_CATIA_REEXPORT','status':'NOT_EVALUATED',
             'selected_solids':len(selected),'expected_faces':sum(n for n,p in selected),'processed_faces':len(faces),
             'worker_errors':sum('error' in r for r in records),'recovered_supports':len(recovered),'recovered_types':types,
             'reason_counts':reasons,'previously_processed_solids':12 if remaining else 0,
             'unprocessed_cached_bspline_solids':sum('error' in r for r in records) if remaining else len(candidates)-len(selected),
             'unprocessed_faces_in_selected_solids':sum(n for n,p in selected)-len(faces),'formal_result_unchanged':True,
             'engineering_pipe_confirmed':False,'design_cavity_confirmed':False,'wall_thickness_mm':None,'records':records}
    (out/'surface_recovery_pilot.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    report=f"# 非解析曲面恢复首批复核\n\n本批来自原始 STEP 的只读缓存，不是 CATIA 再导出的无空腔模型。\n\n检查 {len(selected)} 个实体、计划 {summary['expected_faces']} 张 BSpline 曲面，实际处理 {len(faces)} 张，工作进程错误 {summary['worker_errors']}。恢复解析支撑曲面 {len(recovered)} 张，类型统计：{types}。\n\n恢复须先通过面身份复核，再满足内核误差和独立投影采样误差均不超过 0.00001 mm。采样不是全域误差证明，恢复不修改原曲面的裁剪与拓扑。\n\n所有结果仍为 NOT_EVALUATED；不能据此外推空腔、壁厚、流道或设计管路。原有正式干涉结果未改动。仍有 {summary['unprocessed_cached_bspline_solids']} 个含 BSpline 的已缓存实体未处理，未缓存曲面也不在本批范围内。\n"
    (out/'非解析曲面恢复首批复核.md').write_text(report,encoding='utf-8')
    if remaining:
        report=report.replace('非解析曲面恢复首批复核','非解析曲面恢复剩余缓存复核')
        report+=f"\n首批 12 个实体、58 张面已另行复核。本批失败或超时的工作进程数为 {summary['worker_errors']}，其曲面仍未完成复核；原因统计：{reasons}。未缓存的 BSpline 曲面不在范围内。\n"
        (out/'非解析曲面恢复剩余缓存复核.md').write_text(report,encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k!='records'},ensure_ascii=False))

if __name__=='__main__': main()
