"""Diagnose failed identities against every explicit single-Body cache, no tolerances relaxed."""
import json
from pathlib import Path
from catia_checker.occt_brep import OCCTBRepModel
from catia_checker.geometry_fingerprint import compare_geometry_features


def main():
    root = Path(__file__).resolve().parents[1]
    directory = root / 'artifacts' / 'step_filter_body_recheck'
    baseline = json.loads((root / 'artifacts' / 'live_acceptance_20260916' / 'turbine_traceability_merged.json').read_text(encoding='utf-8'))
    replay = json.loads((directory / 'body_recheck.json').read_text(encoding='utf-8'))
    old = {s['shape_id']: s for s in baseline['large_single_part_analysis']['batch_plan']['shapes']}
    targets = {f['metadata'][f'geometry_object_{s}'] for f in baseline['findings'] if f['status'] == 'FAIL' for s in ('a', 'b')}
    candidates = []
    for body in replay['export_audit']['body_mapping']:
        for path in directory.glob(f"body_{body['source_body_index']}_STEP_SOLID_*.brep"):
            model = OCCTBRepModel(); model.load_brep('CACHE', path)
            record = model.describe('CACHE')
            candidates.append({**record, 'cache_file': str(path),
                'source_body_index': body['source_body_index'], 'source_body_name': body['source_body_name']})
    diagnostics = []
    for sid in sorted(targets - set(replay['matches'])):
        ranked = []
        for candidate in candidates:
            comparison = compare_geometry_features(old[sid], candidate)
            ranked.append({'source_body_index': candidate['source_body_index'],
                           'source_body_name': candidate['source_body_name'],
                           'cache_file': candidate['cache_file'], 'comparison': comparison})
        ranked.sort(key=lambda x: x['comparison']['score'])
        exact = [x for x in ranked if x['comparison']['compatible']]
        diagnostics.append({'shape_id': sid, 'previous_body_index': old[sid].get('source_body_index'),
                            'previous_body_name': old[sid].get('source_body_name'),
                            'compatible_candidate_count': len(exact),
                            'compatible_candidates': exact, 'nearest_candidates': ranked[:3]})
    output = {'unresolved_count': len(diagnostics), 'candidate_count': len(candidates),
              'tolerances_relaxed': False, 'diagnostics': diagnostics}
    (directory / 'unresolved_diagnostics.json').write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
