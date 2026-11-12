"""Topology and finite-boundary review of recovered export supports."""
import json
import math
from pathlib import Path
from tools.review_surface_recovery_pilot import ROOT,digest
from catia_checker.occt_brep import OCCTBRepModel
from catia_checker.geometry_fingerprint import compare_geometry_features
from standalone.step_pipe_semantics.route_seeds import tangent_route_seeds
from standalone.step_pipe_semantics.shared_topology import verify_seed_topology
from standalone.step_pipe_semantics.shared_section_boundary import shared_section_boundary

def main():
    art=ROOT/'artifacts'; out=art/'step_export_recovered_connections'; out.mkdir(exist_ok=True)
    recovery=json.loads((art/'step_export_surface_supports/export_surface_support_review.json').read_text(encoding='utf-8'))
    pilot=json.loads((art/'step_pipe_semantics_pilot/turbine_pipe_pilot.json').read_text(encoding='utf-8'))
    items={r['solid_id']:r for r in pilot['records']}
    formal=art/'step_filter_local_evidence/turbine_source_evidence_filtered.json'; before=digest(formal)
    records=[]; recovered_count=0
    for r in recovery['records']:
        recovered={f['face_id']:f['recovery'] for f in r['faces'] if f['recovery']['support_recovered']}
        if not recovered: continue
        recovered_count+=len(recovered); item=items[r['solid_id']]; cache=Path(item['cache_file']); assert digest(cache)==item['cache_sha256']
        detail=json.loads((art/'step_pipe_semantics_pilot'/item['detail_file']).read_text(encoding='utf-8'))
        model=OCCTBRepModel(); model.load_brep(r['solid_id'],cache); model.solid_face_provenance(r['solid_id'])
        saved={f['shape_id']:f for f in detail['faces']}; views=dict(saved); identities={}; accepted=set()
        for fid,evidence in recovered.items():
            identity=compare_geometry_features(saved[fid],model.describe(fid)); identities[fid]=identity
            if not identity['compatible']: continue
            accepted.add(fid); views[fid]={**saved[fid],'surface_features':{**saved[fid]['surface_features'],**evidence['recovered_support']}}
        seeds=[s for s in tangent_route_seeds(list(views.values())) if accepted.intersection([s['torus_face_id'],*s['cylinder_face_ids']])]
        topology=verify_seed_topology(model,seeds,detail['faces']); sections=[]
        for seed in topology['seeds']:
            seed['recovered_support_face_ids']=sorted(accepted.intersection([seed['torus_face_id'],*seed['cylinder_face_ids']]))
            if not seed['topology_verified']:
                sections.append({'seed':seed,'boundary_review':{'status':'NOT_EVALUATED','reason':'SHARED_TOPOLOGY_UNCONFIRMED'}}); continue
            ref=views[seed['torus_face_id']]['surface_features']; center=ref['axis_origin_mm']; normal=ref['axis_direction']; R=ref['major_radius_mm']; radius=ref['minor_radius_mm']; grouped=[]
            for fid,face in views.items():
                s=face.get('surface_features') or {}
                if s.get('surface_type')!='TORUS': continue
                if abs(s['major_radius_mm']-R)>1e-5 or abs(s['minor_radius_mm']-radius)>1e-5 or math.dist(s['axis_origin_mm'],center)>1e-5 or abs(abs(sum(a*b for a,b in zip(s['axis_direction'],normal)))-1)>1e-8: continue
                if fid not in identities: identities[fid]=compare_geometry_features(saved[fid],model.describe(fid))
                if identities[fid]['compatible']: grouped.append(fid)
            radial=[(seed['support_tangent_point_mm'][i]-center[i])/R for i in range(3)]
            tangent=[normal[1]*radial[2]-normal[2]*radial[1],normal[2]*radial[0]-normal[0]*radial[2],normal[0]*radial[1]-normal[1]*radial[0]]
            norm=math.sqrt(sum(v*v for v in tangent)); tangent=[v/norm for v in tangent]
            boundary=shared_section_boundary(model,seed,grouped,tangent)
            sections.append({'seed':seed,'same_support_torus_face_ids':grouped,'boundary_review':boundary})
        assert digest(cache)==item['cache_sha256']
        records.append({'solid_id':r['solid_id'],'source_body_index':item['source_body_index'],
            'source_binding':item['source_binding'],'cache_sha256':item['cache_sha256'],
            'accepted_recovered_face_ids':sorted(accepted),'face_identity_checks':identities,
            'topology_identity_checks':topology['face_identity_checks'],'connections':sections})
    assert digest(formal)==before
    connections=[c for r in records for c in r['connections']]; classes={}
    for c in connections:
        label=c['boundary_review'].get('boundary_evidence_class','UNRESOLVED_BOUNDARY'); classes[label]=classes.get(label,0)+1
    result={'geometry_source':'CATIA_SINGLE_BODY_EXPORT_CACHE_NOT_ORIGINAL_STEP','status':'NOT_EVALUATED',
        'scope':'PARTIAL_RETAINED_EXPORT_CACHES_NOT_FULL_MODEL','recovered_support_count':recovered_count,
        'identity_accepted_support_count':sum(len(r['accepted_recovered_face_ids']) for r in records),
        'body_count':len(records),'new_support_tangencies':len(connections),
        'shared_edge_confirmed':sum(c['seed']['topology_verified'] for c in connections),
        'complete_local_shared_circles':sum(c['boundary_review'].get('complete_boundary_circle_verified',False) for c in connections),
        'boundary_evidence_classes':classes,'formal_result_unchanged':True,'design_cavity_confirmed':False,
        'engineering_pipe_confirmed':False,'records':records}
    (out/'export_recovered_connections.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    report=f"# 导出缓存恢复环面连接复核\n\n复核 CATIA 单 Body 导出缓存中的 {recovered_count} 张恢复曲面，涉及 {len(records)} 个 Body；{result['identity_accepted_support_count']} 张重新通过面身份检查。与原始 STEP 结果分开，不代表全模型。\n\n发现 {len(connections)} 条新增支撑相切线索，{result['shared_edge_confirmed']} 条具有实际共享边界，{result['complete_local_shared_circles']} 条通过完整局部共享圆形截面检查。边界分类：{classes}。\n\n只使用原始裁剪面实际共享边，完整圆须满足位置、半径、法向、闭合线框与总圆弧角度条件。恢复类型只是支撑几何，不替换源面。\n\n所有结果保留 NOT_EVALUATED，不确认空腔、壁厚、流道、设计管路、正常连接或半径合规。源缓存及正式干涉结果保持不变。没有跨 Body 合并曲面，也没有将原始 STEP 实体顺序套用于导出模型。\n"
    (out/'导出缓存恢复环面连接复核.md').write_text(report,encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='records'},ensure_ascii=False))

if __name__=='__main__': main()
