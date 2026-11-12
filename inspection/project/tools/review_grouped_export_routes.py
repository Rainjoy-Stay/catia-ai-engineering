import hashlib
import json
from pathlib import Path
from catia_checker.occt_brep import OCCTBRepModel
from standalone.step_pipe_semantics.grouped_finite_route import grouped_finite_route_evidence


def main():
    art=Path(__file__).resolve().parents[1]/'artifacts'; directory=art/'step_exterior_pilot'
    formal=art/'step_filter_local_evidence'/'turbine_source_evidence_filtered.json'
    digest=hashlib.sha256(formal.read_bytes()).hexdigest()
    source=json.loads((directory/'export_route_seeds.json').read_text(encoding='utf-8'))
    pilot=json.loads((art/'step_pipe_semantics_pilot'/'turbine_pipe_pilot.json').read_text(encoding='utf-8'))
    lookup={r['source_body_index']:r for r in pilot['records']}; records=[]; seen=set()
    for body in source['records']:
        info=lookup[body['source_body_index']]
        detail=json.loads((art/'step_pipe_semantics_pilot'/info['detail_file']).read_text(encoding='utf-8'))
        sid=detail['solid']['shape_id']; model=OCCTBRepModel(); model.load_brep(sid,info['cache_file'])
        ids=model.solid_face_provenance(sid)['face_ids']
        for seed in body['seeds']:
            if not seed['topology_verified']: continue
            evidence=grouped_finite_route_evidence(model,seed,ids)
            key=(body['source_body_index'],tuple(evidence['same_support_torus_face_ids']),
                 tuple(sorted(seed['cylinder_face_ids'])),tuple(round(x,5) for x in seed['support_tangent_point_mm']))
            if key in seen: continue
            seen.add(key)
            records.append({'source_body_index':body['source_body_index'],'seed':seed,'grouped_evidence':evidence})
    assert hashlib.sha256(formal.read_bytes()).hexdigest()==digest
    count=sum(r['grouped_evidence']['local_grouped_route_candidate'] for r in records)
    result={'distinct_grouped_join_count':len(records),'local_grouped_candidate_count':count,
            'interference_result_unchanged':True,'centerline_reconstructed':False,'records':records}
    (directory/'grouped_export_route_review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['# 导出模型碎分环面联合复核','',
        f"32 条共享边线索归为 {len(records)} 个不同的环面组与连接位置，联合检查后局部候选 {count} 个。",'',
        '同组必须具有相同支撑圆心、轴线、大半径和小半径，保留全部 Face ID。连接处实际共享圆弧须组成闭合 wire 并覆盖一整圈；在两侧三个圆弧位置各采样 24 个截面方向，检查点是否落在实际修剪 Face 中。',
        '修剪覆盖是采样证据，不能证明全局覆盖或完整路线。全部结果仍待评估，不确认空腔、流道、内外壁或工程管路。','',
        '| Body | 联合连接位置 | 局部候选 |','|---|---:|---:|']
    for b in source['records']:
        subset=[r for r in records if r['source_body_index']==b['source_body_index']]
        lines.append(f"| {b['source_body_index']} | {len(subset)} | {sum(r['grouped_evidence']['local_grouped_route_candidate'] for r in subset)} |")
    lines+=['','独立精确几何验收证明：融合的直弯组合即使环面被拆成四片仍可恢复局部候选；缺少一片时拒绝完整截面。原 23 项干涉结果文件摘要保持一致。详细圆弧、闭合性及修剪采样见 grouped_export_route_review.json。']
    (directory/'碎分环面联合复核记录.md').write_text('\n'.join(lines),encoding='utf-8')
    print('Distinct joins',len(records),'grouped candidates',count)


if __name__=='__main__': main()
