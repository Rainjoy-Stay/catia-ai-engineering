"""Coverage audit never equates original STEP traversal with CATIA Body indices."""
import json
from pathlib import Path
from tools.review_surface_recovery_pilot import ROOT,digest

def main():
    art=ROOT/'artifacts'; out=art/'step_export_coverage_audit'; out.mkdir(exist_ok=True)
    formal=art/'step_filter_local_evidence/turbine_source_evidence_filtered.json'; before=digest(formal)
    payload=json.loads(formal.read_text(encoding='utf-8')); total=payload['source']['source_body_count_before']
    pilot=json.loads((art/'step_pipe_semantics_pilot/turbine_pipe_pilot.json').read_text(encoding='utf-8'))
    audit=json.loads((art/'step_filter_body_recheck/export_audit.json').read_text(encoding='utf-8'))
    assert total==audit['source_body_count_before']==audit['source_body_count_after']
    verified=[]; rejected=[]
    for r in pilot['records']:
        cache=Path(r['cache_file']); detail=art/'step_pipe_semantics_pilot'/r['detail_file']
        ok=cache.is_file() and digest(cache)==r['cache_sha256'] and detail.is_file()
        record={'body_index':r['source_body_index'],'solid_id':r['solid_id'],'cache_file':str(cache),
            'cache_sha256':r['cache_sha256'],'cache_integrity_verified':ok,'source_binding':r['source_binding']}
        (verified if ok else rejected).append(record)
    covered={r['body_index'] for r in verified}; assert len(covered)==len(verified)
    exported={int(r['source_body_index']) for r in audit['body_mapping']}
    missing=sorted(set(range(1,total+1))-covered); unexported=sorted(set(range(1,total+1))-exported)
    no_solid=sorted(exported-covered)
    pending=[{'body_index':i,'status':'NOT_EVALUATED',
              'reason':'EXPORTED_WITHOUT_RETAINED_SOLID_CACHE' if i in no_solid else 'NO_RETAINED_AUDITED_EXPORT_CACHE'} for i in missing]
    batches=[unexported[i:i+40] for i in range(0,len(unexported),40)]
    assert len(covered)+len(missing)==total and digest(formal)==before
    result={'document':payload['document'],'status':'NOT_EVALUATED','source_body_count':total,
        'coverage_basis':'HISTORICAL_EXPLICIT_SINGLE_BODY_EXPORT_AUDIT_AND_CACHE_SHA256',
        'coverage_is_current_live_document_verification':False,'retained_body_cache_count':len(verified),
        'missing_body_count':len(missing),'unexported_body_count':len(unexported),
        'exported_without_solid_cache':no_solid,'rejected_caches':rejected,'historical_full_batch_exports_retained':False,
        'original_step_faces_do_not_fill_export_coverage':True,'formal_result_unchanged':True,
        'verified_cache_records':verified,'pending_bodies':pending,
        'next_export_plan':{'executed':False,'batch_size':40,'batches':batches,
            'prerequisites':['READ_ONLY_VERIFY_ACTIVE_CATPART_IDENTITY_AND_BODY_COUNT',
                'RECORD_SOURCE_STATE_BEFORE_AND_AFTER','DO_NOT_SAVE_SOURCE_DOCUMENT',
                'RETAIN_STEP_BREP_SHA256_AND_EXPLICIT_BODY_EXPORT_BINDINGS',
                'VERIFY_SOLID_FACE_OWNERSHIP_NOT_ORDINAL_SOURCE_MAPPING']}}
    (out/'export_semantic_coverage.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    text=f"# 导出模型语义检查覆盖验收\n\n历史源文档：{payload['document']}，1412 个 Body。已核对显式单 Body 导出记录及缓存摘要；这是历史缓存覆盖核对，尚未复核当前 CATIA 活动文档。\n\n保留且完整的 BREP 缓存覆盖 {len(verified)}/{total} 个 Body（{100*len(verified)/total:.2f}%），缺失 {len(missing)} 个。尚未导出 {len(unexported)} 个；已导出但没有保留 Solid 缓存的 Body 为 {no_solid}。原全模型 36 批临时导出已清理，其 1410 个 Solid 统计不能作为当前外形检查缓存。\n\n缺失项目逐项记为 NOT_EVALUATED；原始 STEP 的 1413 个 Solid 不能按序填补 CATIA 导出覆盖，也不能代表导出模型空腔。\n\n已生成 {len(batches)} 批、每批最多 40 个 Body 的补充导出计划，尚未执行。执行前须确认活动文档和 Body 数，记录源状态，保留 STEP、BREP、摘要和显式导出来源，禁止保存源文档。Body {no_solid} 单独复核，不能直接当作正常空实体。\n\n104 个缓存外形识别得到的 20 个直段外形候选仍仅是局部外形，不能确认设计管路。全部缺失与不确定语义保留待评估。正式干涉结果摘要保持不变。\n"
    (out/'导出模型覆盖与补充计划.md').write_text(text,encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ['verified_cache_records','pending_bodies','next_export_plan']},ensure_ascii=False))

if __name__=='__main__': main()
