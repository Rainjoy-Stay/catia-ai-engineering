"""Relocatable current spatial workflow. Geometry is never supplied by AI."""
import argparse,json,os,sys,subprocess,hashlib,math
from pathlib import Path
from datetime import datetime
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'project'),str(ROOT/'scripts')]
def save(folder,name,value):
    p=folder/name;p.write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str),encoding='utf8')
def event(stage,**kw):print(json.dumps({'stage':stage,**kw},ensure_ascii=False),flush=True)
def run(script,folder,*args,env=None):
    subprocess.run([sys.executable,str(ROOT/'project/tools/current'/script),str(folder),*map(str,args)],cwd=ROOT,env=env,check=True)
def prepare(folder,config):
    from r18_connection import R18Connection
    from catia_checker.occt_brep import OCCTBRepModel
    from catia_checker.catia_body_batches import export_geometrical_sets
    c=R18Connection();info=c.connect();d=c.active_document
    if not hasattr(d,'Part'):raise RuntimeError('空间框入口需要活动 CATPart；CATProduct 使用装配检查入口。')
    config['document']=str(d.Name);save(folder,'run-config.json',config)
    save(folder,'run-started.json',{'started':datetime.now().isoformat(),'historical_geometry_read':False,'historical_measurements_read':False})
    names={str(d.Part.Bodies.Item(i).Name):i for i in range(1,d.Part.Bodies.Count+1)}
    if len(names)!=d.Part.Bodies.Count:raise RuntimeError('Body 名称不唯一，不能按序猜测来源。')
    save(folder,'manifest-before.json',{'document':str(d.Name),'connection':info,'summary':{'total_bodies':d.Part.Bodies.Count},'bodies':names,'saved':bool(d.Saved)})
    event('FULL_EXPORT_START',operation='从当前活动模型重新导出')
    source=folder/'current-full-model.stp';d.ExportData(str(source),'stp')
    save(folder,'full-export-audit.json',{'file':source.name,'bytes':source.stat().st_size,'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'document':str(d.Name),'source_saved_by_tool':False})
    event('FULL_EXPORT_COMPLETE',operation='当前全模型导出完成')
    (folder/'surfaces').mkdir(exist_ok=True)
    surfaces=export_geometrical_sets(c.app,d,folder/'surfaces',batch_size=40,bulk_copy=True,progress=lambda e:event(e.pop('stage'),**e));save(folder,'surface-export-audit.json',surfaces)
    m=OCCTBRepModel();mf=m.load_step(source);save(folder,'fresh-geometry-manifest.json',mf)
    records=[(names[s['source_name']],s) for s in mf['shapes'] if s.get('source_name') in names and s.get('solid_count')==1 and s.get('bounds_mm') and all(math.isfinite(v) and abs(v)<1e6 for v in s['bounds_mm']['min']+s['bounds_mm']['max'])]
    if not records:raise RuntimeError('当前模型没有唯一名称映射的有限实体')
    save(folder,'full-body-mapping-audit.json',{'native_body_count':d.Part.Bodies.Count,'fresh_finite_mapped_solid_count':len(records),'unmapped_body_indices':sorted(set(names.values())-{i for i,s in records})})
    center=config.get('center_mm')
    if center is None:
        low=[min(s['bounds_mm']['min'][k] for i,s in records) for k in range(3)]
        high=[max(s['bounds_mm']['max'][k] for i,s in records) for k in range(3)]
        center=[(low[k]+high[k])/2 for k in range(3)];center[0]=low[0]+(high[0]-low[0])*.25
    ordered=sorted((max(max(s['bounds_mm']['min'][k]-center[k],center[k]-s['bounds_mm']['max'][k],0) for k in range(3)),i) for i,s in records)
    target=min(config['target_bodies'],len(ordered));half=config.get('half_size_mm')
    if half is None:half=(ordered[target-1][0]+ordered[target][0])/2 if target<len(ordered) else ordered[-1][0]+1e-4
    selected=sorted(i for distance,i in ordered if distance<=half)
    save(folder,'revised-scope-plan.json',{'center_mm':center,'half_size_mm':half,'selected_body_indices':selected,'selection_method':'CURRENT_MODEL_AABB_REGION','requested_body_count':config['target_bodies']})
    event('SCOPE_READY',operation=f'空间框纳入 {len(selected)} 个 Body；同框有限面壳全部纳入')
    run('complete40_worker.py',folder,config['workers'])
def finish(folder,capture=True):
    run('reclassify40_piping.py',folder)
    run('scan40_swept_routes.py',folder)
    baseline=json.loads((folder/'样条管路中心线检查.json').read_text(encoding='utf8'))
    env=dict(os.environ,CATIA_ROUTE_STATIONS='401');run('scan40_swept_routes.py',folder,env=env)
    refined=json.loads((folder/'样条管路中心线检查.json').read_text(encoding='utf8'))
    for r in refined['routes']:
        old=next((x for x in baseline['routes'] if x['shape_id']==r['shape_id'] and x['face_indices']==r['face_indices']),None)
        values=[x for x in [r.get('minimum_stable_bend_radius_mm'),old.get('minimum_stable_bend_radius_mm') if old else None] if x is not None]
        r['radius_range_mm']=[min(values),max(values)] if values else None
        r['sampling_verified']=bool(old);r['engineering_radius_status']='NOT_EVALUATED_NO_SPEC'
    save(folder,'中心线加密采样验证.json',{'baseline':baseline,'refined':refined})
    save(folder,'样条管路中心线检查.json',refined)
    check=json.loads((folder/'check.json').read_text(encoding='utf8'));check['swept_route_review']=refined;save(folder,'check.json',check)
    if capture:
        try:run('complete40_capture.py',folder)
        except subprocess.CalledProcessError as e:save(folder,'capture-error.json',{'error':str(e),'status':'INCOMPLETE_EVIDENCE'})
    run('portable_report.py',folder)
    save(folder,'run-completed.json',{'completed':datetime.now().isoformat(),'report_generated':True})
    event('DELIVERY_COMPLETE',operation='检查、管形识别与报告已写入本轮目录')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run-directory',type=Path,required=True);p.add_argument('--finish-only',action='store_true');p.add_argument('--no-capture',action='store_true');args=p.parse_args()
    folder=args.run_directory.resolve();folder.mkdir(parents=True,exist_ok=True);config=json.loads((folder/'run-config.json').read_text(encoding='utf8'))
    if not args.finish_only:prepare(folder,config)
    finish(folder,not args.no_capture)
