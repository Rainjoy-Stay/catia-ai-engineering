import hashlib
import json
from pathlib import Path
from catia_checker.occt_brep import OCCTBRepModel
from standalone.step_pipe_semantics.finite_route import finite_route_evidence


def main():
    art=Path(__file__).resolve().parents[1]/'artifacts'; directory=art/'step_exterior_pilot'
    formal=art/'step_filter_local_evidence'/'turbine_source_evidence_filtered.json'
    digest=hashlib.sha256(formal.read_bytes()).hexdigest()
    source=json.loads((directory/'export_route_seeds.json').read_text(encoding='utf-8'))
    pilot=json.loads((art/'step_pipe_semantics_pilot'/'turbine_pipe_pilot.json').read_text(encoding='utf-8'))
    lookup={r['source_body_index']:r for r in pilot['records']}
    records=[]
    for body in source['records']:
        info=lookup[body['source_body_index']]
        detail=json.loads((art/'step_pipe_semantics_pilot'/info['detail_file']).read_text(encoding='utf-8'))
        sid=detail['solid']['shape_id']; model=OCCTBRepModel(); model.load_brep(sid,info['cache_file']); model.solid_face_provenance(sid)
        for seed in body['seeds']:
            if not seed['topology_verified']: continue
            evidence=finite_route_evidence(model,seed)
            records.append({'source_body_index':body['source_body_index'],'seed':seed,'finite_evidence':evidence})
    assert hashlib.sha256(formal.read_bytes()).hexdigest()==digest
    count=sum(r['finite_evidence'].get('local_full_section_route_candidate',False) for r in records)
    result={'checked_shared_topology_join_count':len(records),'local_full_section_candidate_count':count,
            'centerline_reconstructed':False,'interference_result_unchanged':True,'records':records}
    (directory/'export_finite_route_review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['# 导出模型有限截面复核','',
        f"复核 {len(records)} 条具有共享边界的连接，{count} 条满足局部完整圆形边界与完整环面截面包络条件。",'',
        '实际共享 Edge 的曲线必须形成以相切点为中心、半径等于截面半径的完整圆周。还要求环面 V 参数跨度为完整一圈。参数包络不证明修剪面内无缺口，局部通过仍不等于整段管路成立。',
        '未通过条件的连接保持曲面相邻线索，不能用来重建完整管路中心线，也不能将环面大半径签发为工程弯曲半径。设计空腔和流道仍未确认。','',
        '| Body | 检查连接数 | 局部完整截面候选 |','|---|---:|---:|']
    for b in source['records']:
        subset=[r for r in records if r['source_body_index']==b['source_body_index']]
        lines.append(f"| {b['source_body_index']} | {len(subset)} | {sum(r['finite_evidence'].get('local_full_section_route_candidate',False) for r in subset)} |")
    lines+=['','全部结果仍待评估，原 23 项干涉文件摘要保持一致。详细共享边界曲线、圆心偏差和 UV 范围见 export_finite_route_review.json。']
    (directory/'有限截面复核记录.md').write_text('\n'.join(lines),encoding='utf-8')
    print('Checked',len(records),'full-section local candidates',count)


if __name__=='__main__': main()
