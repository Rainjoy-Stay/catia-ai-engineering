"""Cross-check former FAILs against unmodified original STEP entity geometry."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path
from catia_checker.occt_brep import OCCTBRepModel
from catia_checker.geometry_fingerprint import compare_geometry_features
from OCP.STEPControl import STEPControl_Reader
from OCP.IFSelect import IFSelect_RetDone


def extract_entities(source, ids, output):
    source_bytes = source.read_bytes()
    text = source_bytes.decode('latin-1')
    index = {int(m.group(1)): (m.start(), m.end())
             for m in re.finditer(r'^#(\d+)\s*=.*?;', text, re.M | re.S)}
    # Keep the source representation's unit/uncertainty context unchanged.
    contexts = [n for n, (a, b) in index.items()
                if re.search(r'GEOMETRIC_REPRESENTATION_CONTEXT\s*\(\s*3\s*\)', text[a:b])]
    if len(contexts) != 1:
        raise RuntimeError('Requires one unambiguous source representation context')
    selected, pending = set(), list(ids) + contexts
    while pending:
        n = pending.pop()
        if n in selected:
            continue
        if n not in index:
            raise RuntimeError(f'Missing STEP entity #{n}')
        selected.add(n)
        a, b = index[n]
        record = re.sub(r"'(?:''|[^'])*'", "''", text[a:b].split('=', 1)[1])
        pending.extend(int(x) for x in re.findall(r'#(\d+)', record))
    next_id = max(index) + 1
    header = text[:text.index('DATA;') + 5]
    representation = f"#{next_id}=ADVANCED_BREP_SHAPE_REPRESENTATION('SOURCE_RECHECK',({','.join('#'+str(n) for n in sorted(ids))}),#{contexts[0]});"
    n = next_id
    representation += '\n' + '\n'.join([
        f"#{n+1}=SHAPE_DEFINITION_REPRESENTATION(#{n+2},#{n});",
        f"#{n+2}=PRODUCT_DEFINITION_SHAPE('','',#{n+3});",
        f"#{n+3}=PRODUCT_DEFINITION('design','',#{n+4},#{n+5});",
        f"#{n+4}=PRODUCT_DEFINITION_FORMATION('','',#{n+6});",
        f"#{n+5}=PRODUCT_DEFINITION_CONTEXT('part definition',#{n+7},'design');",
        f"#{n+6}=PRODUCT('SOURCE','SOURCE','',(#{n+8}));",
        f"#{n+7}=APPLICATION_CONTEXT('automotive design');",
        f"#{n+8}=PRODUCT_CONTEXT('',#{n+7},'mechanical');"])
    records = []
    for n in sorted(selected):
        record = text[index[n][0]:index[n][1]]
        if n in ids:
            record, changed = re.subn(r"((?:MANIFOLD_SOLID_BREP|BREP_WITH_VOIDS)\s*\()'(?:''|[^'])*'",
                         lambda m: m.group(1) + f"'SOURCE_ENTITY_{n}'", record, count=1)
            if changed != 1:
                raise RuntimeError(f'Unsupported solid entity #{n}')
        records.append(record)
    output.write_text(header + '\n' + '\n'.join(records) + '\n' + representation +
                      '\nENDSEC;\nEND-ISO-10303-21;\n', encoding='latin-1')
    return {'source_sha256': hashlib.sha256(source_bytes).hexdigest(),
            'source_entity_count': len(index), 'extracted_entity_count': len(selected),
            'context_entity': contexts[0], 'geometry_records_changed': False,
            'solid_labels_changed_for_binding': True, 'binding_method': 'SINGLE_ENTITY_PRODUCT_ROOT'}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('source', type=Path)
    p.add_argument('baseline', type=Path)
    p.add_argument('directory', type=Path)
    args = p.parse_args()
    args.directory.mkdir(parents=True, exist_ok=True)
    baseline = json.loads(args.baseline.read_text(encoding='utf-8'))
    findings = [f for f in baseline['findings'] if f['status'] == 'FAIL']
    old = {s['shape_id']: s for s in baseline['large_single_part_analysis']['batch_plan']['shapes']}
    targets = {f['metadata'][f'geometry_object_{s}'] for f in findings for s in ('a', 'b')}
    entities = {}
    for sid in sorted(targets):
        label = old[sid].get('source_body_name') or old[sid].get('source_name') or ''
        match = re.fullmatch(r'(?:MANIFOLD_SOLID_BREP|BREP_WITH_VOIDS) #(\d+)', label)
        if match:
            entities[sid] = int(match[1])
    subset = args.directory / 'original_entities.step'
    audit = extract_entities(args.source, set(entities.values()), subset)
    print(json.dumps({'stage': 'SOURCE_SUBSET', **audit}), flush=True)
    reader = STEPControl_Reader()
    if reader.ReadFile(str(subset.resolve())) != IFSelect_RetDone:
        raise RuntimeError('Source subset STEP read failed')
    step = reader.StepModel()
    if reader.TransferRoots() <= 0:
        raise RuntimeError('Source subset transferred no roots')
    by_label = {}
    for i in range(1, step.NbEntities() + 1):
        entity = step.Entity(i)
        if hasattr(entity, 'Name'):
            name = entity.Name()
            if name and hasattr(name, 'ToCString') and name.ToCString().startswith('SOURCE_ENTITY_'):
                by_label[int(name.ToCString().split('_')[-1])] = entity
    model, records, identities = OCCTBRepModel(), {}, {}
    subset_text = subset.read_text(encoding='latin-1')
    for sid, label in entities.items():
        # A product root with exactly one explicitly referenced source entity
        # avoids any reliance on reader traversal order or missing transfer binders.
        single = args.directory / f'source_{label}.step'
        single.write_text(re.sub(r"(ADVANCED_BREP_SHAPE_REPRESENTATION\('SOURCE_RECHECK',)\([^)]*\)",
                                lambda m: m.group(1) + f'(#{label})', subset_text), encoding='latin-1')
        single_reader = STEPControl_Reader()
        if single_reader.ReadFile(str(single.resolve())) != IFSelect_RetDone or single_reader.TransferRoots() <= 0:
            identities[sid] = {'verified': False, 'reason': 'TRANSFER_FAILED'}
            continue
        shape = single_reader.OneShape()
        if shape.IsNull():
            identities[sid] = {'verified': False, 'reason': 'TRANSFER_FAILED'}
            continue
        record = model.register_shape(sid, shape)
        record.update(model.solid_face_provenance(sid))
        comparison = compare_geometry_features(record, old[sid],
                       {'relative_volume': 1e-4, 'relative_area': 1e-4,
                        'centroid_mm': 1e-3, 'bounds_mm': 1e-3})
        identities[sid] = {'source_step_entity': label, 'verified': comparison['compatible'],
                           'comparison': comparison}
        records[sid] = record
        model.write_brep(sid, args.directory / f'source_{label}.brep')
        print(json.dumps({'stage': 'SOURCE_SOLID', 'shape_id': sid,
                          'valid': record['valid'], 'identity_verified': comparison['compatible']}), flush=True)
    results = []
    for finding in findings:
        meta = finding['metadata']
        a, b = meta['geometry_object_a'], meta['geometry_object_b']
        item = {'issue_id': finding['issue_id'], 'object_a': a, 'object_b': b,
                'old_volume_mm3': finding['measured_value'], 'status': 'NOT_EVALUATED'}
        if all(identities.get(s, {}).get('verified') for s in (a, b)):
            fact = {**model.distance(a, b), **model.common_volume(a, b)}
            item.update(fact)
            item['source_overlap_present'] = fact['intersection_volume_mm3'] > 0
            item['diagnostic'] = ('OVERLAP_PRESENT_IN_ORIGINAL_STEP_INTENT_UNCONFIRMED'
                                  if item['source_overlap_present'] else 'OVERLAP_NOT_REPRODUCED_IN_SOURCE')
        else:
            item['diagnostic'] = 'SOURCE_AND_DERIVATIVE_IDENTITY_UNCONFIRMED'
        results.append(item)
        result = {'source_file': str(args.source), 'audit': audit, 'identities': identities,
                  'source_solids': records, 'pairs': results, 'source_modified': False,
                  'full_model_acceptance': False}
        (args.directory / 'source_recheck.json').write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({'stage': 'SOURCE_PAIR', **item}), flush=True)


if __name__ == '__main__':
    main()
