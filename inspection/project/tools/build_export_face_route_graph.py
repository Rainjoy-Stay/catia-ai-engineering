import hashlib
import json
from pathlib import Path
from standalone.step_pipe_semantics.route_graph import build_face_route_graph


def main():
    art=Path(__file__).resolve().parents[1]/'artifacts'; directory=art/'step_exterior_pilot'
    formal=art/'step_filter_local_evidence'/'turbine_source_evidence_filtered.json'
    digest=hashlib.sha256(formal.read_bytes()).hexdigest()
    source=json.loads((directory/'export_route_seeds.json').read_text(encoding='utf-8'))
    graph=build_face_route_graph(source['records'])
    graph['interference_result_unchanged']=hashlib.sha256(formal.read_bytes()).hexdigest()==digest
    assert graph['interference_result_unchanged']
    (directory/'export_face_route_graph.json').write_text(json.dumps(graph,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['# 导出模型局部曲面连接图','',
        '只使用已确认共享 Edge 的圆柱 Face 与环面 Face 建图。不同 Face 即便位于同一个支撑圆柱上也保留独立节点，避免把不相邻碎片拼成路线。',
        '图中的链、分支和环都是局部曲面拓扑类别，不是工程管路。平面及其他曲面尚未纳入，不能据此确认流道、内外壁或完整中心线。','',
        '| Body | Face 节点 | 共享边连接 | 连通分量 |','|---|---:|---:|---:|']
    for b in graph['bodies']: lines.append(f"| {b['source_body_index']} | {len(b['nodes'])} | {len(b['edges'])} | {len(b['components'])} |")
    lines+=['','支撑相切线索的截面半径仅 0.0125–0.05 mm，也可能来自局部圆角或细小结构。图已确认相邻，但用途仍需整段外形证据；不将这些参数签发为工程管路弯曲半径。',
        '新增 5 项图验收覆盖无共享边界、同轴但断开的碎片、重复线索、分支和环。原 23 项干涉裁决保持待评估。下一步应验证有限曲面范围及整段截面一致性，再提出中心线候选。']
    (directory/'局部曲面连接图记录.md').write_text('\n'.join(lines),encoding='utf-8')
    print([(b['source_body_index'],len(b['nodes']),len(b['edges']),len(b['components'])) for b in graph['bodies']])


if __name__=='__main__': main()
