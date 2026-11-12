"""Separate recovered supports from source descriptors; verify real adjacency."""
import concurrent.futures
import json
import subprocess
import sys
from pathlib import Path
from tools.review_surface_recovery_pilot import ROOT,digest

def worker(input_path,output):
    from catia_checker.occt_brep import OCCTBRepModel
    from catia_checker.geometry_fingerprint import compare_geometry_features
    from standalone.step_pipe_semantics.route_seeds import tangent_route_seeds
    from standalone.step_pipe_semantics.shared_topology import verify_seed_topology
    request=json.loads(input_path.read_text(encoding='utf-8')); sid=request['solid_id']
    path=ROOT/'artifacts/step_full_exterior_scan'/f'{sid}.json'
    detail=json.loads(path.read_text(encoding='utf-8')); model=OCCTBRepModel()
    sha=digest(path.with_suffix('.brep')); model.load_brep(sid,path.with_suffix('.brep')); model.solid_face_provenance(sid)
    saved={f['shape_id']:f for f in detail['faces']}; views=dict(saved); identities={}; accepted=[]
    for record in request['recovered_faces']:
        fid=record['face_id']; identity=compare_geometry_features(saved[fid],model.describe(fid)); identities[fid]=identity
        if not identity['compatible']: continue
        recovery=record['recovery']
        assert recovery['support_recovered'] and recovery['maximum_sample_error_mm']<=recovery['tolerance_mm']
        views[fid]={**saved[fid],'surface_features':{**(saved[fid].get('surface_features') or {}),
                                                  **recovery['recovered_support']}}
        accepted.append(fid)
    recovered=set(accepted)
    seeds=[s for s in tangent_route_seeds(list(views.values()))
           if recovered.intersection([s['torus_face_id'],*s['cylinder_face_ids']])]
    topology=verify_seed_topology(model,seeds,detail['faces'])
    for seed in topology['seeds']:
        seed['recovered_support_face_ids']=sorted(recovered.intersection([seed['torus_face_id'],*seed['cylinder_face_ids']]))
        seed['support_basis']='RECOVERED_ANALYTICAL_SUPPORT_WITH_ORIGINAL_TRIMMED_FACE_TOPOLOGY'
    assert digest(path.with_suffix('.brep'))==sha
    result={'solid_id':sid,'input_brep_sha256':sha,'recovered_face_count':len(request['recovered_faces']),
            'accepted_recovered_face_ids':accepted,'recovered_face_identity_checks':identities,**topology}
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')

def main():
    if len(sys.argv)>1: worker(Path(sys.argv[1]),Path(sys.argv[2])); return
    art=ROOT/'artifacts'; out=art/'step_recovered_route_supports'; out.mkdir(exist_ok=True)
    formal=art/'step_filter_local_evidence/turbine_source_evidence_filtered.json'; before=digest(formal)
    recovered={}
    for relative in ['step_surface_recovery_pilot/surface_recovery_pilot.json',
                     'step_surface_recovery_remaining/surface_recovery_pilot.json',
                     'step_surface_recovery_retry/chunk_recovery_review.json']:
        data=json.loads((art/relative).read_text(encoding='utf-8'))
        for record in data['records']:
            for face in record['faces']:
                if face['recovery']['support_recovered']:
                    assert face['face_id'] not in recovered
                    recovered[face['face_id']]=face
    groups={}
    for fid,face in recovered.items(): groups.setdefault(fid.split('::')[0],[]).append(face)
    tasks=[]
    for sid,faces in groups.items():
        request=out/(sid+'.input.json'); request.write_text(json.dumps({'solid_id':sid,'recovered_faces':faces},ensure_ascii=False),encoding='utf-8')
        tasks.append((sid,request,out/(sid+'.review.json')))
    def run(task):
        sid,request,target=task
        try:
            p=subprocess.run([sys.executable,__file__,str(request),str(target)],capture_output=True,text=True,timeout=60)
            if p.returncode: raise RuntimeError(f'EXIT_{p.returncode}: {p.stderr[-1000:]}')
            return json.loads(target.read_text(encoding='utf-8'))
        except Exception as exc: return {'solid_id':sid,'error':str(exc),'seeds':[],'accepted_recovered_face_ids':[]}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool: records=list(pool.map(run,tasks))
    seeds=[s for r in records for s in r['seeds']]; assert digest(formal)==before
    summary={'geometry_source':'ORIGINAL_STEP_NOT_CATIA_REEXPORT','status':'NOT_EVALUATED',
        'recovered_support_count':len(recovered),'solid_count':len(groups),
        'identity_accepted_recovered_faces':sum(len(r['accepted_recovered_face_ids']) for r in records),
        'worker_errors':sum('error' in r for r in records),'new_support_tangencies':len(seeds),
        'shared_edge_confirmed':sum(s['topology_verified'] for s in seeds),
        'formal_result_unchanged':True,'design_cavity_confirmed':False,'engineering_pipe_confirmed':False,'records':records}
    (out/'recovered_route_review.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    report=f"# 恢复曲面直弯连接复核\n\n来自原始 STEP 缓存的 {len(recovered)} 张恢复曲面，涉及 {len(groups)} 个实体。重新通过身份复核的恢复面为 {summary['identity_accepted_recovered_faces']} 张，工作进程错误 {summary['worker_errors']}。\n\n新增支撑几何相切线索 {len(seeds)} 条，其中 {summary['shared_edge_confirmed']} 条具有原始裁剪面的实际共享边界。\n\n恢复类型仅作为独立支撑几何证据；原始面描述、裁剪与拓扑保持不变。支撑相切可发生在裁剪范围之外，共享边界也不证明完整管路截面。\n\n所有线索仍为 NOT_EVALUATED，不确认外壁、空腔、壁厚、流道、设计连接或弯曲半径合规。与 CATIA 导出的无空腔模型分开记录。正式干涉结果保持不变。\n"
    (out/'恢复曲面直弯连接复核.md').write_text(report,encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k!='records'},ensure_ascii=False))

if __name__=='__main__': main()
