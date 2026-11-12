"""Independent evidence on spatially nearby representations; no identity inference."""
import hashlib
import json
from collections import Counter
from pathlib import Path
from OCP.BRep import BRep_Tool
from OCP.TopAbs import TopAbs_FACE, TopAbs_EDGE, TopAbs_VERTEX
from catia_checker.occt_brep import OCCTBRepModel
from catia_checker.geometry_fingerprint import compare_geometry_features
from standalone.step_pipe_semantics.bore_selection import select_straight_bore_review
from standalone.step_pipe_semantics.bore_evidence import inspect_straight_bore


def inspect(path, sid):
    model=OCCTBRepModel(); model.load_brep(sid,path)
    solid=model.describe(sid)
    faces=[model.describe(f) for f in model.solid_face_provenance(sid)['face_ids']]
    openings=[{'face_id':f['shape_id'],**b} for f in faces
              for b in (f.get('surface_features') or {}).get('circular_inner_boundaries',[])]
    selection=select_straight_bore_review({'faces':faces,'opening_seeds':openings})
    tolerance=max(1e-7,*(BRep_Tool.MaxTolerance_s(model._shape(sid),k)
                        for k in (TopAbs_FACE,TopAbs_EDGE,TopAbs_VERTEX)))
    result={'cache_file':str(path.resolve()),'cache_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'solid':solid,'faces':faces,'openings':openings,'selection':selection,
            'surface_counts':dict(Counter((f.get('surface_features') or {}).get('surface_type','UNKNOWN') for f in faces)),
            'local_tolerance_mm':tolerance,'design_cavity_confirmed':False,'fluid_channel_confirmed':False}
    if selection['eligible']:
        try:
            result['empty_region_evidence']=inspect_straight_bore(model,sid,selection['centers_mm'],
                selection['inner_radius_mm'],selection['radial_search_outer_radius_mm'],tolerance)
        except ValueError as e: result['deferred_reason']=str(e)
    return result


def main():
    artifacts=Path(__file__).resolve().parents[1]/'artifacts'
    output=artifacts/'step_representation_comparison'; output.mkdir(exist_ok=True)
    formal=artifacts/'step_filter_local_evidence'/'turbine_source_evidence_filtered.json'
    before=hashlib.sha256(formal.read_bytes()).hexdigest()
    audit=json.loads((artifacts/'step_filter_body_recheck'/'export_audit.json').read_text(encoding='utf-8'))
    records=[]
    for sid,body in [('SOURCE_SOLID_0835',833),('SOURCE_SOLID_0836',834)]:
        original=inspect(artifacts/'step_pipe_complex_discovery'/(sid+'.brep'),sid)
        exported=inspect(artifacts/'step_filter_body_recheck'/f'body_{body}_STEP_SOLID_0001.brep',f'EXPORTED_BODY_{body}')
        comparison=compare_geometry_features(original['solid'],exported['solid'])
        records.append({'original':original,'catia_export':exported,'comparison':comparison,
            'pairing_basis':'NEAREST_SPATIAL_MULTI_FEATURE_DIAGNOSTIC_ONLY',
            'cross_representation_identity_verified':False,'status':'NOT_EVALUATED',
            'export_body_audit':next(b for b in audit['body_mapping'] if b['source_body_index']==body)})
    assert hashlib.sha256(formal.read_bytes()).hexdigest()==before
    result={'scope':'TWO_ORIGINAL_SOLIDS_AND_TWO_NEARBY_EXPORTED_BODY_CACHES',
            'interference_result_unchanged':True,'records':records,
            'limits':'Independent single-solid observations do not confirm design cavities or whole-assembly channels'}
    (output/'representation_comparison.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['# 原始与导出几何证据对照','',
        '仅比较两个原始 STEP 实体缓存及空间最近的两个 CATIA 单 Body 导出缓存。严格对应检查未通过，不能宣称两套实体完全对应，也不能据此判断导出过程增加或丢失了空腔。',
        '用户提示导出 STP 没有空腔。以下将圆形边界、测试空区域、设计空腔和整机流道分别记录；任何局部几何空区域都不能确认设计空腔或流道。','',
        '| 表示 | Face 数 | 表面类型 | 闭合圆形内边界数 | 独立测试空区域 |',
        '|---|---:|---|---:|---|']
    for r in records:
        for key in ('original','catia_export'):
            v=r[key]; e=v.get('empty_region_evidence',{})
            lines.append(f"| {v['solid']['shape_id']} | {v['solid']['face_count']} | {v['surface_counts']} | {len(v['openings'])} | {e.get('clear_passage_witness_confirmed','未执行')} |")
        failed=[c['feature'] for c in r['comparison']['checks'] if not c['match']]
        print(r['original']['solid']['shape_id'],r['catia_export']['solid']['shape_id'], 'failed',failed,
              'export',r['catia_export']['surface_counts'],len(r['catia_export']['openings']),
              r['catia_export'].get('empty_region_evidence',{}).get('clear_passage_witness_confirmed'))
    lines+=['','两套表示分别建立测试轴和参数，未把原始 STEP 的孔口结论复制到导出几何。即便测试空区域存在，也只相对于所检查的单实体，周围零件可能占据该空间。',
            '本次不作“模型有空腔”或“导出保留空腔”的全局结论。工程空腔、壁厚和流道检查仍应按缺少设计空腔证据处理，保持 NOT_EVALUATED。后续应扩展基于外形的管状候选识别，避免以有内孔作为所有管路的前提。',
            '原 23 项干涉裁决文件通过前后摘要一致性检查。详细面记录、来源及失败的对应检查见 representation_comparison.json。']
    (output/'原始与导出几何对照.md').write_text('\n'.join(lines),encoding='utf-8')


if __name__=='__main__': main()
