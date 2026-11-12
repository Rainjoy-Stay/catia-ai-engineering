"""Read-only source/export comparison; sampling is evidence, never a verdict."""
import json
from pathlib import Path
from catia_checker.occt_brep import OCCTBRepModel


def inspect(first, second):
    model = OCCTBRepModel()
    model.load_brep('A', first); model.load_brep('B', second)
    result = model.local_overlap_evidence('A', 'B')
    bounds = result['common_bounds_mm']
    points = [result['centroid_mm']]
    if bounds:
        points += [[bounds['min'][i] + (bounds['max'][i]-bounds['min'][i])*f[i]
                    for i in range(3)] for f in
                   ((x,y,z) for x in (.1,.3,.5,.7,.9) for y in (.1,.3,.5,.7,.9)
                    for z in (.1,.3,.5,.7,.9))]
    result['tolerance_sampling'] = []
    for tolerance in (1e-7, 1e-6, 1e-5, 1e-4, result['classification_tolerance_mm']):
        counts = {}
        for point in points:
            states = '/'.join(model.classify_point(s, point, tolerance)['point_state']
                              for s in ('A', 'B'))
            counts[states] = counts.get(states, 0) + 1
        result['tolerance_sampling'].append({'tolerance_mm': tolerance,
                                            'point_count': len(points), 'states': counts})
    result['input_paths'] = [str(first.resolve()), str(second.resolve())]
    return result


def main():
    artifacts = Path(__file__).resolve().parents[1] / 'artifacts'
    directory = artifacts / 'step_filter_local_evidence'
    records = []
    for issue, body, entity in [('SINGLEPART-3E0F0776CC7F', 840, 39358),
                                 ('SINGLEPART-C63A5532AA23', 841, 39359)]:
        source = artifacts / 'step_filter_source_recheck'
        exported = artifacts / 'step_filter_body_recheck'
        original = inspect(source / 'source_39346.brep', source / f'source_{entity}.brep')
        derived = inspect(exported / 'body_828_STEP_SOLID_0001.brep',
                          exported / f'body_{body}_STEP_SOLID_0001.brep')
        record = {'issue_id': issue, 'body_pair': [828, body],
                  'source_entities': [39346, entity], 'original_step': original,
                  'catia_export': derived, 'status': 'NOT_EVALUATED',
                  'source_binding': 'Explicit STEP entity references from retained Body names',
                  'comparison_limit': 'Source and export topology may differ; no identical-shape claim',
                  'sampling_limit': 'No sampled IN/IN point does not prove absence of overlap',
                  'engineering_intent_inferred': False}
        records.append(record)
        (directory / 'thin_overlap_sensitivity.json').write_text(
            json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
        print(issue, original['volume_mm3'], derived['volume_mm3'], flush=True)


if __name__ == '__main__':
    main()
