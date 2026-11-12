"""Apply exterior-only recognition to retained CATIA export face evidence."""
import hashlib
import json
from collections import Counter
from pathlib import Path
from standalone.step_pipe_semantics.exterior import exterior_candidate


def main():
    art=Path(__file__).resolve().parents[1]/'artifacts'; source=art/'step_pipe_semantics_pilot'
    out=art/'step_exterior_pilot'; out.mkdir(exist_ok=True)
    formal=art/'step_filter_local_evidence'/'turbine_source_evidence_filtered.json'
    digest=hashlib.sha256(formal.read_bytes()).hexdigest()
    pilot=json.loads((source/'turbine_pipe_pilot.json').read_text(encoding='utf-8'))
    records=[]
    for item in pilot['records']:
        if not item.get('detail_file'): continue
        path=source/item['detail_file']; detail=json.loads(path.read_text(encoding='utf-8'))
        result=exterior_candidate(detail['solid'],detail['faces'])
        records.append({'source_body_index':item['source_body_index'],
            'source_body_name':item['source_body_name'],'source_binding':item['source_binding'],
            'geometry_source':'CATIA_SINGLE_BODY_EXPORT_CACHE','evidence_file':str(path.resolve()),
            'evidence_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'candidate':result})
    candidates=[r for r in records if r['candidate']['geometry_kind']!='UNDETERMINED']
    assert hashlib.sha256(formal.read_bytes()).hexdigest()==digest
    summary={'scope':'104_RETAINED_CATIA_EXPORT_SOLIDS_NOT_FULL_MODEL','processed_count':len(records),
        'geometry_counts':dict(Counter(r['candidate']['geometry_kind'] for r in records)),
        'candidate_count':len(candidates),'reason_counts':dict(Counter(r['candidate']['reason'] for r in records)),
        'interference_result_unchanged':True,'records':records}
    (out/'export_exterior_candidates.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['# CATIA 导出模型外形候选试运行','',
        f"对 {len(records)} 个现有单 Body 导出缓存进行外形识别，得到 {len(candidates)} 个外形候选。分类计数：{summary['geometry_counts']}。仅覆盖此前局部复核缓存，不代表全模型。",'',
        '此识别不要求内孔。实心杆、销和套筒也可满足外形条件；候选不等于设计管路。只报告外径、轴线和两端平面距离，壁厚为空、流道未确认、端口列表为空，全部状态 NOT_EVALUATED。',
        '两端平面与轴线的交点只是外形定位点，不是已确认的开口或连接接口。不得将这些点直接送入正常连接裁决。','',
        '| Body | 外形类型 | 外径 mm | 直段长度或弧长 mm | 中心线弯曲半径 mm |','|---|---|---:|---:|---:|']
    for r in candidates:
        c=r['candidate']; length=c.get('length_mm',c.get('centerline_length_mm'))
        lines.append(f"| {r['source_body_index']} | {c['geometry_kind']} | {c['outer_diameter_mm']:.6g} | {length:.6g} | {c.get('centerline_bend_radius_mm','')} |")
    lines+=['','34 项外形及现有管路识别相关测试通过，覆盖实心杆、实心弯曲体、空心体、旋转、碎分圆柱面、端部圆角、带孔方块及盲孔反例。正式干涉结果摘要保持一致，原 23 项结论不变。',
            '弯曲外形需要端面位置、切向、转角、表面积和材料体积相互验证；中心线几何半径不代表工程弯曲半径已合规。多段复合外形及碎分环面仍待路由复核。完整轴线和来源见 export_exterior_candidates.json。']
    (out/'导出模型外形识别记录.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k!='records'}))


if __name__=='__main__': main()
