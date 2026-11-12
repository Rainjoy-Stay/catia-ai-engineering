"""Read-only declaration audit; does not infer identity from identical names."""
import json
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from catia_checker.occt_session_cache import atomic_json, digest

root = Path(sys.argv[1]).resolve()
source = Path('F:/涡轮发动机_爱给网_aigei_com/涡轮发动机.stp')
text = source.read_text(encoding='ascii', errors='replace')
records = {int(m[1]): m[2] for m in re.finditer(r'^\s*#(\d+)\s*=\s*(.*?);', text, re.M | re.S)}
registry = json.loads((root/'registry.json').read_text(encoding='utf-8'))['objects']
receipts = json.loads((root/'body-mapping.json').read_text(encoding='utf-8'))
rows = []
for number in (10, 11, 12):
    identifier = f'BATCH_0044::STEP_SHELL_{number:04d}'
    obj = registry[identifier]
    rows.append({'shape_id': identifier, 'registry': obj,
        'matching_receipts': [r for r in receipts if r.get('batch_id') == 'BATCH_0044'
            and r.get('batch_body_name') == obj.get('source_name')],
        'source_identity_verified': False})
record = records[3068]
references = [int(n) for n in re.findall(r'#(\d+)', record)]
result = {'source_step_sha256': digest(source), 'source_declaration': record,
    'referenced_topology': [{'label': n, 'declaration': records.get(n)} for n in references],
    'rows': rows, 'source_modified': False, 'automatic_conversion_exclusions': 0,
    'limitation': 'STEP topology references alone do not identify CATIA split surfaces or exported shell instances'}
atomic_json(root/'shape-review/contact-shell-source-scope.json', result)
print(json.dumps({'source_label': 3068, 'outer_shell': references[0],
    'inner_shell_count': len(references)-1,
    'reviewed_shells': len(rows),
    'unique_object_receipts': sum(len(r['matching_receipts']) == 1 for r in rows),
    'source_identity_verified': False}, ensure_ascii=False))
