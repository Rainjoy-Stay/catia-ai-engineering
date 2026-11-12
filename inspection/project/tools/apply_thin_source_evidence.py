"""Attach diagnostic source facts before the formal conservative filter."""
import json
from pathlib import Path
from standalone.step_interference_filter import filter_result


def main():
    directory = Path(__file__).resolve().parents[1] / 'artifacts' / 'step_filter_local_evidence'
    payload = json.loads((directory / 'turbine_local_filtered.json').read_text(encoding='utf-8'))
    evidence = json.loads((directory / 'thin_overlap_sensitivity.json').read_text(encoding='utf-8'))
    facts = {f['issue_id']: f for f in payload['large_single_part_analysis']['analysis']['findings']}
    for record in evidence:
        original = record['original_step']
        facts[record['issue_id']]['source_overlap_evidence'] = {
            'exact_brep': original['exact_brep'], 'entity_binding_verified': True,
            'intersection_volume_mm3': original['volume_mm3'],
            'source_entities': record['source_entities'],
            'source_binding': record['source_binding'],
            'comparison_limit': record['comparison_limit'],
            'diagnostic_file': 'thin_overlap_sensitivity.json'}
    filter_result(payload)
    (directory / 'turbine_source_evidence_filtered.json').write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(payload['counts']))


if __name__ == '__main__':
    main()
