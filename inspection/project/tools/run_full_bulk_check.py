"""Full CATIA bulk export followed by global OCCT candidate checking, with durable receipts."""
import argparse
import asyncio
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime,timedelta,timezone
from pathlib import Path
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'project'))
from catia_checker.large_single_part import inspect_large_single_part_batches_isolated,build_large_single_part_result
from catia_checker.routing_rules import validate_rules

def emit(event):print(json.dumps(event,ensure_ascii=False),flush=True)
def save(path,data):
    temporary=path.with_suffix(path.suffix+'.pending')
    temporary.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');temporary.replace(path)

async def export(args):
    directory=args.directory.resolve();directory.mkdir(parents=True,exist_ok=True)
    env=dict(os.environ,PYTHONPATH=os.pathsep.join(str(ROOT/p) for p in ('scripts','vendor/catia-v5-mcp-server','project')),
        PYTHONIOENCODING='utf-8',CATIA_AGENT_MODE='full')
    params=StdioServerParameters(command=sys.executable,args=[str(ROOT/'scripts/start_mcp.py')],env=env,cwd=str(ROOT))
    paths=[];mapping=[];errors=[]
    async with stdio_client(params) as (reader,writer):
        async with ClientSession(reader,writer,read_timeout_seconds=timedelta(hours=4)) as session:
            await session.initialize()
            definitions=await session.list_tools()
            save(directory/'tool-definitions.json',[t.model_dump() for t in definitions.tools])
            async def call(name,values):
                result=await session.call_tool(name,values)
                if result.isError:raise RuntimeError(str(result.content))
                return result
            connected=await call('catia_connect',{})
            save(directory/'connection.json',connected.model_dump())
            await call('catia_activate_document',{'name':args.source})
            info=await call('catia_get_active_document_info',{})
            facts=json.loads(next(x.text for x in info.content if getattr(x,'text',None)))
            if facts['name']!=args.source or facts['type']!='CATPart':raise RuntimeError('Wrong active document')
            previous_facts=json.loads((directory/'document-info.json').read_text(encoding='utf-8')) if args.resume_export else None
            if previous_facts and any(previous_facts.get(k)!=facts.get(k) for k in ('name','type','full_name','bodies')):
                raise RuntimeError('Source document identity/tree changed')
            save(directory/('document-info-recovery.json' if args.resume_export else 'document-info.json'),facts)
            # Fresh run only; never reuse exports merely because their names/counts match.
            if (directory/'export-audit.json').exists() and not args.resume_export:raise RuntimeError('Existing full export; explicit verified recovery required')
            await call('catia_get_model_manifest',{'include_parameters':False,'output_path':str(directory/('manifest-recovery.json' if args.resume_export else 'manifest-before.json'))})
            count=len(facts['bodies']);total=(count+39)//40
            if args.resume_export:
                cached=json.loads((directory/'export-audit.json').read_text(encoding='utf-8'))
                if cached['status']!='EXPORTING' or cached['exported_body_count']!=count or cached['expected_body_count']!=count:
                    raise RuntimeError('Recovery requires complete Body-only export')
                paths=cached['batch_files'];mapping=cached['body_mapping'];errors=cached['errors']
                receipts=[]
                for filename in paths:
                    step=Path(filename)
                    if not step.resolve().is_relative_to(directory):raise RuntimeError('Export outside run directory')
                    audit=json.loads((step.parent/'benchmark.json').read_text(encoding='utf-8'))
                    case=next(c for c in audit['cases'] if c.get('step_path')==filename)
                    if audit['status']!='COMPLETE' or not audit['source_state_unchanged'] or not case['mapping_verified'] or step.stat().st_size!=case['step_bytes']:
                        raise RuntimeError('Export receipt invalid: '+filename)
                    with step.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
                    receipts.append({'file':filename,'sha256_at_recovery':digest,'size':step.stat().st_size})
                save(directory/'recovery-file-verification.json',receipts)
                emit({'stage':'CATIA_EXPORT_RECOVERY','body_total':count,'batch_count':len(paths),'operation':'35批导出凭据已核验；复测源实体后续导面和壳'})
            emit({'stage':'CATIA_EXPORT_START','body_total':count,'batch_count':total,'operation':'全模型批量复制和 STEP 导出'})
            for batch,start in enumerate([] if args.resume_export else range(1,count+1,40),1):
                indices=list(range(start,min(start+40,count+1)));trial=directory/'export'/('batch-'+str(batch))
                emit({'stage':'CATIA_BATCH_EXPORT_START','batch_id':f'BATCH_{batch:04d}','batch_number':batch,'batch_count':total,'body_count':len(indices)})
                await call('catia_benchmark_batch_copy',{'source_name':args.source,'body_indices':indices,
                    'output_directory':str(trial),'copy_modes':['bulk']})
                audit=json.loads((trial/'benchmark.json').read_text(encoding='utf-8'))
                if audit['status']!='COMPLETE':
                    errors.append({'batch':batch,'indices':indices,'error':audit.get('error')})
                    # Retain the failed bulk receipt. Existing individual workflow is an audited fallback.
                    emit({'stage':'CATIA_BATCH_FALLBACK','batch_number':batch,'operation':'批量复制未完整；本批改用逐对象复制，不改源模型'})
                    trial=directory/'export'/('fallback-'+str(batch))
                    await call('catia_benchmark_batch_copy',{'source_name':args.source,'body_indices':indices,
                        'output_directory':str(trial),'copy_modes':['individual']})
                    audit=json.loads((trial/'benchmark.json').read_text(encoding='utf-8'))
                    if audit['status']!='COMPLETE':raise RuntimeError('Both export paths failed for batch '+str(batch))
                case=audit['cases'][0]
                paths.append(case['step_path'])
                mapping.extend({**r,'batch_id':f'BATCH_{batch:04d}','source_kind':'BODY'} for r in case['mapping'])
                save(directory/'export-audit.json',{'source':args.source,'expected_body_count':count,
                    'exported_body_count':len(mapping),'batch_files':paths,'body_mapping':mapping,'errors':errors,'status':'EXPORTING'})
                emit({'stage':'CATIA_BATCH_EXPORT_COMPLETE','batch_id':f'BATCH_{batch:04d}','batch_number':batch,'batch_count':total,
                    'body_count':len(indices),'exported_body_count':len(mapping),'body_total':count})
            emit({'stage':'CATIA_SURFACE_EXPORT_START','operation':'纳入全部几何图形集元素；导出失败单独登记，隐藏不等于删除'})
            surfaces=directory/'surfaces'
            surface_args={'source_name':args.source,'output_directory':str(surfaces),'start_batch':total}
            if args.resume_export:surface_args['verify_body_audit']=str(directory/'export-audit.json')
            await call('catia_export_surface_batches',surface_args)
            surface=json.loads((surfaces/'surface-audit.json').read_text(encoding='utf-8'))
            # Failed chunks can leave numbering gaps; engine batch IDs are input-order IDs.
            for filename in surface['batch_files']:
                old=Path(filename).stem;new=f'BATCH_{len(paths)+1:04d}';paths.append(filename)
                mapping.extend({**r,'export_batch_id':old,'batch_id':new} for r in surface['mapping'] if r['batch_id']==old)
            errors.extend(surface['errors'])
            await call('catia_get_model_manifest',{'include_parameters':False,'output_path':str(directory/'manifest-after-export.json')})
            save(directory/'export-audit.json',{'source':args.source,'expected_body_count':count,'exported_body_count':count,
                'batch_files':paths,'body_mapping':mapping,'errors':errors,'surface_element_count':surface['element_count'],
                'surface_exported_count':len(surface['mapping']),'status':'EXPORTED'})
    return paths,mapping,errors

