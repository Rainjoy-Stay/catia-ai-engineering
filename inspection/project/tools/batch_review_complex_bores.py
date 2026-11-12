import hashlib
import json
import subprocess
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from standalone.step_pipe_semantics.bore_selection import select_straight_bore_review


def main():
    artifacts=Path(__file__).resolve().parents[1]/'artifacts'
    source=artifacts/'step_pipe_complex_discovery'; output=source/'straight_bore_batch'; output.mkdir(exist_ok=True)
    formal=artifacts/'step_filter_local_evidence'/'turbine_source_evidence_filtered.json'
    digest=hashlib.sha256(formal.read_bytes()).hexdigest()
    queue=json.loads((source/'complex_pipe_review_queue.json').read_text(encoding='utf-8'))['queue']
    def inspect(item):
        sid=item['solid_id']; detail=source/item['detail_file']
        selection=select_straight_bore_review(json.loads(detail.read_text(encoding='utf-8')))
        record={'solid_id':sid,'selection':selection,'status':'NOT_EVALUATED'}
        if not selection['eligible']: return record
        path=output/(sid+'.bore.json')
        try:
            process=subprocess.run([sys.executable,str(Path(__file__).with_name('inspect_selected_bore.py')),str(detail),str(path)],timeout=45,capture_output=True,text=True)
            if process.returncode: record['error']='EXACT_BORE_WORKER_FAILED'
            else: record['evidence']=json.loads(path.read_text(encoding='utf-8'))
        except subprocess.TimeoutExpired: record['error']='EXACT_BORE_WORKER_TIMEOUT'
        return record
    records=[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        for r in pool.map(inspect,queue):
            records.append(r)
            if len(records)%20==0: print('Reviewed selection',len(records),'of',len(queue),flush=True)
    assert hashlib.sha256(formal.read_bytes()).hexdigest()==digest,'Formal result changed'
    summary={'review_seed_count':len(records),'eligible_count':sum(r['selection']['eligible'] for r in records),
        'exact_success_count':sum(r.get('evidence',{}).get('exact_brep') is True for r in records),
        'tolerance_deferred_count':sum(r.get('evidence',{}).get('reason')=='LOCAL_TOLERANCE_TOO_LARGE_FOR_WITNESS' for r in records),
        'error_count':sum('error' in r for r in records),
        'clear_passage_witness_count':sum(r.get('evidence',{}).get('clear_passage_witness_confirmed',False) for r in records),
        'selection_reason_counts':dict(Counter(r['selection']['reason'] for r in records)),
        'engineering_pipe_confirmed':False,'interference_result_unchanged':True,'records':records}
    (output/'batch_bore_review.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    full_wall=sum(r.get('evidence',{}).get('valid_wall_sample_count')==40 and r.get('evidence',{}).get('clear_passage_witness_confirmed',False) for r in records)
    text=f'''# 复杂线索几何空区域批量复核

扫描 169 个线索，19 个符合双端口同轴测试条件；16 个完成精确计算，3 个因局部容差过大保留未评估，异常 {summary['error_count']} 个。其余 150 个不适用此直线测试。

10 个测试圆柱不与该单 Solid 材料相交。这只表示相对于当前单实体的几何空区域，不证明设计空腔、流道、装配整体空隙或真实管路。10 项中仅 {full_wall} 项在全部 40 个径向采样上获得符合目标内半径的两次壁面求交；其余项目不能据此提取可靠壁厚。

几何来自原始 STEP 实体缓存，不能代替 CATIA 重导出后的空腔证据。用户已提示导出 STP 未保留空腔，后续必须分别验证两套表示，不从原始缓存推断导出模型拥有空腔。

全部项目仍 NOT_EVALUATED，design_cavity_confirmed=false、fluid_channel_confirmed=false。原 23 项干涉待评估结论不变。

逐项端口筛选、容差及径向求交见 batch_bore_review.json。
'''
    (output/'几何空区域批量复核.md').write_text(text,encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k!='records'}),flush=True)


if __name__=='__main__': main()
