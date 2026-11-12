"""Explicit inspection scope via a result-without-link copy, never source deletion."""
import json
import time
from pathlib import Path


def export_scope_derivative(conn, source_name, excluded_set_names, file_path, audit_path):
    conn.ensure_connected()
    source = conn.active_document
    if str(source.Name) != source_name:
        raise ValueError('Active source does not match requested document')
    output, audit_file = Path(file_path).resolve(), Path(audit_path).resolve()
    if output.suffix.lower() not in ('.stp', '.step') or output.exists() or audit_file.exists():
        raise ValueError('Require new STEP and audit paths; overwrite prohibited')
    part = source.Part
    bodies = [part.Bodies.Item(i) for i in range(1, part.Bodies.Count + 1)]
    groups = [part.HybridBodies.Item(i) for i in range(1, part.HybridBodies.Count + 1)]
    excluded = set(excluded_set_names)
    if not excluded or len(excluded) != len(excluded_set_names):
        raise ValueError('Require unique explicit exclusions')
    names = [str(g.Name) for g in groups]
    if any(names.count(name) != 1 for name in excluded):
        raise ValueError('Excluded set names must resolve uniquely')
    retained = [g for g in groups if str(g.Name) not in excluded]
    before = (bool(source.Saved), len(bodies), len(groups))
    audit = {'source_document': source_name, 'source_saved_before': before[0],
             'source_modified': False, 'formal_coverage_complete': False,
             'exclusion_reason': 'USER_APPROVED_SUSPECT_IMPORT_FAILURE_SCOPE_TRIAL',
             'dependency_validation': 'NOT_PROVEN; source retained; copied geometry is result-without-link',
             'excluded_sets': [], 'retained_set_names': [str(g.Name) for g in retained],
             'expected_bodies': len(bodies), 'expected_retained_elements': sum(int(g.HybridShapes.Count) for g in retained),
             'phase': 'INVENTORY', 'status': 'RUNNING'}
    output.parent.mkdir(parents=True, exist_ok=True)
    audit_file.parent.mkdir(parents=True, exist_ok=True)
    def save():
        audit_file.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf-8')
    selection = source.Selection
    target = None
    started = time.monotonic()
    try:
        for group in groups:
            if str(group.Name) not in excluded:
                continue
            selection.Clear(); selection.Add(group)
            try: show = int(selection.VisProperties.GetShow())
            except Exception: show = None
            audit['excluded_sets'].append({'name':str(group.Name), 'parent':'Part',
                'type':'HybridBody', 'visibility_raw':show,
                'elements':[str(group.HybridShapes.Item(i).Name) for i in range(1,group.HybridShapes.Count+1)]})
        selection.Clear()
        audit['phase'] = 'COPY_RETAINED_GEOMETRY'; save()
        for obj in [*bodies, *retained]: selection.Add(obj)
        selection.Copy(); selection.Clear()
        target = conn.app.Documents.Add('Part')
        target.Activate()
        dest = target.Selection
        dest.Clear(); dest.Add(target.Part)
        dest.PasteSpecial('CATPrtResultWithOutLink'); dest.Clear()
        audit['derivative_document'] = str(target.Name)
        audit['phase'] = 'VERIFY_COPY'; save()
        copied_groups = [target.Part.HybridBodies.Item(i) for i in range(1,target.Part.HybridBodies.Count+1)]
        audit['actual_bodies'] = int(target.Part.Bodies.Count)
        audit['actual_retained_elements'] = sum(int(g.HybridShapes.Count) for g in copied_groups)
        audit['actual_set_names'] = [str(g.Name) for g in copied_groups]
        # CATIA may leave an empty default MainBody alongside copied Bodies.
        actual_nonempty = sum(int(target.Part.Bodies.Item(i).Shapes.Count)>0 for i in range(1,target.Part.Bodies.Count+1))
        expected_nonempty = sum(int(b.Shapes.Count)>0 for b in bodies)
        if actual_nonempty != expected_nonempty or audit['actual_retained_elements'] != audit['expected_retained_elements']:
            raise RuntimeError('Copy coverage mismatch; derivative is not valid for checking')
        if any(name in audit['actual_set_names'] for name in excluded):
            raise RuntimeError('Excluded set unexpectedly present in derivative')
        target.Part.Update()
        audit['phase'] = 'STEP_EXPORT'; save()
        target.ExportData(str(output), 'stp')
        if not output.is_file() or not output.stat().st_size:
            raise RuntimeError('STEP export produced no file')
        audit.update(status='COMPLETE', phase='EXPORTED', file=str(output), size_bytes=output.stat().st_size,
                     derivative_saved=False, copy_count_verified=True)
    except Exception as exc:
        audit.update(status='ERROR', error=str(exc)); raise
    finally:
        source.Activate(); selection.Clear()
        after = (bool(source.Saved), int(part.Bodies.Count), int(part.HybridBodies.Count))
        audit['source_state_unchanged'] = before == after
        audit['elapsed_seconds'] = time.monotonic() - started
        save()
        if before != after:
            raise RuntimeError('Source state changed unexpectedly')
    return json.dumps(audit, ensure_ascii=False)
