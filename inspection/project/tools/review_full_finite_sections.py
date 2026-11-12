import hashlib
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def main():
    art=Path(__file__).resolve().parents[1]/'artifacts'; scan=art/'step_full_exterior_scan'
    source=scan/'shared_topology_review'; out=scan/'finite_section_review'; out.mkdir(exist_ok=True)
    formal=art/'step_filter_local_evidence'/'turbine_source_evidence_filtered.json'
    digest=hashlib.sha256(formal.read_bytes()).hexdigest()
    topology=json.loads((source/'full_seed_topology_review.json').read_text(encoding='utf-8'))
    targets=[r for r in topology['records'] if any(s['topology_verified'] for s in r.get('seeds',[]))]
    def inspect(record):
        sid=record['solid_id']; output=out/(sid+'.sections.json')
        item={'solid_id':sid,'expected_join_count':sum(s['topology_verified'] for s in record['seeds'])}
        try:
            process=subprocess.run([sys.executable,str(Path(__file__).with_name('inspect_full_finite_sections.py')),
                str(scan/(sid+'.json')),str(source/record['detail_file']),str(output)],
                timeout=60,capture_output=True,text=True)
            if process.returncode: item['error']='FINITE_SECTION_WORKER_FAILED'
            else:
                detail=json.loads(output.read_text(encoding='utf-8'))
                assert len(detail['records'])==item['expected_join_count']
                item['joins']=detail['records']; item['detail_file']=output.name
        except subprocess.TimeoutExpired: item['error']='FINITE_SECTION_WORKER_TIMEOUT'
        return item
    records=[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        for r in pool.map(inspect,targets):
            records.append(r)
            if len(records)%10==0: print('Section review solids',len(records),'of',len(targets),flush=True)
    assert hashlib.sha256(formal.read_bytes()).hexdigest()==digest
    joins=[j for r in records for j in r.get('joins',[])]
    result={'expected_join_count':topology['shared_topology_count'],'processed_join_count':len(joins),
        'worker_error_count':sum('error' in r for r in records),
        'complete_boundary_count':sum(j['finite_evidence']['complete_boundary_circle_verified'] for j in joins),
        'local_candidate_count':sum(j['finite_evidence']['local_grouped_route_candidate'] for j in joins),
        'coverage_deferred_count':sum(bool(j['finite_evidence'].get('coverage_deferred_reason')) for j in joins),
        'geometry_source':'ORIGINAL_STEP_NOT_CATIA_REEXPORT','interference_result_unchanged':True,
        'engineering_pipe_confirmed':False,'design_cavity_confirmed':False,'records':records}
    (out/'full_finite_section_review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['# 全模型有限截面与碎分环面复核','',
        f"预期 {result['expected_join_count']} 条共享边连接，完成 {len(joins)} 条，工作进程异常 {result['worker_error_count']} 个。",
        f"完整闭合圆形边界 {result['complete_boundary_count']} 条；完成后续修剪覆盖采样并形成局部候选 {result['local_candidate_count']} 条。",'',
        '同支撑环面碎片联合检查前，逐 Face 重新核验缓存空间与拓扑对应。连接圆弧必须以目标相切点为圆心、截面半径一致、组成闭合 wire 并覆盖一整圈。',
        f"{result['coverage_deferred_count']} 条因边界已不完整而未运行修剪覆盖采样；这不证明曲面不存在或该零件不是管路。完整边界才继续在两侧三处圆弧位置、24 个截面方向检查实际修剪面覆盖。",
        '修剪覆盖是采样证据，局部通过也不证明全局覆盖、工程中心线、空腔或流道。来源为原始 STEP，不能移用于 CATIA 重导出几何。原 23 项干涉裁决文件摘要保持一致。','',
        '| Solid | 检查连接 | 局部候选 |','|---|---:|---:|']
    for r in records: lines.append(f"| {r['solid_id']} | {len(r.get('joins',[]))} / {r['expected_join_count']} | {sum(j['finite_evidence']['local_grouped_route_candidate'] for j in r.get('joins',[]))} |")
    lines+=['','详细闭合性、圆弧跨度、Face 来源及覆盖采样见 full_finite_section_review.json 和各实体 sections.json。']
    (out/'全模型有限截面复核记录.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='records'}),flush=True)


if __name__=='__main__': main()
