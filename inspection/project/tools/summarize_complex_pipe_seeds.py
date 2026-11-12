"""Review queue from openings; never interpret holes alone as pipe semantics."""
import json
from pathlib import Path


def main():
    artifacts=Path(__file__).resolve().parents[1]/'artifacts'
    directory=artifacts/'step_pipe_complex_discovery'
    result=json.loads((directory/'full_step_pipe_discovery.json').read_text(encoding='utf-8'))
    seeds=sorted((r for r in result['records'] if r.get('complex_review_seed')),
                 key=lambda r:(r['face_count'],r['solid_id']))
    queue=[]
    for r in seeds:
        radii=sorted(s['radius_mm'] for s in r['opening_seeds'])
        queue.append({'solid_id':r['solid_id'],'face_count':r['face_count'],
            'opening_count':len(radii),'inner_boundary_radii_mm':radii,
            'surface_type_counts':r['surface_type_counts'],'centroid_mm':r['centroid_mm'],
            'status':'NOT_EVALUATED','engineering_pipe_confirmed':False,
            'reason':'OPENING_AND_CYLINDER_REVIEW_SEED_ONLY',
            'detail_file':r['solid_id']+'.json'})
    mapping=json.loads((artifacts/'step_pipe_full_discovery'/'short_candidate_spatial_mapping.json').read_text(encoding='utf-8'))
    output={'source_sha256':result['source_sha256'],'scanned_count':result['scanned_count'],
        'seed_count':len(queue),'ordering':'FEWER_FACES_FIRST_FOR_BOUNDED_TOPOLOGY_REVIEW',
        'limits':'Seeds can include drilled blocks and fittings; bore continuity and wall topology unconfirmed',
        'short_candidate_mapping':mapping,'queue':queue}
    (directory/'complex_pipe_review_queue.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['# 复杂管状几何复核线索','',
        f"原始 STEP 的 {result['scanned_count']} 个 Solid 已完成只读筛选，读取异常 {result['error_count']} 个。发现 {len(queue)} 个复杂复核线索；这些不是已确认的管路，也不是正常连接。",'',
        '筛选要求有效实体、至少两个闭合同圆内边界及至少两个圆柱 Face。带孔方块、法兰和壳体也可能满足条件，因此仍需空腔贯通、内外壁对应和局部壁厚证据。按面数从少到多安排复核，仅为控制下一轮验证规模。',
        '此前两个短空心候选与 1410 个 CATIA 批次 Solid 的严格多特征空间匹配均未解析。未放宽容差，未使用遍历序号或旧标签单独确定 Body。',
        '最接近的批次项分别为 BATCH_0015::STEP_SOLID_0032 和 SOLID_0033。体积、面积和重心通过当前阈值，但包围盒边界差约 0.002034 mm、尺寸差约 0.004067 mm，超过 0.0001 mm 阈值；这些仅是诊断线索，尚未确认来源。',
        f"源文件及干涉结果前后摘要核验通过：{result['source_unchanged']} / {result['interference_result_unchanged']}。原 23 项待评估不变。",'',
        '| Solid | Face 数 | 圆形内边界数 | 内边界半径 mm | 表面类型 |','|---|---:|---:|---|---|']
    for q in queue:
        lines.append(f"| {q['solid_id']} | {q['face_count']} | {q['opening_count']} | {', '.join(format(r,'.6g') for r in q['inner_boundary_radii_mm'])} | {q['surface_type_counts']} |")
    lines+=['','全部线索的精确 Face 和 BREP 已缓存，不需再次读取或导出 CATIA 模型。结构化复核队列见 complex_pipe_review_queue.json。']
    (directory/'复杂管体复核记录.md').write_text('\n'.join(lines),encoding='utf-8')
    print('Complex review seeds:',len(queue))


if __name__=='__main__': main()
