"""Evidence-based, conservative STEP interference adjudication (no geometry edits)."""
from __future__ import annotations

import math
from collections import Counter

VERSION = "step-interference-filter.v1.1"


def provenance(shapes, document=None):
    """Keep unresolved identities unresolved; face IDs are local to their solid."""
    records, groups = {}, {}
    for shape in shapes:
        sid = shape['shape_id']
        body = shape.get('source_body_index')
        method = str(shape.get('mapping_method') or '').upper()
        verified = body is not None and bool(method) and 'SEQUENCE' not in method and 'FALLBACK' not in method and method != 'STABLE_SOURCE_LABEL_VOLUME_VERIFIED'
        key = f"{document}::BODY_{body}" if verified and document else None
        records[sid] = {'solid_id': sid, 'body_key': key,
                        'mapping_method': shape.get('mapping_method'),
                        'face_ids': shape.get('face_ids') or [],
                        'faces_complete': bool(shape.get('faces_complete'))}
        if key:
            groups.setdefault(key, []).append(sid)
    return {'schema_version': VERSION, 'records': records,
            'one_to_many': {k: v for k, v in groups.items() if len(v) > 1},
            'verified_solid_count': sum(bool(r['body_key']) for r in records.values()),
            'rejected_legacy_label_solid_ids': [s['shape_id'] for s in shapes
                      if s.get('mapping_method') == 'STABLE_SOURCE_LABEL_VOLUME_VERIFIED'],
            'sequence_fallback_used': False}


def classify(fact, a=None, b=None, *, micro_volume_mm3=1e-6,
             contact_tolerance_mm=1e-5):
    """Small volume is a suspicion, never proof of a conversion artifact.

    FAIL requires valid exact solids, different verified origins and affirmative
    non-design overlap evidence. Same origin is never sufficient for PASS.
    """
    a, b = a or {}, b or {}
    for value in (micro_volume_mm3, contact_tolerance_mm):
        if not math.isfinite(value) or value < 0:
            raise ValueError('Filter tolerances must be finite and non-negative')
    def result(category, status, reason):
        return {'schema_version': VERSION, 'category': category, 'status': status,
                'reason': reason, 'micro_volume_mm3': micro_volume_mm3,
                'contact_tolerance_mm': contact_tolerance_mm}
    if fact.get('surface_evidence'):
        return result('SURFACE_REVIEW','NOT_EVALUATED','SURFACE_METRICS_RECORDED_VOLUME_NOT_APPLICABLE_RULES_PENDING')
    try:
        volume = float(fact['intersection_volume_mm3'])
        gap = float(fact['minimum_distance_mm'])
    except (KeyError, ValueError, TypeError):
        return result('UNDETERMINED', 'NOT_EVALUATED', 'MISSING_EXACT_METRICS')
    if not all(math.isfinite(v) and v >= 0 for v in (volume, gap)) or fact.get('exact_brep') is not True:
        return result('UNDETERMINED', 'NOT_EVALUATED', 'INVALID_OR_NONEXACT_METRICS')
    if a.get('valid') is not True or b.get('valid') is not True:
        return result('UNDETERMINED', 'NOT_EVALUATED', 'BREP_VALIDITY_NOT_CONFIRMED')
    if a.get('solid_count') != 1 or b.get('solid_count') != 1:
        return result('UNDETERMINED', 'NOT_EVALUATED', 'REQUIRES_TWO_CLOSED_SOLIDS')
    if volume > 0 and gap > contact_tolerance_mm:
        return result('UNDETERMINED', 'NOT_EVALUATED', 'CONTRADICTORY_METRICS')
    if a.get('body_key') and a.get('body_key') == b.get('body_key'):
        return result('SAME_SOURCE_FRAGMENTATION', 'NOT_EVALUATED', 'VERIFIED_SHARED_BODY')
    connection = fact.get('connection_evidence') or {}
    if connection.get('verified') is True and fact.get('non_design_overlap_confirmed') is True:
        return result('UNDETERMINED', 'NOT_EVALUATED', 'CONFLICTING_CONNECTION_AND_PENETRATION_EVIDENCE')
    if connection.get('verified') is True and connection.get('interface_id') and connection.get('overlap_within_interface') is True:
        return result('NORMAL_PIPE_CONNECTION', 'PASS', 'VERIFIED_INTERFACE_AND_OVERLAP_BOUND')
    if volume > 0 and a.get('body_key') and b.get('body_key') and fact.get('non_design_overlap_confirmed') is True:
        return result('TRUE_PENETRATION', 'FAIL', 'VALID_EXACT_OVERLAP_DISTINCT_ORIGINS_NON_DESIGN')
    source = fact.get('source_overlap_evidence') or {}
    try:
        source_volume = float(source.get('intersection_volume_mm3', 0))
    except (TypeError, ValueError):
        source_volume = 0
    if volume > 0 and source.get('exact_brep') is True and source.get('entity_binding_verified') is True and math.isfinite(source_volume) and source_volume > 0:
        return result('UNDETERMINED', 'NOT_EVALUATED', 'OVERLAP_REPRODUCED_IN_SOURCE_INTENT_UNCONFIRMED')
    if 0 < volume <= micro_volume_mm3:
        return result('MICRO_CONVERSION_ARTIFACT', 'NOT_EVALUATED', 'SUSPECTED_ONLY_SMALL_COMMON_VOLUME')
    if volume > micro_volume_mm3:
        return result('UNDETERMINED', 'NOT_EVALUATED', 'OVERLAP_INTENT_OR_ORIGIN_UNCONFIRMED')
    if gap <= contact_tolerance_mm:
        return result('CONTACT_OR_COPLANAR', 'NOT_EVALUATED', 'NO_COMMON_VOLUME_CONTACT_REQUIRES_CONTEXT')
    return result('CLEAR', 'PASS', 'VALID_EXACT_DISJOINT_SOLIDS')


