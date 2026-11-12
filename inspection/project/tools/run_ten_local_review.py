import json,sys,subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from catia_checker.occt_session_cache import atomic_json
root=Path(sys.argv[1]).resolve();rows=[]
for index in range(3,10):
    row={'pair_index':index}
    try:
        subprocess.run([sys.executable,str(Path(__file__).with_name('audit_local_penetration.py')),str(root),str(index)],
                       timeout=45,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        data=json.loads((root/f'shape-review/local-penetration-pair-{index:02d}.json').read_text(encoding='utf-8'))
        witnesses=[w for region in data['rows'] for w in region['interior_witnesses']]
        both=lambda w,a,b:all(w['input_states'][key]=='TopAbs_State.TopAbs_IN' for key in (a,b))
        row.update(status='COMPLETED',pair=data['pair'],witness_count=len(witnesses),
                   original_internal_witness_count=sum(both(w,'OA','OB') for w in witnesses),
                   cached_internal_witness_count=sum(both(w,'A','B') for w in witnesses),
                   missing_witness_regions=sum(not r['interior_witnesses'] for r in data['rows']))
    except subprocess.TimeoutExpired:row.update(status='TIMEOUT')
    except Exception as exc:row.update(status='ERROR',reason=str(exc))
    rows.append(row);atomic_json(root/'shape-review/ten-local-review.json',{'rows':rows,'source_modified':False})
    print(json.dumps(row,ensure_ascii=False),flush=True)