def load_completed_export(directory, source):
    """Resume this immutable exported snapshot, not a newly edited CATIA document."""
    cached=json.loads((directory/'export-audit.json').read_text(encoding='utf-8'))
    if cached.get('status')!='EXPORTED' or cached.get('source')!=source:
        raise RuntimeError('Complete matching export required for check resume')
    verified={str(Path(r['file']).resolve()):r['sha256_at_recovery'] for r in
              json.loads((directory/'recovery-file-verification.json').read_text(encoding='utf-8'))}
    paths=cached['batch_files']
    if not paths or len(set(paths))!=len(paths):raise RuntimeError('Invalid exported batch list')
    for filename in paths:
        path=Path(filename).resolve()
        if not path.is_relative_to(directory.resolve()):raise RuntimeError('Export outside run directory')
        expected=verified.get(str(path))
        if expected is None:
            receipt=json.loads(path.with_suffix('.mapping.json').read_text(encoding='utf-8'))
            if receipt['file']!=path.name or receipt['size_bytes']!=path.stat().st_size:
                raise RuntimeError('Surface receipt identity mismatch')
            expected=receipt['sha256']
        with path.open('rb') as stream:actual=hashlib.file_digest(stream,'sha256').hexdigest()
        if actual!=expected:raise RuntimeError('Export changed since receipt: '+str(path))
    return paths,cached['body_mapping'],cached['errors']

