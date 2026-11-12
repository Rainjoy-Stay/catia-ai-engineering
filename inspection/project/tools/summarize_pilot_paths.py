"""Publish numerical comparison evidence, not engineering acceptance."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'project/output/path-comparison-20261001'
PILOT=ROOT/'project/output/bulk-copy-pilot/retry'

def run():
    single={r['source_body_index']:r for r in json.loads((OUT/'singleton-step.json').read_text(encoding='utf-8'))}
    bulk={r['source_body_index']:r for r in json.loads((OUT/'bulk-step.json').read_text(encoding='utf-8'))}
    original={r['source_body_index']:r for r in json.loads((OUT/'raw-original-step.json').read_text(encoding='utf-8'))['geometry']}
    source={r['source_body_index']:r for r in json.loads((PILOT/'benchmark.json').read_text(encoding='utf-8'))['source_records']}
    rows=[]
    for index,s in single.items():
        b=bulk[index];o=original[index];facts=source[index]
        delta={key:s['adaptive_1e8'][key]-b['adaptive_1e8'][key] for key in ('volume_mm3','surface_area_mm2')}
        delta['centroid_max_axis_mm']=max(abs(x-y) for x,y in zip(s['adaptive_1e8']['centroid_mm'],b['adaptive_1e8']['centroid_mm']))
        rows.append({'source_body_index':index,'source_name':facts['source_body_name'],
            'original_valid':o['valid_topology'],'singleton_valid':s['valid_topology'],'bulk_valid':b['valid_topology'],
            'singleton_bulk_deltas':delta,'original_default':o['default'],'catia_export_default':s['default'],
            'catia_spa':facts,'original_bounds':o['bounds_mm'],'export_bounds':s['bounds_mm'],
            'original_errors':o['local_status_errors'],'export_errors':s['local_status_errors'],
            'original_topology_counts':o['topology_counts'],'export_topology_counts':s['topology_counts'],
            'original_normal_import_status':'NOT_EVALUATED',
            'raw_translation_usable_as_reference':False,
            'engineering_status':'NOT_EVALUATED'})
    before=json.loads((OUT/'source-before.json').read_text(encoding='utf-8'))
    after=json.loads((OUT/'source-after.json').read_text(encoding='utf-8'))
    result={'objects':rows,'source_summary_unchanged':before['summary']==after['summary'],
        'source_state_unchanged':all(json.loads((OUT/('body-'+str(i))/'benchmark.json').read_text(encoding='utf-8'))['source_state_unchanged'] for i in single),
        'singleton_3_extra_bulk_trial':'ERROR_ZERO_NONEMPTY_BODY; singleton export complete',
        'original_adaptive_integration':'NOT_EXECUTED; compare default properties with default properties',
        'normal_original_reader_association':'UNRESOLVED; raw entity translator is supplemental only',
        'formal_check':False,'full_model_interference_check':False}
    (OUT/'comparison.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['# STEP / CATIA / OCCT 小样本路径对照（2026-10-01）','',
        '原始文件：F:/涡轮发动机_爱给网_aigei_com/涡轮发动机.stp。文件头记录 NX 11 / ST-DEVELOPER / 2019-01-26。CATIA 开发验证为 Release 32，非目标 Release 30。','',
        '原 STEP 正常整文件导入成功，但原实体与返回几何关联未解决，不能视为完成正常导入路径对照。补充测试采用精确 CATIA BREP 编号、原文件实体位置交叉验证，再经 StepToTopoDS_Builder 直接转换所选实体；长度毫米、角度度来自原文件单位。该底层路径未证明与正常 STEPControl_Reader 转换等价。没有用空间相近冒充身份关联。','',
        '底层转换的 7 个结果均拓扑无效，部分壳/面结构也与正常导出明显不一致。这批底层转换结果不可作为有效几何参照，不能据此断言原文件已损坏或 CATIA 修复了模型；其体积和重心不用于验收或归因。第三条正常原 STEP 路径仍为 NOT_EVALUATED。','',
        '| Body 索引 | CATIA 原名 | 原 STEP 正常路径 | 单对象导出有效 | 40 对象批量导出有效 |','|---|---|---|---|---|']
    for r in rows:
        lines.append('| '+str(r['source_body_index'])+' | '+r['source_name']+' | 未评价（身份关联未解决） | '+str(r['singleton_valid'])+' | '+str(r['bulk_valid'])+' |')
    lines+=['','## 当前可用结论','',
        '7 个样本单对象导出与批量导出的自适应 1e-8 体积、总面积及重心差为零（当前数值结果，不是拓扑完全等价证明）。三个 OCCT 错误在两种导出中一致，因此没有证据说明这三个错误是批量复制独有的问题。不能由此断言原始 STEP 与 CATIA 转换谁负责。',
        '', 'Body 3：face #1361，UnorientableShape；Body 9：face #17，BadOrientationOfSubshape；Body 31：face #64，UnorientableShape。这里的 face 编号为各导出文件的局部 OCCT 枚举编号，不是 CATIA 树名称或原 STEP 编号。',
        '', '下一步应补齐正常原 STEP 导入后的身份关联，或在独立临时导出副本上测试定向拓扑修复并验证几何变化。当前未执行修复，未自动启动全模型检查。',
        '', 'Body 3 的单独导出成功；额外的单 Body 批量复制测试得到零个非空 Body 并报错。原失败审计保留，不能把该项当作成功。',
        '', '源前后摘要相同：'+str(result['source_summary_unchanged'])+'；各临时导出试验源 Saved 状态/Body 数量/集合数量一致：'+str(result['source_state_unchanged'])+'。未保存、删除或修改原模型，临时文档仅关闭本试验创建的对象。',
        '', '本次不是工程验收，所有工程状态为 NOT_EVALUATED。OCCT 拓扑无效不等于 CATIA 内核也判无效。原始 STEP 未做自适应积分，跨原始/再导出只比较相同默认积分方法，不混用积分口径。']
    (OUT/'对照结论.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps({'rows':[{'index':r['source_body_index'],'original':r['original_valid'],'single':r['singleton_valid'],'bulk':r['bulk_valid']} for r in rows],
        'source_unchanged':result['source_state_unchanged']},ensure_ascii=False),flush=True)

if __name__=='__main__':run()