def filter_result(payload):
    """Filter a unified result in place, preserving raw OCCT facts and old status."""
    bundle = payload.get('large_single_part_analysis') or {}
    shapes = (bundle.get('batch_plan') or bundle.get('manifest') or {}).get('shapes') or []
    origins = provenance(shapes, payload.get('document'))
    by_id = {s['shape_id']: {**s, **origins['records'][s['shape_id']]} for s in shapes}
    raw = {f['issue_id']: f for f in (bundle.get('analysis') or {}).get('findings', [])}
    before = Counter(f['status'] for f in payload.get('findings') or [])
    extras = {s: max(0, n - before[s]) for s, n in (payload.get('counts') or {}).items()}
    categories, transitions = Counter(), Counter()
    for finding in payload.get('findings') or []:
        meta = finding.get('metadata') or {}
        if not meta.get('large_single_part'):
            continue
        fact = raw.get(finding['issue_id']) or {}
        decision = classify(fact, by_id.get(meta.get('geometry_object_a')),
                            by_id.get(meta.get('geometry_object_b')))
        old = meta.setdefault('pre_filter_status', finding['status'])
        meta['step_interference_filter'] = decision
        for suffix in ('a', 'b'):
            record = by_id.get(meta.get(f'geometry_object_{suffix}')) or {}
            if record.get('body_key'):
                meta[f'source_body_{suffix}'] = {
                    'source_body_index': record.get('source_body_index'),
                    'source_body_name': record.get('source_body_name'),
                    'mapping_method': record.get('mapping_method')}
            elif record.get('mapping_method') == 'STABLE_SOURCE_LABEL_VOLUME_VERIFIED':
                if meta.get(f'source_body_{suffix}'):
                    meta.setdefault(f'unverified_legacy_source_body_{suffix}', meta[f'source_body_{suffix}'])
                meta[f'source_body_{suffix}'] = None
            geometry_id = meta.get(f'geometry_object_{suffix}')
            if record.get('body_key'):
                finding[f'object_{suffix}'] = f"{record.get('source_body_name')} [Body #{record.get('source_body_index')}]"
            elif geometry_id:
                finding[f'object_{suffix}'] = geometry_id
        finding['metadata'] = meta
        finding['status'] = decision['status']
        finding['title'] = 'STEP干涉分类：' + decision['category']
        finding['message'] = '保守裁决：' + decision['reason']
        if decision['status'] != 'FAIL':
            finding['severity'] = 'S2'
        categories[decision['category']] += 1
        transitions[f"{old}->{decision['status']}"] += 1
    previous = Counter(f['status'] for f in payload.get('findings') or [])
    # Errors/deferred pairs may be counted outside findings; retain their totals.
    for status in ('PASS', 'WARN', 'FAIL', 'NOT_EVALUATED', 'EXEMPTED', 'ERROR'):
        previous.setdefault(status, 0)
    for status, count in extras.items():
        previous[status] += count
    payload['counts'] = dict(previous)
    payload.setdefault('audit', {})['step_interference_filter'] = {
        'schema_version': VERSION, 'categories': dict(categories),
        'transitions': dict(transitions), 'provenance': origins,
        'raw_analysis_preserved': True}
    if origins['rejected_legacy_label_solid_ids']:
        audit = payload['audit']
        if audit.get('body_solid_traceability') and 'legacy_body_solid_traceability' not in audit:
            audit['legacy_body_solid_traceability'] = audit['body_solid_traceability']
        unresolved = [sid for sid, r in origins['records'].items() if not r['body_key']]
        audit['body_solid_traceability'] = {
            'method': 'CONSERVATIVE_SPATIAL_PROVENANCE_LEGACY_VOLUME_LABELS_QUARANTINED',
            'solid_count': len(shapes), 'mapped_solid_count': origins['verified_solid_count'],
            'coverage_percent': round(100*origins['verified_solid_count']/max(1,len(shapes)),2),
            'unresolved_shape_ids': unresolved, 'is_complete': not unresolved,
            'one_to_many_body_groups': origins['one_to_many'], 'sequence_fallback_used': False}
    if previous['NOT_EVALUATED']:
        budget = payload.setdefault('confidence_budget', {})
        budget['is_complete'] = False
        degraded = budget.setdefault('degraded', [])
        message = 'STEP过滤层仍有待评估项，不能签发最终通过结论'
        if message not in degraded:
            degraded.append(message)
    return payload