def main():
    p=argparse.ArgumentParser();p.add_argument('--directory',type=Path,required=True)
    p.add_argument('--source',default='full_all_features.CATPart');p.add_argument('--workers',type=int,default=8)
    p.add_argument('--resume-export',action='store_true',help='Verify and reuse complete Body exports, then retry surface export')
    p.add_argument('--resume-check',action='store_true',help='Resume exact checks against verified exported snapshot without CATIA export')
    p.add_argument('--budget-minutes',type=int)
    a=p.parse_args();a.directory=a.directory.resolve();a.directory.mkdir(parents=True,exist_ok=True)
    if not 1<=a.workers<=min(32,os.cpu_count() or 1):raise ValueError('Invalid workers')
    os.environ['CATIA_MONITOR_DIRECTORY']=str(a.directory)
    if a.resume_check:
        rules=json.loads((a.directory/'rules-snapshot.json').read_text(encoding='utf-8'))
    else:
        rules=json.loads((ROOT/'project/config/rules-active.json').read_text(encoding='utf-8'))
        rules['ruleset_id']=rules['ruleset_id']+'-full-bulk-20261001'
        rules['large_single_part']['max_exact_pairs']=100000000 # no candidate truncation for this full run
    if a.budget_minutes is not None and not 1<=a.budget_minutes<=240:raise ValueError('Invalid budget')
    validate_rules(rules);save(a.directory/'rules-snapshot.json',rules)
    save(a.directory/'run-ledger.json',{'scope':'ALL_BODIES_AND_GEOMETRICAL_SET_ELEMENTS','stage':'EXPORTING',
        'formal_engineering_acceptance':False,'remaining':['OCCT import','global candidate checking','exception review'],
        'previous_check_progress_reused':a.resume_check,'workers':a.workers})
    emit({'stage':'RUN_START','operation':'核验本轮导出快照并续跑检查点' if a.resume_check else '全模型批量导出＋全局精确候选检查；不复用旧检查进度','max_workers':a.workers})
    try:
        paths,mapping,errors=load_completed_export(a.directory,a.source) if a.resume_check else asyncio.run(export(a))
        save(a.directory/'body-mapping.json',mapping)
        emit({'stage':'FULL_EXPORT_COMPLETE','batch_count':len(paths),'mapping_count':len(mapping),'export_error_count':len(errors)})
        runtime_options={}
        runtime_file=a.directory/'resume-runtime.json'
        if a.resume_check and runtime_file.exists():
            options=json.loads(runtime_file.read_text(encoding='utf-8'))
            for name in ('pair_timeout_seconds','pair_retry_timeout_seconds'):
                if name in options:
                    value=float(options[name])
                    if not 1<=value<=600:raise ValueError('Invalid resume timeout')
                    runtime_options[name]=value
            emit({'stage':'RESUME_RUNTIME','operation':'本轮提高计算时限；不改变几何判定标准',**runtime_options})
        bundle=inspect_large_single_part_batches_isolated(paths,rules=rules,progress=emit,**runtime_options,
            checkpoint_path=a.directory/'checkpoint.json',max_pair_workers=a.workers,body_mapping=mapping,
            run_budget_seconds=a.budget_minutes*60 if a.budget_minutes else None)
        result=build_large_single_part_result(bundle,document=a.source,rules=rules,
            run_id='FULL-BULK-'+datetime.now().strftime('%Y%m%d-%H%M%S'),generated_at=datetime.now(timezone.utc).isoformat())
        result['confidence_budget']['is_complete']=False
        result['confidence_budget']['not_checked'].extend(['开发试跑不是全部工程专项验收；未执行逐对象双视角 CATIA 证据',
            '全部对象拓扑有效性、转换测量口径及工程连接语义尚未完成复核'])
        result['audit']['full_bulk_export_errors']=errors
        result['audit']['formal_engineering_acceptance']=False
        save(a.directory/'check-raw.json',result)
        # Preserve raw geometry predictions, but no unreviewed engineering PASS/FAIL publication.
        for finding in result['findings']:
            if finding['status'] in ('PASS','FAIL'):
                finding.setdefault('metadata',{})['raw_geometry_status']=finding['status']
                finding['status']='NOT_EVALUATED'
        for status in ('PASS','FAIL','WARN','NOT_EVALUATED','EXEMPTED'):
            result['counts'][status]=sum(f['status']==status for f in result['findings'])
        save(a.directory/'check.json',result)
        paused=(a.directory/'pause-request.json').exists() or bool(bundle.get('budget_deferred_count'))
        save(a.directory/'run-ledger.json',{'stage':'PAUSED' if paused else 'GEOMETRY_TRIAL_COMPLETE','formal_engineering_acceptance':False,
            'candidate_coverage':result.get('resume_status'),'export_errors':errors,
            'remaining':['拓扑和转换差异复核','工程语义与规则复核','正式截图报告未请求/未执行']})
        emit({'stage':'RUN_END','exit_code':2 if paused else 0,'operation':'已暂停；检查点已保存，可调整并发后续跑' if paused else '全范围几何试跑结束；请核对超时和未评价范围'})
        return 2 if paused else 0
    except Exception as exc:
        save(a.directory/'run-error.json',{'error':str(exc),'source_saved_by_tool':False})
        emit({'stage':'RUN_ERROR','error':str(exc)});raise

if __name__=='__main__':raise SystemExit(main())
