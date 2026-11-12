"""Human review summary; unsupported geometry remains undetermined."""
import json
from collections import Counter
from pathlib import Path


def main():
    directory=Path(__file__).resolve().parents[1]/'artifacts'/'step_pipe_full_discovery'
    p=json.loads((directory/'full_step_pipe_discovery.json').read_text(encoding='utf-8'))
    counts=p['geometry_counts']; records=p['records']
    straight=Counter(r.get('recognition_reasons',{}).get('straight','ERROR') for r in records)
    bend=Counter(r.get('recognition_reasons',{}).get('bend','ERROR') for r in records)
    candidates=[r for r in records if r.get('candidate',{}).get('geometry_kind','UNDETERMINED')!='UNDETERMINED']
    lines=['# 原始 STEP 全实体管路候选发现','',
        f"读取 {p['solid_count']} 个 Solid，扫描 {p['scanned_count']} 个，异常 {p['error_count']} 个。范围仅覆盖 OCCT 成功转入的 Solid，不声明覆盖未转入实体或独立 Shell、Face。",
        f"直管候选 {counts.get('STRAIGHT_HOLLOW_CANDIDATE',0)}；弯管候选 {counts.get('CIRCULAR_HOLLOW_BEND_CANDIDATE',0)}；未确定 {counts.get('UNDETERMINED',0)}；端口连接候选 {p['connection_candidate_count']}。",'',
        '原始 STEP 转入 1413 个 Solid，历史 CATIA 批次为 1410 个；两套表示不能按序对齐。当前标识仅代表原始文件摘要和本次局部 OCCT 注册，不声明 CATIA Body 或 STEP 实体编号对应。',
        '几何候选的工程用途、连接许可及弯曲半径合规性均待评估。未识别不等于不是管路；多段组合管体、碎分端面、碎分环面、法兰及 BSpline 尚需扩展。',
        f"原始 STEP 与正式干涉结果前后 SHA256 核验：{p['source_unchanged']} / {p['interference_result_unchanged']}。原 23 项待评估状态保持不变。",'',
        '| Solid | 候选类型 | 外径 mm | 内径 mm | 壁厚 mm | 中心线弯曲半径 mm |',
        '|---|---|---:|---:|---:|---:|']
    for r in candidates:
        c=r['candidate']
        lines.append(f"| {r['solid_id']} | {c['geometry_kind']} | {2*c['outer_radius_mm']:.6g} | {2*c['inner_radius_mm']:.6g} | {c['wall_thickness_mm']:.6g} | {c.get('centerline_bend_radius_mm','')} |")
    lines+=['','直管诊断分布：']+[f'- {k}：{v}' for k,v in straight.most_common()]
    lines+=['','弯管诊断分布：']+[f'- {k}：{v}' for k,v in bend.most_common()]
    lines+=['','完整 Face 来源、尺寸与端口见 full_step_pipe_discovery.json；候选另保留对应 BREP 和 Face 详情 JSON。']
    (directory/'全模型管路候选发现记录.md').write_text('\n'.join(lines),encoding='utf-8')
    print('Summary written; candidates',len(candidates))


if __name__=='__main__': main()
