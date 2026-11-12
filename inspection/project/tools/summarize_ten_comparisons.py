import json,sys
from pathlib import Path
from collections import Counter
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from catia_checker.source_comparison import classify_source_comparison
from catia_checker.occt_session_cache import atomic_json,digest
root=Path(sys.argv[1]).resolve()
original=json.loads((root/'shape-review/ten-original-pairs.json').read_text(encoding='utf-8'))
cached=[]
for filename in ('shape-review/review.json','shape-review/round-2/review.json'):
    cached.extend(json.loads((root/filename).read_text(encoding='utf-8'))['rows'])
lookup={tuple(sorted(r['pair'])):r for r in cached}
checkpoint=json.loads((root/'checkpoint.json').read_text(encoding='utf-8'))
facts={tuple(sorted(r['pair'])):r['fact'] for r in checkpoint['completed_pairs']}
rows=[]
for row in original['rows']:
    key=tuple(sorted(row['pair']));conclusion=classify_source_comparison(row,facts.get(key,{}),lookup.get(key,{}))
    rows.append({'pair':row['pair'],**conclusion,'source_review_status':row['status'],
                 'source_association_certified':row.get('source_association_certified',False),
                 'original_volume_raw_mm3':row.get('details',{}).get('common_volume_raw_mm3')})
result={'rows':rows,'counts':dict(Counter(r['classification'] for r in rows)),
        'source_modified':False,'automatic_conversion_exclusions':0,
        'original_review_sha256':digest(root/'shape-review/ten-original-pairs.json'),
        'checkpoint_sha256':digest(root/'checkpoint.json'),'geometry_fingerprint':checkpoint['geometry_fingerprint']}
atomic_json(root/'shape-review/ten-comparison-summary.json',result)
print(json.dumps(result,ensure_ascii=False))
