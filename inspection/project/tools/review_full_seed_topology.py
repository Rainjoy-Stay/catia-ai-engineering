import hashlib
import json
import subprocess
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def main():
    art=Path(__file__).resolve().parents[1]/'artifacts'; source=art/'step_full_exterior_scan'
    out=source/'shared_topology_review'; out.mkdir(exist_ok=True)
    formal=art/'step_filter_local_evidence'/'turbine_source_evidence_filtered.json'
    digest=hashlib.sha256(formal.read_bytes()).hexdigest()
    scan=json.loads((source/'full_exterior_scan.json').read_text(encoding='utf-8'))
    targets=[r for r in scan['records'] if r.get('support_tangency_seed_count',0)>0]
    def inspect(record):
        sid=record['solid_id']; output=out/(sid+'.topology.json')
        item={'solid_id':sid,'expected_seed_count':record['support_tangency_seed_count'],
              'geometry_source':'ORIGINAL_STEP_NOT_CATIA_REEXPORT','status':'NOT_EVALUATED'}
        try:
            process=subprocess.run([sys.executable,str(Path(__file__).with_name('inspect_full_seed_topology.py')),
                str(source/record['detail_file']),str(output)],timeout=45,capture_output=True,text=True)
            if process.returncode: item['error']='TOPOLOGY_WORKER_FAILED'
            else:
                value=json.loads(output.read_text(encoding='utf-8'))
                if len(value['seeds'])!=item['expected_seed_count']: raise ValueError('Seed count mismatch')
                item['seeds']=value['seeds']; item['detail_file']=output.name
                item['verified_face_count']=sum(c['compatible'] for c in value['face_identity_checks'].values())
                item['referenced_face_count']=len(value['face_identity_checks'])
        except subprocess.TimeoutExpired: item['error']='TOPOLOGY_WORKER_TIMEOUT'
        return item
    records=[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        for r in pool.map(inspect,targets):
            records.append(r)
            if len(records)%20==0: print('Reviewed solids',len(records),'of',len(targets),flush=True)
    assert hashlib.sha256(formal.read_bytes()).hexdigest()==digest
    seeds=[s for r in records for s in r.get('seeds',[])]
    result={'scope':'ORIGINAL_STEP_FULL_SCAN_SUPPORT_TANGENCY_SEEDS',
        'expected_seed_count':scan['support_tangency_seed_count'],'processed_seed_count':len(seeds),
        'solid_with_seeds_count':len(targets),'worker_error_count':sum('error' in r for r in records),
        'reason_counts':dict(Counter(s['reason'] for s in seeds)),
        'shared_topology_count':sum(s['topology_verified'] for s in seeds),
        'interference_result_unchanged':True,'engineering_pipe_confirmed':False,
        'catia_body_identity_verified':False,'records':records}
    (out/'full_seed_topology_review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['# 全模型相切线索共享边界复核','',
        f"预期 {result['expected_seed_count']} 条相切线索，涉及 {len(targets)} 个原始 STEP Solid；完成 {len(seeds)} 条，工作进程异常 {result['worker_error_count']} 个。",
        f"实际共享边界 {result['shared_topology_count']} 条。诊断分布：{result['reason_counts']}。",'',
        '每个引用 Face 在缓存读取后重新核验体积、面积、重心、绝对包围盒及拓扑计数，再以同一 Edge 身份确认实际邻接。未通过 Face 对应核验的线索保留未评估。',
        '共享边界只证明局部相邻，尚需完整截面、有限修剪覆盖及整段外形证据，不能直接重建工程中心线或确认空腔、流道、正常连接。',
        '来源为原始 STEP 的缓存，不移用于 CATIA 重导出 STP。CATIA Body 对应未确认；局部注册编号不是 STEP 实体号。','',
        '| Solid | 相切线索 | 实际共享边界 | Face 对应核验 |','|---|---:|---:|---|']
    for r in records:
        lines.append(f"| {r['solid_id']} | {r['expected_seed_count']} | {sum(s['topology_verified'] for s in r.get('seeds',[]))} | {r.get('verified_face_count','未完成')} / {r.get('referenced_face_count','')} |")
    lines+=['','原 23 项干涉裁决文件摘要保持一致。详细 Face 核验见各实体 topology.json；汇总见 full_seed_topology_review.json。']
    (out/'全模型共享边界复核记录.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='records'}),flush=True)


if __name__=='__main__': main()
