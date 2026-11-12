"""Verify each saved result and its original inputs before using batch classifications."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from catia_checker.occt_session_cache import digest,atomic_json
root=Path(sys.argv[1]).resolve();review=root/'shape-review';batch=review/'original-retry-batch'
summary=json.loads((batch/'summary.json').read_text(encoding='utf-8'));errors=[]
if summary['checkpoint_sha256']!=digest(root/'checkpoint.json'):errors.append('CHECKPOINT_CHANGED')
source=Path('F:/涡轮发动机_爱给网_aigei_com/涡轮发动机.stp')
if summary['source_step_sha256']!=digest(source):errors.append('SOURCE_CHANGED')
if summary['state']!='COMPLETE' or len(summary['rows'])!=109:errors.append('INCOMPLETE_BATCH')
pairs=[tuple(sorted(r['pair'])) for r in summary['rows']]
if len(set(pairs))!=len(pairs):errors.append('DUPLICATE_PAIRS')
fact_hashes={digest(p):p for p in batch.glob('fact-*.json')};checked=0
for row in summary['rows']:
    if row['status']!='ORIGINAL_RETRY_COMPLETED':
        if row['screen_pass']:errors.append('TIMEOUT_PASSED')
        continue
    checked+=1
    path=fact_hashes.get(row['fact_sha256'])
    if not path or json.loads(path.read_text(encoding='utf-8'))!=row['facts']:errors.append('FACT_CHANGED:'+str(row['pair']))
    paths=[review/f'original-{n}/target.brep' for n in row['original_labels']]
    if [digest(p) for p in paths]!=row['original_brep_sha256']:errors.append('INPUT_CHANGED:'+str(row['pair']))
    fact=row['facts']
    if row['screen_pass'] and not (fact['input_valid']==[True,True] and fact['common_valid'] is True and fact['common_solid_count']==0):errors.append('UNSUPPORTED_PASS')
result={'verified':not errors,'errors':errors,'scope_pairs':len(pairs),'completed_facts_checked':checked,
    'screen_passes':sum(r['screen_pass'] for r in summary['rows']),'summary_sha256':digest(batch/'summary.json')}
atomic_json(review/'original-retry-integrity.json',result);print(json.dumps(result,ensure_ascii=True))
if errors:raise SystemExit(1)
