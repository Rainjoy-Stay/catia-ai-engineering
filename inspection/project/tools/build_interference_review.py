"""Merge completed morphology and independent diagnostics into a review queue."""
import json, sys, hashlib
from pathlib import Path
from collections import Counter
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from catia_checker.interference_review import assess
from catia_checker.occt_session_cache import atomic_json

def main():
    root = Path(sys.argv[1]).resolve()
    evidence_files = [root/'shape-triage-pilot.json', root/'shape-review/review.json',
                      root/'shape-review/round-2/review.json', root/'shape-review/b1s38-topology.json']
    evidence = {}; loaded = {}
    for path in evidence_files:
        if path.is_file():
            raw = path.read_bytes(); evidence[str(path.relative_to(root))] = hashlib.sha256(raw).hexdigest()
            loaded[path.name if path.name != 'review.json' else path.parent.relative_to(root).as_posix()] = json.loads(raw)
    triage = loaded['shape-triage-pilot.json']; reviews = {}
    for key in ('shape-review', 'shape-review/round-2'):
        for row in loaded.get(key, {}).get('rows', []):
            reviews[tuple(sorted(row['pair']))] = row
    invalid = set()
    topology = loaded.get('b1s38-topology.json', {})
    if topology.get('valid') is False:
        invalid.add(topology['shape_id'])
    rows = [assess(row, reviews.get(tuple(sorted(row['pair']))), invalid) for row in triage['rows']]
    source_path=root/'shape-review/ten-pair-source-review.json'
    if source_path.exists():
        raw=source_path.read_bytes();evidence[str(source_path.relative_to(root))]=hashlib.sha256(raw).hexdigest()
        source_rows={tuple(sorted(row['pair'])):row for row in json.loads(raw)['rows']}
        for row in rows:
            source=source_rows.get(tuple(sorted(row['pair'])))
            if source:
                row['source_review']=source
                row['next_action']=source['reason']
    comparison_path=root/'shape-review/ten-comparison-summary.json'
    if comparison_path.exists():
        raw=comparison_path.read_bytes();evidence[str(comparison_path.relative_to(root))]=hashlib.sha256(raw).hexdigest()
        conclusions={tuple(sorted(row['pair'])):row for row in json.loads(raw)['rows']}
        for row in rows:
            conclusion=conclusions.get(tuple(sorted(row['pair'])))
            if conclusion:
                row['source_comparison']=conclusion
                row['next_action']=conclusion['reason']
                row['priority']=0
    rows.sort(key=lambda row: (row['priority'], tuple(row['pair'])))
    output = {'schema_version': 'interference-review.v1', 'geometry_fingerprint': triage['geometry_fingerprint'],
              'evidence_sha256': evidence, 'counts': dict(Counter(row['status'] for row in rows)),
              'rows': rows, 'automatic_exclusions': 0, 'source_modified': False,
              'original_verdicts_modified': False, 'basis': 'LOCAL_RULES_AND_RECORDED_GEOMETRY_EVIDENCE',
              'limitations': ['不是 AI 最终判断或工程验收', '复算缓存不等于独立源模型对照',
                              '异常对象不等于其全部相交都是伪干涉', '尚未接入实时 UI']}
    atomic_json(root/'interference-review.json', output)
    print(json.dumps({'counts': output['counts'], 'automatic_exclusions': 0}, ensure_ascii=False))

if __name__ == '__main__': main()
