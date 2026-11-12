"""Resume original STEP retries without changing the CATIA/checkpoint baseline."""
import argparse,concurrent.futures,json,os,subprocess,sys,threading,time
from collections import Counter
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from catia_checker.occt_session_cache import atomic_json,digest

def main():
    parser=argparse.ArgumentParser();parser.add_argument('directory',type=Path)
    parser.add_argument('--workers',type=int,default=4);parser.add_argument('--pair-timeout',type=float,default=60)
    args=parser.parse_args();root=args.directory.resolve();review=root/'shape-review';tools=Path(__file__).resolve().parent
    choice=json.loads((review/'baseline-choice.json').read_text(encoding='utf-8'))
    source=Path('F:/涡轮发动机_爱给网_aigei_com/涡轮发动机.stp');source_hash=digest(source)
    queue=json.loads((review/'original-retry-queue.json').read_text(encoding='utf-8'))
    checkpoint_hash=digest(root/'checkpoint.json')
    if choice['baseline']!='ORIGINAL_STEP' or choice['source_step_sha256']!=source_hash or choice['geometry_fingerprint']!=queue['geometry_fingerprint']:
        raise ValueError('Original source baseline mismatch')
    if queue['checkpoint_sha256']!=checkpoint_hash:raise ValueError('Retry queue checkpoint stale')
    output=review/'original-retry-batch';output.mkdir(exist_ok=True)
    lockpath=output/'run.lock'
    # Never remove somebody else's lock or launch a duplicate runner.
    lockfd=os.open(lockpath,os.O_CREAT|os.O_EXCL|os.O_WRONLY);os.write(lockfd,str(os.getpid()).encode());os.close(lockfd)
    workers=max(1,min(8,args.workers));label_locks={n:threading.Lock() for r in queue['rows'] for n in r['original_labels']}
    import_gate=threading.Semaphore(1);result_lock=threading.Lock();results={};active={};started=time.time()
    items=[r for r in queue['rows'] if r['status']=='ORIGINAL_SOLID_RETRY_READY']
    def publish(state):
        payload={'state':state,'pid':os.getpid(),'baseline':'ORIGINAL_STEP',
            'geometry_fingerprint':queue['geometry_fingerprint'],'source_step_sha256':source_hash,
            'checkpoint_sha256':checkpoint_hash,'workers':workers,'started_at_unix':started,
            'total':len(items),'completed':len(results),'counts':dict(Counter(r['status'] for r in results.values())),
            'passed':sum(r['screen_pass'] for r in results.values()),'active':list(active.values()),
            'rows':list(results.values()),'mapping_required':11,'source_modified':False,'legacy_checkpoint_modified':False}
        try:atomic_json(output/'summary.json',payload)
        except OSError as exc:
            if state!='RUNNING':raise
            # Individual result files remain authoritative; snapshot is optional.
            print(json.dumps({'event':'PROGRESS_SNAPSHOT_DEFERRED','error':str(exc)}),flush=True)
    def ensure_original(label):
        with label_locks[label]:
            directory=review/f'original-{label}';audit_path=directory/'audit.json';brep=directory/'target.brep'
            if not audit_path.exists() or not brep.exists():
                with import_gate:
                    subprocess.run([sys.executable,str(tools/'check_original_3067.py'),str(root),str(label)],
                        timeout=60,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
            audit=json.loads(audit_path.read_text(encoding='utf-8'))
            if audit.get('actual_target_label',audit.get('step_entity'))!=label or audit['source_sha256']!=source_hash:
                raise ValueError('Original target identity/source mismatch')
            return brep
    def run(index,item):
        key='|'.join(item['pair']);result_path=output/f'result-{index:03d}.json';fact_path=output/f'fact-{index:03d}.json'
        with result_lock:
            active[key]={'pair':item['pair'],'stage':'ORIGINAL_CACHE_OR_LOCAL_TRANSFER'};publish('RUNNING')
        row={'pair':item['pair'],'original_labels':item['original_labels'],'screen_pass':False,
            'source_step_sha256':source_hash,'geometry_fingerprint':queue['geometry_fingerprint']}
        clock=time.monotonic()
        try:
            if result_path.exists():
                saved=json.loads(result_path.read_text(encoding='utf-8'))
                cached_paths=[review/f'original-{label}/target.brep' for label in item['original_labels']]
                inputs_match=all(p.exists() for p in cached_paths) and [digest(p) for p in cached_paths]==saved.get('original_brep_sha256')
                if inputs_match and saved['pair']==item['pair'] and saved['source_step_sha256']==source_hash and saved['geometry_fingerprint']==queue['geometry_fingerprint'] and saved.get('status')=='ORIGINAL_RETRY_COMPLETED' and fact_path.exists() and digest(fact_path)==saved['fact_sha256']:
                    row=saved;return row
            paths=[ensure_original(n) for n in item['original_labels']]
            with result_lock:active[key]['stage']='ORIGINAL_BOOLEAN_COMMON';publish('RUNNING')
            subprocess.run([sys.executable,str(tools/'review_shape_candidates.py'),str(root),'--worker',
                *map(str,paths),str(fact_path)],timeout=args.pair_timeout,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
            facts=json.loads(fact_path.read_text(encoding='utf-8'))
            valid=facts.get('input_valid')==[True,True] and facts.get('common_valid') is True
            row.update(status='ORIGINAL_RETRY_COMPLETED',facts=facts,fact_sha256=digest(fact_path),
                original_brep_sha256=[digest(p) for p in paths],screen_pass=valid and facts.get('common_solid_count')==0,
                reason='原始 STEP 实体干涉复算；无效、重叠或计算不足不自动通过')
        except subprocess.TimeoutExpired:row.update(status='ORIGINAL_RETRY_TIMEOUT',reason='达到局部复算时间上限，保留未评价')
        except Exception as exc:row.update(status='ORIGINAL_RETRY_ERROR',reason=str(exc))
        finally:
            row['elapsed_seconds']=time.monotonic()-clock
            atomic_json(result_path,row)
            with result_lock:
                results[key]=row;active.pop(key,None);publish('RUNNING')
            print(json.dumps({'pair':row['pair'],'status':row.get('status'),'screen_pass':row['screen_pass']},ensure_ascii=True),flush=True)
        return row
    try:
        publish('RUNNING')
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            list(pool.map(lambda indexed:run(*indexed),enumerate(items)))
        if digest(root/'checkpoint.json')!=checkpoint_hash or digest(source)!=source_hash:raise RuntimeError('Baseline changed during run')
        publish('COMPLETE')
    except Exception:
        publish('ERROR');raise
    finally:lockpath.unlink()

if __name__=='__main__':main()
