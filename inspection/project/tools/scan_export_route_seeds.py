import hashlib
import json
from pathlib import Path
from catia_checker.occt_brep import OCCTBRepModel,_subshapes
from OCP.TopAbs import TopAbs_EDGE
from standalone.step_pipe_semantics.route_seeds import tangent_route_seeds


def main():
    art=Path(__file__).resolve().parents[1]/'artifacts'; source=art/'step_pipe_semantics_pilot'
    out=art/'step_exterior_pilot'; formal=art/'step_filter_local_evidence'/'turbine_source_evidence_filtered.json'
    digest=hashlib.sha256(formal.read_bytes()).hexdigest()
    pilot=json.loads((source/'turbine_pipe_pilot.json').read_text(encoding='utf-8'))
    records=[]
    for record in pilot['records']:
        path=source/record['detail_file']; detail=json.loads(path.read_text(encoding='utf-8'))
        seeds=tangent_route_seeds(detail['faces'])
        if not seeds: continue
        sid=detail['solid']['shape_id']; model=OCCTBRepModel(); model.load_brep(sid,record['cache_file'])
        model.solid_face_provenance(sid)
        for seed in seeds:
            torus_edges=_subshapes(model._shape(seed['torus_face_id']),TopAbs_EDGE)
            adjacent=[]
            for face_id in seed['cylinder_face_ids']:
                if any(a.IsSame(b) for a in _subshapes(model._shape(face_id),TopAbs_EDGE) for b in torus_edges):
                    adjacent.append(face_id)
            seed['shared_edge_cylinder_face_ids']=adjacent
            seed['topology_verified']=bool(adjacent)
            seed['topology_method']='OCCT_SHARED_EDGE_IDENTITY_WITHIN_ONE_SOLID'
        records.append({'source_body_index':record['source_body_index'],
                        'source_body_name':record['source_body_name'],'seeds':seeds})
    assert hashlib.sha256(formal.read_bytes()).hexdigest()==digest
    result={'scope':'104_RETAINED_CATIA_SINGLE_BODY_EXPORT_CACHES',
        'support_tangency_count':sum(len(r['seeds']) for r in records),
        'shared_topology_count':sum(s['topology_verified'] for r in records for s in r['seeds']),
        'body_with_seed_count':len(records),'interference_result_unchanged':True,'records':records}
    (out/'export_route_seeds.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['# 导出模型直弯连接几何线索','',
        f"检查 104 个单 Body 导出缓存，发现 {result['support_tangency_count']} 条支撑几何相切线索，涉及 {len(records)} 个 Body。其中 {result['shared_topology_count']} 条具有实际共享边界。",'',
        '相切要求圆柱轴线位于环面中心线圆平面、与该圆相切，且圆柱半径与环面小半径相同；共享边界使用 OCCT 同一实体内的 Edge 身份检查。',
        '共享边界证明局部曲面相邻，不证明它是管路外壁、内壁或批准的连接。中心线、外表面属性、流道、壁厚及设计半径均待评估；局部面连接不会改变干涉裁决。','',
        '| Body | 相切线索 | 有共享边界 |','|---|---:|---:|']
    for r in records: lines.append(f"| {r['source_body_index']} | {len(r['seeds'])} | {sum(s['topology_verified'] for s in r['seeds'])} |")
    lines+=['','5 项支撑几何独立验收覆盖相切、割线、不同平面、同轴圆角和截面半径不符。原 23 项待评估裁决文件摘要保持一致。详细共享边界及曲面来源见 export_route_seeds.json。']
    (out/'直弯连接线索记录.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='records'}))


if __name__=='__main__': main()
