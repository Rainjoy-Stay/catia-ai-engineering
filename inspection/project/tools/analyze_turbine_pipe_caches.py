"""Partial turbine pilot; cache provenance stays separate from design semantics."""
import hashlib
import json
import subprocess
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from standalone.step_pipe_semantics import VERSION, connection_candidates


def main():
    root=Path(__file__).resolve().parents[1]; artifacts=root/'artifacts'
    source=artifacts/'step_filter_body_recheck'; output=artifacts/'step_pipe_semantics_pilot'
    output.mkdir(exist_ok=True)
    payload_path=artifacts/'step_filter_local_evidence'/'turbine_source_evidence_filtered.json'
    before=hashlib.sha256(payload_path.read_bytes()).hexdigest()
    audit=json.loads((source/'export_audit.json').read_text(encoding='utf-8'))
    jobs=[]; missing=[]
    for body in audit['body_mapping']:
        paths=sorted(source.glob(f"body_{body['source_body_index']}_STEP_SOLID_*.brep"))
        if not paths:
            missing.append({'body_index':body['source_body_index'],'reason':'NO_RETAINED_SOLID_CACHE'})
        for path in paths:
            jobs.append((body,path))
    def run(job):
        body,path=job; sid=path.stem.upper(); detail=output/(sid+'.json')
        record={'solid_id':sid,'source_body_index':body['source_body_index'],
                'source_body_name':body['source_body_name'],'cache_file':str(path.resolve()),
                'cache_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                'source_binding':'RETAINED_EXPLICIT_SINGLE_BODY_EXPORT_AUDIT',
                'status':'NOT_EVALUATED'}
        try:
            worker=subprocess.run([sys.executable,str(root/'tools'/'inspect_pipe_cache.py'),
                str(path),sid,str(detail)],timeout=30,capture_output=True,text=True)
            if worker.returncode:
                record['error']='GEOMETRY_WORKER_FAILED'
            else:
                value=json.loads(detail.read_text(encoding='utf-8'))
                record.update({k:value[k] for k in ('candidate','recognition_reasons','surface_type_counts')})
                record['detail_file']=detail.name
        except subprocess.TimeoutExpired:
            record['error']='GEOMETRY_WORKER_TIMEOUT'
        return record
    records=[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        for record in pool.map(run,jobs):
            records.append(record)
            if len(records)%20==0: print('Analyzed',len(records),'of',len(jobs),flush=True)
    connections=connection_candidates([r['candidate'] for r in records if 'candidate' in r])
    after=hashlib.sha256(payload_path.read_bytes()).hexdigest()
    if before!=after: raise RuntimeError('Formal interference result changed during read-only pilot')
    summary={'schema_version':VERSION,'scope':'PARTIAL_RETAINED_SINGLE_BODY_CACHES',
             'full_model_coverage':False,'exported_body_count':audit['exported_body_count'],
             'cache_count':len(jobs),'successful_count':sum('candidate' in r for r in records),
             'geometry_counts':dict(Counter(r.get('candidate',{}).get('geometry_kind','ERROR') for r in records)),
             'straight_diagnostic_counts':dict(Counter(r.get('recognition_reasons',{}).get('straight','WORKER_ERROR') for r in records)),
             'bend_diagnostic_counts':dict(Counter(r.get('recognition_reasons',{}).get('bend','WORKER_ERROR') for r in records)),
             'connection_candidate_count':len(connections),'missing_cache_bodies':missing,
             'interference_result_unchanged':before==after,'interference_sha256':before,
             'engineering_pipe_confirmed':False,'source_geometry_modified':False,
             'records':records,'connections':connections}
    (output/'turbine_pipe_pilot.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    counts=summary['geometry_counts']
    lines=['# 发动机管路几何候选试运行','',
           f"仅检查已有单 Body 导出缓存：{len(jobs)} 个 Solid，成功 {summary['successful_count']} 个；不是全模型扫描。",
           f"直管候选 {counts.get('STRAIGHT_HOLLOW_CANDIDATE',0)}；弯管候选 {counts.get('CIRCULAR_HOLLOW_BEND_CANDIDATE',0)}；未确定 {counts.get('UNDETERMINED',0)}；端口连接候选 {len(connections)}。",'',
           '所有结果均待评估。未确定不等于非管路。当前直管支持圆柱壁面碎分及多段圆弧端口；弯管仍要求双环面双端面。复杂管件、端面碎分和非解析面尚未支持。',
           '端口吻合不证明设计连接，也不能排除其他区域的穿模。原 23 项干涉待评估和正式结果文件保持不变，并通过前后 SHA256 核验。','',
           '| Body | 几何结果 | 直管诊断 | 弯管诊断 |','|---|---|---|---|']
    for r in records:
        reasons=r.get('recognition_reasons',{})
        lines.append(f"| {r['source_body_index']} | {r.get('candidate',{}).get('geometry_kind',r.get('error'))} | {reasons.get('straight','')} | {reasons.get('bend','')} |")
    lines+=['','完整尺寸、Face 来源、表面类型及端口数据见 turbine_pipe_pilot.json 和对应 Solid 详情文件。']
    (output/'管路识别试运行记录.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k not in ('records','connections','missing_cache_bodies')},ensure_ascii=False))


if __name__=='__main__': main()
