"""Read-only support recovery on explicitly audited CATIA export caches."""
import concurrent.futures
import json
import subprocess
import sys
from pathlib import Path
from tools.review_surface_recovery_pilot import ROOT,digest

def worker(request_path,output):
    from catia_checker.occt_brep import OCCTBRepModel
    from catia_checker.geometry_fingerprint import compare_geometry_features
    from standalone.step_pipe_semantics.surface_recovery import recover_surface_support
    from standalone.step_pipe_semantics.exterior import exterior_candidate
    item=json.loads(request_path.read_text(encoding='utf-8')); cache=Path(item['cache_file'])
    assert digest(cache)==item['cache_sha256']
    detail=json.loads((ROOT/'artifacts/step_pipe_semantics_pilot'/item['detail_file']).read_text(encoding='utf-8'))
    model=OCCTBRepModel(); sid=item['solid_id']; model.load_brep(sid,cache); model.solid_face_provenance(sid)
    records=[]; views=[]
    result={'solid_id':sid,'source_body_index':item['source_body_index'],'geometry_source':'CATIA_SINGLE_BODY_EXPORT_CACHE',
        'source_binding':item['source_binding'],'input_brep_sha256':item['cache_sha256'],'faces':records,
        'original_exterior_candidate':exterior_candidate(detail['solid'],detail['faces'])}
    def save():
        tmp=output.with_suffix('.tmp'); tmp.write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8'); tmp.replace(output)
    save()
    for face in detail['faces']:
        view=face
        if (face.get('surface_features') or {}).get('surface_type')=='BSPLINE':
            fid=face['shape_id']; identity=compare_geometry_features(face,model.describe(fid))
            recovery={'status':'NOT_EVALUATED','support_recovered':False,'reason':'FACE_CACHE_IDENTITY_UNCONFIRMED'}
            if identity['compatible']:
                try: recovery=recover_surface_support(model._shape(fid))
                except Exception as exc: recovery={**recovery,'reason':'RECOVERY_EXCEPTION','error':str(exc)}
            records.append({'face_id':fid,'identity_check':identity,'recovery':recovery})
            if recovery['support_recovered']:
                view={**face,'surface_features':{**face['surface_features'],**recovery['recovered_support']}}
            save()
        views.append(view)
    result['support_assisted_exterior_candidate']=exterior_candidate(detail['solid'],views)
    result['complete']=True; assert digest(cache)==item['cache_sha256']; save()

def main():
    if len(sys.argv)>1: worker(Path(sys.argv[1]),Path(sys.argv[2])); return
    art=ROOT/'artifacts'; out=art/'step_export_surface_supports'; out.mkdir(exist_ok=True)
    pilot=json.loads((art/'step_pipe_semantics_pilot/turbine_pipe_pilot.json').read_text(encoding='utf-8'))
    formal=art/'step_filter_local_evidence/turbine_source_evidence_filtered.json'; before=digest(formal); tasks=[]; expected=0
    for item in pilot['records']:
        detail=json.loads((art/'step_pipe_semantics_pilot'/item['detail_file']).read_text(encoding='utf-8'))
        count=sum((f.get('surface_features') or {}).get('surface_type')=='BSPLINE' for f in detail['faces'])
        if not count: continue
        expected+=count; request=out/(item['solid_id']+'.input.json'); request.write_text(json.dumps(item,ensure_ascii=False),encoding='utf-8')
        tasks.append((item,count,request,out/(item['solid_id']+'.review.json')))
    def run(task):
        item,count,request,target=task; error=None
        try:
            p=subprocess.run([sys.executable,__file__,str(request),str(target)],capture_output=True,text=True,timeout=40)
            if p.returncode: error=f'EXIT_{p.returncode}: {p.stderr[-500:]}'
        except subprocess.TimeoutExpired: error='TIME_LIMIT_40_SECONDS'
        r=json.loads(target.read_text(encoding='utf-8')) if target.exists() else {'solid_id':item['solid_id'],'faces':[]}
        r['expected_bspline_faces']=count; r['worker_error']=error
        assert digest(Path(item['cache_file']))==item['cache_sha256']
        return r
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool: records=list(pool.map(run,tasks))
    faces=[f for r in records for f in r['faces']]; types={}; reasons={}
    for face in faces:
        r=face['recovery']; reasons[r['reason']]=reasons.get(r['reason'],0)+1
        if r['support_recovered']:
            kind=r['recovered_support']['surface_type']; types[kind]=types.get(kind,0)+1
    changed=[r['source_body_index'] for r in records if r.get('complete') and r['original_exterior_candidate']['geometry_kind']!=r['support_assisted_exterior_candidate']['geometry_kind']]
    assert digest(formal)==before
    result={'geometry_source':'CATIA_SINGLE_BODY_EXPORT_CACHE_NOT_ORIGINAL_STEP','status':'NOT_EVALUATED',
        'scope':'104_RETAINED_EXPORT_CACHES_NOT_FULL_MODEL','selected_bodies':len(tasks),'expected_bspline_faces':expected,
        'processed_bspline_faces':len(faces),'deferred_bspline_faces':expected-len(faces),'worker_errors':sum(bool(r['worker_error']) for r in records),
        'recovered_types':types,'reason_counts':reasons,'changed_exterior_candidate_bodies':changed,'formal_result_unchanged':True,
        'design_cavity_confirmed':False,'engineering_pipe_confirmed':False,'records':records}
    (out/'export_surface_support_review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    report=f"# CATIA 导出缓存外形曲面复核\n\n本批仅检查此前保留的 104 个单 Body 导出缓存，不代表全模型；与原始 STEP 曲面恢复记录分开。\n\n其中 {len(tasks)} 个 Body 含 {expected} 张 BSpline 曲面，完成 {len(faces)} 张，未完成 {expected-len(faces)} 张，进程错误 {result['worker_errors']}。恢复类型：{types}。原因统计：{reasons}。\n\n辅助外形分类改变的 Body：{changed}。恢复曲面仅作为独立支撑几何证据，不修改源面、裁剪或拓扑。缓存摘要必须与先前显式导出记录一致，恢复面还须通过身份复核和误差检查。\n\n不要求或推断内孔，不认定空腔、壁厚、流道、开口或管路用途。外形候选允许实心杆等其他用途，全部保留 NOT_EVALUATED。源模型及正式干涉结果未改动。\n"
    (out/'导出缓存外形曲面复核.md').write_text(report,encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='records'},ensure_ascii=False))

if __name__=='__main__': main()
