"""Extract local evidence for repaired identities; keep geometry separate from intent."""
import json
import math
import subprocess
import sys
from collections import Counter
from pathlib import Path
from standalone.step_interference_filter import filter_result


def main():
    root = Path(__file__).resolve().parents[1]
    directory = root / 'artifacts' / 'step_filter_local_evidence'
    replay = json.loads((directory / 'identity_repair.json').read_text(encoding='utf-8'))
    payload = json.loads((directory / 'turbine_identity_corrected.json').read_text(encoding='utf-8'))
    findings = {f['issue_id']: f for f in payload['findings']}
    records = []
    for pair in replay['pairs']:
        sid = pair['issue_id']; path = directory / f'{sid}.local.json'
        a, b = (replay['matches'][pair[f'object_{s}']]['candidate'] for s in ('a','b'))
        item = {'issue_id': sid, 'body_a': a['source_body_index'], 'body_b': b['source_body_index']}
        try:
            process = subprocess.run([sys.executable, str(Path(__file__).with_name('inspect_turbine_local_pair.py')),
                        a['cache_file'], b['cache_file'], '--output', str(path)],
                        timeout=45, capture_output=True, text=True)
            if process.returncode:
                item['error'] = 'LOCAL_EVIDENCE_WORKER_FAILED'
            else:
                evidence = json.loads(path.read_text(encoding='utf-8'))
                item['evidence'] = evidence
                features = {s: [f['surface_features'] for f in evidence[f'faces_{s}']]
                            for s in ('a','b')}
                counts = {s: dict(Counter(f['surface_type'] for f in fs if f))
                          for s,fs in features.items()}
                annuli = {s: sum(bool(f.get('circular_inner_boundaries')) for f in fs if f)
                          for s,fs in features.items()}
                cylinders = {s: [f for f in fs if f and f['surface_type']=='CYLINDER']
                             for s,fs in features.items()}
                angles = []
                for ca in cylinders['a']:
                    for cb in cylinders['b']:
                        dot = abs(sum(x*y for x,y in zip(ca['axis_direction'], cb['axis_direction'])))
                        angles.append(math.degrees(math.acos(min(1.,dot))))
                item['analytic_summary'] = {'surface_type_counts': counts, 'annular_face_counts': annuli,
                                             'minimum_cylinder_axis_angle_deg': min(angles) if angles else None}
                item['geometry_diagnostic'] = ('ROBUST_MATERIAL_OVERLAP' if evidence['robust_interior_witness_found']
                                                else 'COMMON_VOLUME_WITHOUT_ROBUST_MARGIN_WITNESS')
                item['review_question'] = ('是否存在批准的连接/装配重叠范围？' if evidence['robust_interior_witness_found']
                                           else '请先复核局部公差及转换差异，再核对设计关系。')
                findings[sid]['metadata']['local_overlap_evidence'] = item
        except subprocess.TimeoutExpired:
            item['error'] = 'LOCAL_EVIDENCE_TIMEOUT'
        records.append(item)
        (directory / 'local_evidence_ledger.json').write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({'issue_id': sid, 'diagnostic': item.get('geometry_diagnostic'),
                          'error': item.get('error')}), flush=True)
    filter_result(payload)
    payload['audit']['local_overlap_evidence'] = {'pair_count': len(records),
         'successful_count': sum('evidence' in r for r in records),
         'robust_witness_count': sum(r.get('geometry_diagnostic')=='ROBUST_MATERIAL_OVERLAP' for r in records),
         'engineering_intent_inferred': False}
    (directory / 'turbine_local_filtered.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(payload['audit']['local_overlap_evidence']))


if __name__ == '__main__':
    main()
