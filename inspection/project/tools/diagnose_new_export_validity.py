import concurrent.futures
import json
import subprocess
import sys
from pathlib import Path
from tools.review_surface_recovery_pilot import ROOT,digest

def worker(request_path,output):
    from OCP.STEPControl import STEPControl_Reader
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.TopAbs import TopAbs_SOLID
    from catia_checker.occt_brep import OCCTBRepModel,_subshapes
    from catia_checker.brep_validity_evidence import validity_evidence
    request=json.loads(request_path.read_text(encoding='utf-8')); record=request['solid_record']; body=request['body_record']
    step=Path(body['source_step_file']); cache=Path(record['cache_file']); step_sha=digest(step); cache_sha=digest(cache)
    assert step_sha==body['source_step_sha256'] and cache_sha==record['cache_sha256']
    sid=record['solid']['shape_id']; model=OCCTBRepModel(); model.load_brep(sid,cache)
    cached=validity_evidence(model._shape(sid),sid)
    reader=STEPControl_Reader(); assert reader.ReadFile(str(step))==IFSelect_RetDone and reader.TransferRoots()
    shapes=_subshapes(reader.OneShape(),TopAbs_SOLID)
    # This batch has exactly one Solid per explicit Body export; no cross-representation ordinal mapping.
    assert len(shapes)==body['solid_count']==1
    direct=validity_evidence(shapes[0],sid)
    assert digest(step)==step_sha and digest(cache)==cache_sha
    result={'source_body_index':body['source_body_index'],'geometry_source':'CATIA_NEW_SINGLE_BODY_EXPORT',
            'source_step_sha256':step_sha,'cache_sha256':cache_sha,'status':'NOT_EVALUATED',
            'cache':cached,'direct_step':direct,'invalid_already_in_direct_step':not direct['kernel_valid']}
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')

def main():
    if len(sys.argv)==3: worker(Path(sys.argv[1]),Path(sys.argv[2])); return
    art=ROOT/'artifacts'; directory=art/'step_export_expansion/batch_01'; out=directory/'validity_diagnostics'; out.mkdir(exist_ok=True)
    scan=json.loads((directory/'exterior_scan/batch_exterior_scan.json').read_text(encoding='utf-8')); tasks=[]
    formal=art/'step_filter_local_evidence/turbine_source_evidence_filtered.json'; before=digest(formal)
    for body in scan['records']:
        for solid in body['records']:
            if solid['solid']['valid']: continue
            request=out/f"BODY_{body['source_body_index']:06d}.input.json"; target=request.with_name(request.name.replace('.input','.diagnostic'))
            request.write_text(json.dumps({'body_record':body,'solid_record':solid},ensure_ascii=False),encoding='utf-8'); tasks.append((body['source_body_index'],request,target))
    def run(task):
        index,request,target=task
        try:
            p=subprocess.run([sys.executable,__file__,str(request),str(target)],capture_output=True,text=True,timeout=45)
            if p.returncode: raise RuntimeError(f'EXIT_{p.returncode}: {p.stderr[-800:]}')
            return json.loads(target.read_text(encoding='utf-8'))
        except Exception as exc: return {'source_body_index':index,'status':'NOT_EVALUATED','error':str(exc)}
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool: records=list(pool.map(run,tasks))
    assert digest(formal)==before
    result={'status':'NOT_EVALUATED','formal_result_unchanged':True,'worker_errors':sum('error' in r for r in records),'records':records}
    (out/'invalid_solid_review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['# 首批异常 Solid 只读复核','','检查 CATIA 新导入基线的单 Body 导出，不修改或修复几何。','']
    for r in records:
        if 'error' in r: lines.append(f"- Body {r['source_body_index']}：诊断未完成，{r['error']}"); continue
        codes=set()
        for issue in r['direct_step']['issues']:
            codes.update(issue['statuses'])
            for context in issue['contexts']: codes.update(context['statuses'])
        lines.append(f"- Body {r['source_body_index']}：直接读取 STEP 有效性 {r['direct_step']['kernel_valid']}；BREP 缓存有效性 {r['cache']['kernel_valid']}；异常类型 {sorted(codes)}；详细异常子形状 {len(r['direct_step']['issues'])} 个。")
    lines+=['','直接 STEP 与 BREP 均无效时，说明异常不是仅在 BREP 缓存保存后出现；尚不能区分原模型、CATIA 转换或 STEP 读取内核责任。异常子形状标识仅在本次 Solid 诊断内有效，不是跨文件 Face/Edge 来源。','',
            '所有异常结果保留 NOT_EVALUATED，不用于管路、空腔、壁厚或半径合规判定；正式干涉裁决文件保持不变。']
    (out/'首批异常实体复核.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps({'worker_errors':result['worker_errors'],'bodies':[
        {'body':r['source_body_index'],'error':r.get('error'),'direct_step_valid':r.get('direct_step',{}).get('kernel_valid'),
         'cache_valid':r.get('cache',{}).get('kernel_valid'),'issues':len(r.get('direct_step',{}).get('issues',[]))} for r in records]},ensure_ascii=False))

if __name__=='__main__': main()
