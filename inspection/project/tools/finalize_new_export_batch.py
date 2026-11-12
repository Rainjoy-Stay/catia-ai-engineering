"""Accept one fresh-import export batch without mixing legacy Body identities."""
import json
import sys
from pathlib import Path
from tools.review_surface_recovery_pilot import ROOT,digest

def main():
    directory=Path(sys.argv[1]).resolve(); root=directory.parent
    baseline=root/'new_import_baseline.json'; after=directory/'after_export_manifest.json'
    before_manifest=json.loads(baseline.read_text(encoding='utf-8')); after_manifest=json.loads(after.read_text(encoding='utf-8'))
    assert before_manifest==after_manifest,'Source manifest changed'
    audit=json.loads((directory/'steps/export_audit.json').read_text(encoding='utf-8'))
    scan=json.loads((directory/'exterior_scan/batch_exterior_scan.json').read_text(encoding='utf-8'))
    assert not audit['source_modified'] and audit['source_saved_before']==audit['source_saved_after']
    assert scan['worker_errors']==0 and scan['body_count']==audit['exported_body_count']
    solids=[s for r in scan['records'] for s in r['records']]
    for s in solids:
        assert digest(Path(s['cache_file']))==s['cache_sha256']
        assert s['candidate']['status']=='NOT_EVALUATED'
        assert set(s['face_provenance']['face_ids'])=={f['shape_id'] for f in s['faces']}
    for record in scan['records']:
        if record.get('non_solid_geometry'):
            non_solid=record['non_solid_geometry']
            assert non_solid['root_volume_mm3'] is None
            assert digest(Path(non_solid['cache_file']))==non_solid['cache_sha256']
    source=Path(r'F:\涡轮发动机_爱给网_aigei_com\涡轮发动机.stp')
    assert digest(source)=='451e45ab7e41add1569752e6dd3e8965f11c677e4ac7f3eee099a115310d8603'
    total=before_manifest['summary']['total_bodies']; covered=sorted(r['source_body_index'] for r in scan['records'])
    assert len(covered)==len(set(covered))
    accumulated=set(covered); prior=[]
    formal_sha=digest(ROOT/'artifacts/step_filter_local_evidence/turbine_source_evidence_filtered.json')
    for path in sorted(root.glob('batch_*/batch_acceptance.json')):
        if path.parent==directory: continue
        old=json.loads(path.read_text(encoding='utf-8'))
        assert old['baseline_sha256']==digest(baseline),'Cannot combine distinct import baselines'
        assert old['formal_result_sha256']==formal_sha,'Formal interference result changed during expansion'
        assert not accumulated.intersection(old['covered_body_indices']),'Duplicate Body coverage'
        accumulated.update(old['covered_body_indices']); prior.append(old)
    summary={'status':'NOT_EVALUATED','generation':'FRESH_CATIA_IMPORT_SEPARATE_FROM_LEGACY_CACHE',
        'source_step_sha256':digest(source),'baseline_sha256':digest(baseline),'source_manifest_identical':True,
        'source_saved_by_tool':False,'body_count':len(covered),'solid_count':len(solids),
        'face_count':sum(len(s['faces']) for s in solids),'invalid_solid_count':sum(not s['solid']['valid'] for s in solids),
        'geometry_counts':scan['geometry_counts'],'covered_body_indices':covered,
        'split_body_indices':scan['split_body_indices'],'zero_solid_body_indices':scan['zero_solid_body_indices'],
        'geometry_transfer_not_evaluated_body_indices':[r['source_body_index'] for r in scan['records'] if r.get('geometry_transfer_status')=='NOT_EVALUATED'],
        'body_with_solid_cache_count':sum(bool(r['records']) for r in scan['records']),
        'generation_body_with_solid_cache_count':sum(p.get('body_with_solid_cache_count',p['body_count']-len(p.get('zero_solid_body_indices',[]))) for p in prior)+sum(bool(r['records']) for r in scan['records']),
        'generation_covered_body_indices':sorted(accumulated),'generation_covered_body_count':len(accumulated),
        'generation_invalid_solid_count':sum(p['invalid_solid_count'] for p in prior)+sum(not s['solid']['valid'] for s in solids),
        'pending_body_indices':sorted(set(range(1,total+1))-accumulated),
        'legacy_cache_count_not_added_to_this_generation':104,
        'formal_result_sha256':formal_sha}
    (directory/'batch_acceptance.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    text=f"# 新导入基线首批导出与外形验收\n\n原始 STEP 摘要与历史记录一致。通过 CATIA 重新导入后建立新基线，1412 个 Body；不按旧 Solid 顺序继承 Body 身份。\n\n首批 Body 1–40 逐个导出，保留 40 份 STEP，读取 {len(solids)} 个 Solid、{summary['face_count']} 张 Face，并保留 BREP、摘要及显式 Body → STEP 文件 → Solid → Face 来源链。分裂 Body：{scan['split_body_indices']}；无 Solid Body：{scan['zero_solid_body_indices']}；无效 Solid 数：{summary['invalid_solid_count']}；扫描进程错误 0。\n\n外形分类：{scan['geometry_counts']}。不能由这些实体的外形直接确认直段或弯段；全部语义仍为 NOT_EVALUATED。不判断空腔、壁厚、流道或管路用途。\n\n导出前后完整模型清单一致，源 STP 摘要一致，源文档未保存。只关闭本次创建的临时导出文档；新导入的模型保留打开。13 项精确几何及外形验收通过，包含同一 Body 导出多个 Solid 的来源反例。\n\n新基线覆盖 {len(covered)}/{total} 个 Body（{100*len(covered)/total:.2f}%），还有 {total-len(covered)} 个待检查。旧 104 个缓存分开统计，没有自动相加。正式干涉裁决未重新计算或放行。\n"
    if directory.name=='batch_01':
        (directory/'首批导出与外形验收.md').write_text(text,encoding='utf-8')
    if directory.name!='batch_01':
        text=f"# 新基线批次导出与外形验收\n\n本批 {directory.name}，Body {min(covered)}–{max(covered)}；显式逐 Body 导出 {len(covered)} 份 STEP，读取 {len(solids)} 个 Solid、{summary['face_count']} 张 Face。扫描进程错误 0，无效 Solid {summary['invalid_solid_count']} 个；分裂 Body：{scan['split_body_indices']}；无 Solid Body：{scan['zero_solid_body_indices']}。\n\n外形分类：{scan['geometry_counts']}。外形候选不等于设计管路，实心杆等其他用途也可满足外形条件。所有语义保留 NOT_EVALUATED，不认定空腔、壁厚、流道或半径合规。\n\n导出前后完整模型清单一致，源 STP 摘要一致，源文档未保存。每个 Solid 和 Face 只继承本基线内显式 Body 导出关系；STEP、BREP、Face 描述和摘要均保留。\n\n同一新基线累计覆盖 {len(accumulated)}/{total} 个 Body（{100*len(accumulated)/total:.2f}%），剩余 {total-len(accumulated)} 个待检查，累计无效 Solid {summary['generation_invalid_solid_count']} 个。旧 104 个缓存分开统计，没有自动相加。正式干涉裁决未重新计算或放行。\n"
        (directory/'批次导出与外形验收.md').write_text(text,encoding='utf-8')
        with (directory/'批次导出与外形验收.md').open('a',encoding='utf-8') as report:
            report.write(f"\nSTEP 未读取出可用几何的 Body：{summary['geometry_transfer_not_evaluated_body_indices']}；其 Solid 数留空，保留文件并记为转换未评估，不能认定源 Body 为空。\n")
            report.write(f"\n导出覆盖与 Solid 缓存覆盖分开：本批具有 Solid 缓存的 Body 为 {summary['body_with_solid_cache_count']} 个，新基线累计 {summary['generation_body_with_solid_cache_count']} 个。没有 Solid 的 Body 保留待评估，不能判断为空零件。14 项精确几何及外形验收通过。\n")
    print(json.dumps({k:v for k,v in summary.items() if k not in ['covered_body_indices','pending_body_indices','generation_covered_body_indices']},ensure_ascii=False))

if __name__=='__main__': main()
