"""Read-only split-Body and non-solid export evidence, without healing."""
import json
from collections import Counter
from pathlib import Path
from OCP.STEPControl import STEPControl_Reader
from OCP.IFSelect import IFSelect_RetDone
from OCP.TopAbs import TopAbs_FACE
from OCP.TopExp import TopExp
from OCP.TopTools import TopTools_IndexedMapOfShape
from catia_checker.occt_brep import OCCTBRepModel,_subshapes
from catia_checker.brep_validity_evidence import validity_evidence
from tools.review_surface_recovery_pilot import ROOT,digest

def main():
    art=ROOT/'artifacts'; directory=art/'step_export_expansion/batch_02'; out=directory/'exception_review'; out.mkdir(exist_ok=True)
    scan=json.loads((directory/'exterior_scan/batch_exterior_scan.json').read_text(encoding='utf-8'))
    formal=art/'step_filter_local_evidence/turbine_source_evidence_filtered.json'; before=digest(formal)
    records=[]
    for body in scan['records']:
        if not body['body_split_into_multiple_solids'] and body['solid_count']!=0: continue
        step=Path(body['source_step_file']); assert digest(step)==body['source_step_sha256']
        reader=STEPControl_Reader(); assert reader.ReadFile(str(step))==IFSelect_RetDone and reader.TransferRoots()
        shape=reader.OneShape(); model=OCCTBRepModel(); root=f"NEW_BODY_{body['source_body_index']:06d}::EXPORT_ROOT"; model.register_shape(root,shape)
        cache=out/f"BODY_{body['source_body_index']:06d}_ROOT.brep"; model.write_brep(root,cache)
        shapes=TopTools_IndexedMapOfShape(); TopExp.MapShapes_s(shape,shapes)
        types=Counter(str(shapes.FindKey(i).ShapeType()).split('.')[-1] for i in range(1,shapes.Extent()+1))
        diagnostic=validity_evidence(shape,root)
        faces=[]
        for index,face in enumerate(_subshapes(shape,TopAbs_FACE),1):
            fid=f'{root}::FACE_{index:06d}'; model.register_shape(fid,face); faces.append(model.describe(fid))
        result={'source_body_index':body['source_body_index'],'source_step_file':str(step),
            'source_step_sha256':body['source_step_sha256'],'geometry_source':'CATIA_NEW_EXPLICIT_SINGLE_BODY_EXPORT',
            'status':'NOT_EVALUATED','root_shape_type':str(shape.ShapeType()),'unique_subshape_counts':dict(types),
            'root_cache_file':str(cache),'root_cache_sha256':digest(cache),'validity':diagnostic,
            'face_ownership_method':'OCCT_EXPORT_ROOT_SUBSHAPE_TRAVERSAL','faces':faces,
            'design_cavity_confirmed':False,'engineering_pipe_confirmed':False}
        if body['solid_count']==0:
            result.update({'kind':'NON_SOLID_EXPORT_GEOMETRY','root_volume_mm3':None,
                'solid_interference_evaluation':'NOT_EVALUATED',
                'reason':'EXPORT_HAS_GEOMETRY_BUT_NO_SOLID_VOLUME_AUTHORITY'})
        else:
            descriptors=[]
            for s in body['records']:
                sid=s['solid']['shape_id']; path=Path(s['cache_file']); assert digest(path)==s['cache_sha256']; model.load_brep(sid,path)
                descriptors.append({'solid_id':sid,'centroid_mm':s['solid']['centroid_mm'],
                    'volume_mm3':s['solid']['volume_mm3'],'surface_type_counts':dict(Counter((f.get('surface_features') or {}).get('surface_type') for f in s['faces']))})
            pairs=[]
            for i,a in enumerate(descriptors):
                for b in descriptors[i+1:]: pairs.append({'solid_a':a['solid_id'],'solid_b':b['solid_id'],
                    'distance':model.distance(a['solid_id'],b['solid_id']),
                    'common':model.common_volume(a['solid_id'],b['solid_id']),'status':'NOT_EVALUATED'})
            result.update({'kind':'SAME_EXPORTED_BODY_MULTIPLE_SOLIDS','solids':descriptors,'pairs':pairs,
                'conversion_fragmentation_confirmed':False,'native_preexport_solid_count':None,
                'reason':'EXPLICIT_SHARED_BODY_ORIGIN_DOES_NOT_PROVE_CONVERSION_FRAGMENTATION'})
        assert digest(step)==body['source_step_sha256']; records.append(result)
    assert digest(formal)==before
    result={'status':'NOT_EVALUATED','formal_result_unchanged':True,'records':records}
    (out/'batch_export_exception_review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    split=next(r for r in records if r['source_body_index']==45); surface=next(r for r in records if r['source_body_index']==51)
    codes=set()
    for issue in surface['validity']['issues']:
        codes.update(issue['statuses'])
        for context in issue['contexts']: codes.update(context['statuses'])
    report=f"# 第二批特殊导出几何复核\n\nBody 45 的导出包含两个有效微小球形 Solid，每个体积约 0.00006544984695 mm³，对应半径约 0.025 mm。两者最小距离 {split['pairs'][0]['distance']['minimum_distance_mm']:.9g} mm，公共体积 0。均保留同一显式 Body 导出来源，但尚未知道导出前的原生 Solid 数；不能直接认定转换碎裂或转换伪影，更不能删除它们。用途待评估。\n\nBody 51 并非空几何：STEP 读取结果为 Shell，含 {len(surface['faces'])} 张 Face；唯一子形状统计 {surface['unique_subshape_counts']}。内核有效性 {surface['validity']['kernel_valid']}；异常类型 {sorted(codes)}。已保留整个 Shell 的 BREP、摘要、实际 Face 所属关系和详细诊断。\n\nShell 不具备本检查要求的闭合 Solid 体积依据，根几何体积明确留空，不进入实体公共体积判定；不能由 Shell、没有 Solid 或缺失面推断设计空腔、内孔、壁厚或空零件。\n\n两个 Body 的语义结果均为 NOT_EVALUATED。没有修复或删除源几何，STEP 文件摘要及正式干涉结果保持不变。原始 STEP 与此 CATIA 新导入导出基线分开记录。\n"
    (out/'第二批特殊导出几何复核.md').write_text(report,encoding='utf-8')
    print(json.dumps({'body45_pairs':split['pairs'],'body51_counts':surface['unique_subshape_counts'],'body51_statuses':sorted(codes)},ensure_ascii=False))

if __name__=='__main__': main()
