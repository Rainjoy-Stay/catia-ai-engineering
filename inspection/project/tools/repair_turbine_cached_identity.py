"""Repair cached origins using unique spatial geometry, never label/order fallback."""
import copy
import json
import subprocess
import sys
from pathlib import Path
from catia_checker.occt_brep import OCCTBRepModel
from catia_checker.geometry_fingerprint import match_geometry_records
from standalone.step_interference_filter import filter_result


def main():
    root = Path(__file__).resolve().parents[1]
    previous = root / 'artifacts' / 'step_filter_body_recheck'
    output = root / 'artifacts' / 'step_filter_local_evidence'
    output.mkdir(parents=True, exist_ok=True)
    original = json.loads((root / 'artifacts' / 'live_acceptance_20260916' / 'turbine_traceability_merged.json').read_text(encoding='utf-8'))
    replay = json.loads((previous / 'body_recheck.json').read_text(encoding='utf-8'))
    payload = json.loads((previous / 'turbine_rechecked_filtered.json').read_text(encoding='utf-8'))
    failures = [f for f in original['findings'] if f['status'] == 'FAIL']
    targets = {f['metadata'][f'geometry_object_{s}'] for f in failures for s in ('a', 'b')}
    old = {s['shape_id']: s for s in original['large_single_part_analysis']['batch_plan']['shapes']}
    candidates = []
    for body in replay['export_audit']['body_mapping']:
        for path in previous.glob(f"body_{body['source_body_index']}_STEP_SOLID_*.brep"):
            model = OCCTBRepModel(); model.load_brep('CACHE', path)
            record = model.describe('CACHE'); record.update(model.solid_face_provenance('CACHE'))
            candidates.append({**record, 'cache_id': str(path), 'cache_file': str(path),
                               'source_body_index': body['source_body_index'],
                               'source_body_name': body['source_body_name']})
    matched = match_geometry_records([old[s] for s in sorted(targets)], candidates,
                                      source_id='shape_id', target_id='cache_id')
    by_cache = {c['cache_id']: c for c in candidates}
    matches, corrections = {}, []
    for item in matched['matches']:
        sid = item['source_id']; candidate = by_cache[item['target_id']]
        matches[sid] = {'candidate': candidate, 'comparison': item}
        if old[sid].get('source_body_index') != candidate['source_body_index']:
            corrections.append({'shape_id': sid, 'old_body': old[sid].get('source_body_index'),
                                'new_body': candidate['source_body_index'], 'checks': item['checks']})
    raw = {f['issue_id']: f for f in payload['large_single_part_analysis']['analysis']['findings']}
    by_pair = {p['issue_id']: p for p in replay['pairs']}
    pairs = []
    for finding in failures:
        meta = finding['metadata']; a, b = meta['geometry_object_a'], meta['geometry_object_b']
        pair = copy.deepcopy(by_pair[finding['issue_id']])
        if 'fact' not in pair and a in matches and b in matches:
            path = output / f"{finding['issue_id']}.exact.json"
            process = subprocess.run([sys.executable, str(Path(__file__).with_name('inspect_cached_brep_pair.py')),
                matches[a]['candidate']['cache_file'], matches[b]['candidate']['cache_file'], '--output', str(path)],
                timeout=60, capture_output=True, text=True)
            if process.returncode:
                pair['error'] = 'EXACT_WORKER_FAILED'
            else:
                pair.pop('error', None); pair['fact'] = json.loads(path.read_text(encoding='utf-8'))
        if 'fact' in pair:
            fact = raw[pair['issue_id']]
            if 'previous_exact_fact' not in fact:
                fact['previous_exact_fact'] = copy.deepcopy(fact)
            fact.update(pair['fact']['distance']); fact.update(pair['fact']['common'])
            fact['distance_evidence'] = pair['fact']['distance']; fact['common_volume_evidence'] = pair['fact']['common']
        pairs.append(pair)
    for shape in payload['large_single_part_analysis']['batch_plan']['shapes']:
        sid = shape['shape_id']
        if sid in matches:
            candidate = matches[sid]['candidate']
            shape['previous_source_identity'] = {k: shape.get(k) for k in
                ('source_body_index', 'source_body_name', 'mapping_method')}
            for key in ('valid', 'solid_count', 'source_body_index', 'source_body_name'):
                shape[key] = candidate[key]
            shape['mapping_method'] = 'CACHED_SINGLE_BODY_UNIQUE_SPATIAL_MULTI_FEATURE_VERIFIED'
            shape['face_ids'] = [f'{sid}::FACE_{i:06d}' for i in range(1, len(candidate['face_ids']) + 1)]
            shape['faces_complete'] = True
    filter_result(payload)
    audit = {'target_count': len(targets), 'matched_count': len(matches), 'corrections': corrections,
             'unresolved': matched['unresolved'], 'tolerances_relaxed': False, 'source_modified': False}
    payload['audit']['cached_identity_repair'] = audit
    payload['audit']['focused_body_recheck']['verified_solid_count'] = len(matches)
    payload['audit']['focused_body_recheck']['recomputed_pair_count'] = sum('fact' in p for p in pairs)
    for name, data in [('identity_repair.json', {'audit': audit, 'matches': matches, 'pairs': pairs}),
                       ('turbine_identity_corrected.json', payload)]:
        (output / name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(audit, ensure_ascii=False))


if __name__ == '__main__':
    main()
