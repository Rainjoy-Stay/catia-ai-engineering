import json
import math
from tools.review_surface_recovery_pilot import ROOT,digest
from catia_checker.occt_brep import OCCTBRepModel
from catia_checker.geometry_fingerprint import compare_geometry_features
from standalone.step_pipe_semantics.shared_section_boundary import shared_section_boundary

def main():
    art=ROOT/'artifacts'; source=art/'step_recovered_route_supports'; out=art/'step_recovered_section_boundaries'; out.mkdir(exist_ok=True)
    formal=art/'step_filter_local_evidence/turbine_source_evidence_filtered.json'; before=digest(formal)
    review=json.loads((source/'recovered_route_review.json').read_text(encoding='utf-8')); records=[]
    for record in review['records']:
        if not record['seeds']: continue
        sid=record['solid_id']; path=art/'step_full_exterior_scan'/f'{sid}.json'; detail=json.loads(path.read_text(encoding='utf-8'))
        assert digest(path.with_suffix('.brep'))==record['input_brep_sha256']
        model=OCCTBRepModel(); model.load_brep(sid,path.with_suffix('.brep')); model.solid_face_provenance(sid)
        faces={f['shape_id']:f for f in detail['faces']}; supports={fid:f['surface_features'] for fid,f in faces.items()}
        request=json.loads((source/(sid+'.input.json')).read_text(encoding='utf-8'))
        for f in request['recovered_faces']:
            if f['face_id'] in record['accepted_recovered_face_ids']: supports[f['face_id']]=f['recovery']['recovered_support']
        identities={}
        for seed in record['seeds']:
            reference=supports[seed['torus_face_id']]; center=reference['axis_origin_mm']; normal=reference['axis_direction']; R=reference['major_radius_mm']; radius=reference['minor_radius_mm']
            grouped=[]
            for fid,s in supports.items():
                if not s or s.get('surface_type')!='TORUS': continue
                if abs(s['major_radius_mm']-R)>1e-5 or abs(s['minor_radius_mm']-radius)>1e-5 or math.dist(center,s['axis_origin_mm'])>1e-5 or abs(abs(sum(a*b for a,b in zip(normal,s['axis_direction'])))-1)>1e-8: continue
                if fid not in identities: identities[fid]=compare_geometry_features(faces[fid],model.describe(fid))
                if identities[fid]['compatible']: grouped.append(fid)
            radial=[(seed['support_tangent_point_mm'][i]-center[i])/R for i in range(3)]
            tangent=[normal[1]*radial[2]-normal[2]*radial[1],normal[2]*radial[0]-normal[0]*radial[2],normal[0]*radial[1]-normal[1]*radial[0]]
            length=math.sqrt(sum(v*v for v in tangent)); tangent=[v/length for v in tangent]
            evidence=shared_section_boundary(model,seed,grouped,tangent)
            records.append({'solid_id':sid,'seed':seed,'same_support_identity_verified_torus_face_ids':grouped,
                'same_support_identity_checks':{fid:identities[fid] for fid in grouped},'finite_boundary_evidence':evidence})
        assert digest(path.with_suffix('.brep'))==record['input_brep_sha256']
    assert digest(formal)==before and len(records)==review['new_support_tangencies']
    complete=sum(r['finite_boundary_evidence']['complete_boundary_circle_verified'] for r in records)
    classes={}
    for r in records:
        label=r['finite_boundary_evidence']['boundary_evidence_class']; classes[label]=classes.get(label,0)+1
    result={'status':'NOT_EVALUATED','geometry_source':'ORIGINAL_STEP_NOT_CATIA_REEXPORT','reviewed_seeds':len(records),
        'complete_local_shared_circles':complete,'boundary_evidence_classes':classes,
        'quarter_circle_only_count':sum(r['finite_boundary_evidence']['quarter_circle_only'] for r in records),
        'formal_result_unchanged':True,'records':records}
    (out/'recovered_section_boundaries.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    (out/'恢复曲面有限边界复核.md').write_text(f"# 恢复曲面有限边界复核\n\n检查 {len(records)} 条恢复曲面的直弯连接线索，其中 {complete} 条验证了完整局部共享圆形截面。\n\n使用原始裁剪面的实际共享边，合并经身份复核的同支撑环面片；圆弧须满足截面位置、半径、法向、闭合线框及总角度 2π。没有把 BSpline 参数当作环面角度，也没有修改源几何。\n\n未满足本检查的线索仅说明现有证据不足，不能判定模型没有管路。完整局部圆形截面也不证明曲面延续覆盖、外壁、空腔、壁厚或工程连接。所有结果仍为 NOT_EVALUATED；原始 STEP 与 CATIA 导出的无空腔模型分开记录。正式干涉结果未改动。\n\n3 项精确几何验收覆盖分片完整圆、缺失圆弧和错误截面法向。\n",encoding='utf-8')
    queue={'status':'NOT_EVALUATED','eligible_seeds':[r for r in records if r['finite_boundary_evidence']['eligible_for_centerline_continuation_test']],
        'deferred_seeds':[r for r in records if not r['finite_boundary_evidence']['eligible_for_centerline_continuation_test']],
        'limits':'Eligibility is local geometry only; deferred seeds do not prove absent pipes or cavities'}
    (out/'centerline_continuation_queue.json').write_text(json.dumps(queue,ensure_ascii=False,indent=2),encoding='utf-8')
    report=out/'恢复曲面有限边界复核.md'
    text=report.read_text(encoding='utf-8').replace('3 项精确几何验收覆盖分片完整圆、缺失圆弧和错误截面法向。',
        '4 项精确几何验收覆盖完整圆、缺失圆弧、错误截面法向及单个 90° 圆弧。')
    text+=f"\n边界证据分类：{classes}。仅 90° 圆弧 {result['quarter_circle_only_count']} 条。此类线索记录为局部开放截面，不进入后续中心线延续检查；仍保留待评估，不判定工程用途。共享边的曲线类型直接取自原始几何，未使用 BSpline 边恢复。\n"
    report.write_text(text,encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='records'},ensure_ascii=False))

if __name__=='__main__': main()
