"""Focused read-only Body exports, exact identity verification and pair replay."""
import argparse
import copy
import json
import subprocess
import sys
from pathlib import Path
from catia_checker.catia_body_batches import export_body_batches
from catia_checker.geometry_fingerprint import compare_geometry_features
from catia_checker.occt_brep import OCCTBRepModel
from standalone.step_interference_filter import filter_result
from r18_connection import R18Connection


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('baseline', type=Path)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    args.directory.mkdir(parents=True, exist_ok=True)
    original = json.loads(args.baseline.read_text(encoding='utf-8'))
    old = {s['shape_id']: s for s in original['large_single_part_analysis']['batch_plan']['shapes']}
    failures = [f for f in original['findings'] if f['status'] == 'FAIL']
    targets = {f['metadata'][f'geometry_object_{s}'] for f in failures for s in ('a', 'b')}
    indices = set()
    for sid in targets:
        record = old[sid]
        if record.get('source_body_index') is not None:
            indices.add(int(record['source_body_index']))
        else:
            batch = int(record['batch_id'].split('_')[-1])
            indices.update(range((batch - 1) * 40 + 1, batch * 40 + 1))
    connection = R18Connection(); connection.connect()
    document = connection.active_document
    if str(document.Name) != original['document'] or int(document.Part.Bodies.Count) != original['source']['source_body_count_before']:
        raise RuntimeError('Source document/name/Body count mismatch')
    for sid in targets:
        record = old[sid]
        if record.get('source_body_index') is not None:
            actual = str(document.Part.Bodies.Item(int(record['source_body_index'])).Name)
            if actual != record.get('source_body_name'):
                raise RuntimeError(f'Source Body name mismatch for {sid}')
    audit = export_body_batches(connection.app, document, args.directory / 'body_exports',
                                batch_size=1, body_indices=sorted(indices),
                                progress=lambda event: print(json.dumps(event), flush=True))
    audit['batch_files'] = [str(p) for p in audit['batch_files']]
    (args.directory / 'export_audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf-8')
    candidates = []
    for body_index, filename in zip(sorted(indices), audit['batch_files']):
        model = OCCTBRepModel()
        manifest = model.load_step(filename, lightweight=False)
        for record in manifest['shapes'][1:]:
            local = record['shape_id']
            cache = args.directory / f'body_{body_index}_{local}.brep'
            model.write_brep(local, cache)
            record.update(model.solid_face_provenance(local))
            candidates.append({**record, 'cache_file': str(cache),
                               'source_body_index': body_index,
                               'source_body_name': str(document.Part.Bodies.Item(body_index).Name)})
    matches = {}
    for sid in sorted(targets):
        options = []
        for candidate in candidates:
            if old[sid].get('source_body_index') is not None and old[sid]['source_body_index'] != candidate['source_body_index']:
                continue
            comparison = compare_geometry_features(old[sid], candidate)
            if comparison['compatible']:
                options.append({'candidate': candidate, 'comparison': comparison})
        if len(options) == 1:
            matches[sid] = options[0]
    pair_results = []
    for finding in failures:
        meta = finding['metadata']; a, b = meta['geometry_object_a'], meta['geometry_object_b']
        item = {'issue_id': finding['issue_id'], 'object_a': a, 'object_b': b}
        if a in matches and b in matches:
            output = args.directory / f"{finding['issue_id']}.exact.json"
            try:
                completed = subprocess.run([sys.executable, str(Path(__file__).with_name('inspect_cached_brep_pair.py')),
                    matches[a]['candidate']['cache_file'], matches[b]['candidate']['cache_file'],
                    '--output', str(output)], timeout=60, capture_output=True, text=True)
                if completed.returncode:
                    item['error'] = 'EXACT_WORKER_FAILED'
                else:
                    item['fact'] = json.loads(output.read_text(encoding='utf-8'))
            except subprocess.TimeoutExpired:
                item['error'] = 'EXACT_PAIR_TIMEOUT'
        else:
            item['error'] = 'UNAMBIGUOUS_SOURCE_IDENTITY_NOT_ESTABLISHED'
        pair_results.append(item)
        print(json.dumps({'stage': 'FOCUSED_PAIR', 'issue_id': item['issue_id'],
                          'error': item.get('error')}), flush=True)
        (args.directory / 'body_recheck.json').write_text(json.dumps(
            {'export_audit': audit, 'target_solid_count': len(targets), 'matches': matches,
             'pairs': pair_results, 'source_modified': False}, ensure_ascii=False, indent=2), encoding='utf-8')
    payload = copy.deepcopy(original)
    raw_by_id = {f['issue_id']: f for f in payload['large_single_part_analysis']['analysis']['findings']}
    for shape in payload['large_single_part_analysis']['batch_plan']['shapes']:
        sid = shape['shape_id']
        if sid in matches:
            candidate = matches[sid]['candidate']
            for key in ('valid', 'solid_count', 'source_body_index', 'source_body_name'):
                shape[key] = candidate[key]
            shape['face_ids'] = [f"{sid}::FACE_{n:06d}" for n in range(1, len(candidate['face_ids'])+1)]
            shape['faces_complete'] = True
            shape['mapping_method'] = 'FOCUSED_SINGLE_BODY_MULTI_FEATURE_VERIFIED'
    for pair in pair_results:
        if 'fact' in pair:
            raw = raw_by_id[pair['issue_id']]
            raw['previous_exact_fact'] = copy.deepcopy(raw)
            raw.update(pair['fact']['distance']); raw.update(pair['fact']['common'])
            raw['distance_evidence'] = pair['fact']['distance']
            raw['common_volume_evidence'] = pair['fact']['common']
    filter_result(payload)
    payload['audit']['focused_body_recheck'] = {
        'verified_solid_count': len(matches), 'target_solid_count': len(targets),
        'recomputed_pair_count': sum('fact' in x for x in pair_results),
        'source_modified': False}
    (args.directory / 'turbine_rechecked_filtered.json').write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
