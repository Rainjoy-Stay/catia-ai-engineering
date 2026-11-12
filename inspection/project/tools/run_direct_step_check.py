"""Isolated direct-STEP trial with durable monitor events and a fresh checkpoint."""
import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
PROJECT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PROJECT))
from catia_checker.large_single_part import inspect_large_single_part_batches_isolated,build_large_single_part_result
from catia_checker.routing_rules import validate_rules

def main():
    p=argparse.ArgumentParser()
    p.add_argument('source',type=Path)
    p.add_argument('--directory',type=Path,required=True)
    p.add_argument('--resume',action='store_true')
    p.add_argument('--workers',type=int,default=8)
    p.add_argument('--budget-minutes',type=int,default=60)
    a=p.parse_args()
    directory=a.directory.resolve();directory.mkdir(parents=True,exist_ok=True)
    checkpoint=directory/'checkpoint.json';report=directory/'check.json'
    if not a.resume and (checkpoint.exists() or report.exists()):raise RuntimeError('Fresh trial directory required')
    if not 1<=a.workers<=min(32,os.cpu_count() or 1):raise ValueError('Invalid worker count')
    os.environ['CATIA_MONITOR_DIRECTORY']=str(directory)
    def emit(value):
        event={**value,'time':datetime.now().isoformat(timespec='seconds')}
        if not os.environ.get('CATIA_MONITOR_MANAGED'):
            with (directory/'events.jsonl').open('a',encoding='utf-8') as stream:
                stream.write(json.dumps(event,ensure_ascii=False)+'\n')
        print(json.dumps(event,ensure_ascii=False),flush=True)
    rules=json.loads((PROJECT/'config/rules-active.json').read_text(encoding='utf-8'))
    validate_rules(rules)
    (directory/'rules-snapshot.json').write_text(json.dumps(rules,ensure_ascii=False,indent=2),encoding='utf-8')
    emit({'stage':'RUN_START','operation':f'整模型 STEP；本轮检查点续跑；{a.workers} 并发' if a.resume else f'整模型 STEP 新检查；{a.workers} 并发','max_workers':a.workers,'budget_minutes':a.budget_minutes})
    try:
        with a.source.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
        bundle=inspect_large_single_part_batches_isolated([a.source.resolve()],rules=rules,
            progress=emit,checkpoint_path=checkpoint,run_budget_seconds=a.budget_minutes*60,max_pair_workers=a.workers)
        result=build_large_single_part_result(bundle,document='full_all_features.CATPart',
            rules=rules,run_id='DIRECT-STEP-'+datetime.now().strftime('%Y%m%d-%H%M%S'),
            generated_at=datetime.now(timezone.utc).isoformat())
        result['confidence_budget']['is_complete']=False
        result['confidence_budget']['not_checked'].extend([
            '整模型 STEP 到 CATIA Body／几何图形集的来源映射尚未核验',
            '整模型独立面壳覆盖与导入修复警告的影响尚未核验'])
        result['audit']['direct_step_trial']={'source_step':str(a.source.resolve()),
            'sha256':digest,'previous_facts_reused':bool(bundle.get('resumed_pair_count')),'name_mapping_verified':False}
        report.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        paused=(directory/'pause-request.json').exists()
        emit({'stage':'RUN_END','exit_code':2 if paused else 0,'operation':'已暂停，检查点已保存' if paused else '本轮结束；覆盖／映射尚待核验'})
        return 2 if paused else 0
    except Exception as exc:
        emit({'stage':'RUN_ERROR','error':str(exc)})
        emit({'stage':'RUN_END','exit_code':1})
        raise
if __name__=='__main__':raise SystemExit(main())
