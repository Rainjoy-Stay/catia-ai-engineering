import json,sys
from pathlib import Path
from collections import Counter
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from catia_checker.source_provenance import trace_identity
from catia_checker.occt_session_cache import atomic_json,digest
root=Path(sys.argv[1]).resolve();objects=json.loads((root/'registry.json').read_text(encoding='utf-8'))['objects']
receipts=json.loads((root/'body-mapping.json').read_text(encoding='utf-8'))
review=json.loads((root/'shape-review/ten-pair-source-review.json').read_text(encoding='utf-8'))
rows=[trace_identity(i,objects,receipts) for i in sorted({i for r in review['rows'] for i in r['pair']})]
atomic_json(root/'shape-review/ten-provenance-audit.json',{'rows':rows,'registry_sha256':digest(root/'registry.json'),
    'receipt_sha256':digest(root/'body-mapping.json'),'source_modified':False,'geometry_mapping_modified':False})
print(json.dumps({'traced':sum(r['source_identity_traced'] for r in rows),'total':len(rows),
    'reasons':dict(Counter(r['reason'] for r in rows))},ensure_ascii=False))
