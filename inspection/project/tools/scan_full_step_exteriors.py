"""All transferred STEP solids, exterior-only recognition and retained face evidence."""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from OCP.STEPControl import STEPControl_Reader
from OCP.IFSelect import IFSelect_RetDone
from OCP.TopAbs import TopAbs_SOLID
from catia_checker.occt_brep import OCCTBRepModel,_subshapes
from standalone.step_pipe_semantics.exterior import exterior_candidate
from standalone.step_pipe_semantics.route_seeds import tangent_route_seeds


def main():
    p=argparse.ArgumentParser(); p.add_argument('source',type=Path); p.add_argument('output',type=Path)
    a=p.parse_args(); a.output.mkdir(parents=True,exist_ok=True)
    art=Path(__file__).resolve().parents[1]/'artifacts'
    formal=art/'step_filter_local_evidence'/'turbine_source_evidence_filtered.json'
    formal_digest=hashlib.sha256(formal.read_bytes()).hexdigest() if formal.exists() else None
    source_digest=hashlib.sha256(a.source.read_bytes()).hexdigest()
    reader=STEPControl_Reader()
    if reader.ReadFile(str(a.source.resolve()))!=IFSelect_RetDone: raise RuntimeError('STEP read failed')
    print('STEP read complete',flush=True)
    if reader.TransferRoots()<=0: raise RuntimeError('STEP transfer failed')
    shapes=_subshapes(reader.OneShape(),TopAbs_SOLID); print('Transferred solids',len(shapes),flush=True)
    records=[]
    for index,shape in enumerate(shapes,1):
        sid=f'EXTERIOR_SOURCE_SOLID_{index:04d}'
        record={'solid_id':sid,'geometry_source':'ORIGINAL_STEP_NOT_CATIA_REEXPORT',
                'source_body_index':None,'source_entity_id':None,
                'identity_method':'SOURCE_FILE_SHA256_AND_LOCAL_REGISTRATION',
                'source_sha256':source_digest,'status':'NOT_EVALUATED'}
        try:
            model=OCCTBRepModel(); solid=model.register_shape(sid,shape)
            ledger=model.solid_face_provenance(sid)
            faces=[model.describe(f) for f in ledger['face_ids']]
            candidate=exterior_candidate(solid,faces)
            try: seeds=tangent_route_seeds(faces)
            except (ValueError,KeyError,TypeError): seeds=[]
            detail={'solid':solid,'faces':faces,'face_provenance':ledger,'candidate':candidate,
                    'support_tangency_seeds':seeds,'geometry_source':record['geometry_source'],
                    'source_sha256':source_digest}
            detail_path=a.output/(sid+'.json')
            detail_path.write_text(json.dumps(detail,ensure_ascii=False,indent=2),encoding='utf-8')
            record.update({'candidate':candidate,'detail_file':detail_path.name,
                'surface_type_counts':dict(Counter((f.get('surface_features') or {}).get('surface_type','UNKNOWN') for f in faces)),
                'support_tangency_seed_count':len(seeds),'face_count':solid['face_count'],
                'valid':solid['valid'],'bounds_mm':solid['bounds_mm'],'centroid_mm':solid['centroid_mm']})
            if candidate['geometry_kind']!='UNDETERMINED' or seeds:
                model.write_brep(sid,a.output/(sid+'.brep'))
                record['brep_cache_file']=sid+'.brep'
        except Exception as error: record['error']=type(error).__name__+': '+str(error)
        records.append(record)
        if index%50==0:
            (a.output/'checkpoint.json').write_text(json.dumps(records,ensure_ascii=False),encoding='utf-8')
            print('Scanned',index,'of',len(shapes),flush=True)
    unchanged=(hashlib.sha256(formal.read_bytes()).hexdigest() if formal.exists() else None)==formal_digest
    source_unchanged=hashlib.sha256(a.source.read_bytes()).hexdigest()==source_digest
    if not unchanged or not source_unchanged: raise RuntimeError('Read-only hash audit failed')
    counts=dict(Counter(r.get('candidate',{}).get('geometry_kind','ERROR') for r in records))
    result={'scope':'ALL_OCCT_TRANSFERRED_ORIGINAL_STEP_SOLIDS_EXTERIOR_ONLY',
        'solid_count':len(shapes),'scanned_count':len(records),'geometry_counts':counts,
        'error_count':sum('error' in r for r in records),'source_sha256':source_digest,
        'source_file':str(a.source.resolve()),'source_unchanged':source_unchanged,
        'interference_result_unchanged':unchanged,'catia_body_mapping_verified':False,
        'design_cavity_confirmed':False,'engineering_pipe_confirmed':False,
        'support_tangency_seed_count':sum(r.get('support_tangency_seed_count',0) for r in records),
        'records':records}
    (a.output/'full_exterior_scan.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='records'},ensure_ascii=False),flush=True)
    candidates=[r for r in records if r.get('candidate',{}).get('geometry_kind','UNDETERMINED')!='UNDETERMINED']
    lines=['# 原始 STEP 全模型外形候选扫描','',
        f"读取并扫描 {len(shapes)} 个成功转入 OCCT 的 Solid，异常 {result['error_count']} 个。候选分类：{counts}。",'',
        '本扫描不依赖内孔或设计空腔。直线和弯曲外形候选仍可能是杆、销、套筒或其他机械零件，用途未确认。壁厚为空，流道、空腔及已确认端口不从外形推断。',
        '来源为原始 STEP，不能代替 CATIA 重导出 STP 的证据。未转入的实体、独立 Shell 或 Face 不在本实体扫描范围内。CATIA Body 对应关系仍未解析。','',
        '| 局部 Solid | 外形类别 | 外径 mm | 直段长度或弧长 mm | 中心线几何弯曲半径 mm |',
        '|---|---|---:|---:|---:|']
    for r in candidates:
        c=r['candidate']; length=c.get('length_mm',c.get('centerline_length_mm'))
        lines.append(f"| {r['solid_id']} | {c['geometry_kind']} | {c['outer_diameter_mm']:.6g} | {length:.6g} | {c.get('centerline_bend_radius_mm','')} |")
    lines+=['',f"另记录 {result['support_tangency_seed_count']} 条无限支撑几何相切线索，尚未逐项确认共享边界、有限覆盖或工程路线。",
        '全部实体保留 Face 详情 JSON；外形候选或相切线索另保留 BREP，后续复核可复用缓存。原始文件和正式干涉结果摘要核验一致，原 23 项仍待评估。']
    (a.output/'全模型外形扫描记录.md').write_text('\n'.join(lines),encoding='utf-8')


if __name__=='__main__': main()
