"""Evidence gate for attribution, separate from immutable measurement facts.

AI proposals are explanations only. Certificates come from deterministic verifiers,
must match the exact pair and evidence digests, and may be revoked by the caller.
"""
import copy
import hashlib
import json
import math
from pathlib import Path

VERSION = 'interference-attribution.v1'
METHODS = {
    'DUPLICATE_EXPORT': 'TRACKED_COPY_AND_EXACT_EQUIVALENCE',
    'PLACEMENT_CHANGE': 'BOUND_SOURCE_POSE_AND_LOCAL_COMMON',
    'ADDED_GEOMETRY': 'BOUND_SOURCE_LOCAL_SYMMETRIC_DIFFERENCE',
}

def fingerprint(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False).encode()).hexdigest()

def exact_result(measurement):
    if measurement.get('state')!='COMPLETE' or measurement.get('exact_brep') is not True:
        return False
    if measurement.get('input_valid') != [True, True] or measurement.get('result_valid') is not True:
        return False
    try:
        v=float(measurement['common_volume_mm3']);d=float(measurement['distance_mm'])
        return math.isfinite(v) and math.isfinite(d) and v>=0 and d>=0 and not(v>0 and d>1e-5)
    except (KeyError,TypeError,ValueError):return False

def adjudicate(package, proposal, *, evidence_root=None, certificate=None,
               trusted_certificate_digests=(), revoked=False):
    """Never accept confidence, screenshots, names, visibility, or smallness as proof."""
    result={'schema_version':VERSION,'excluded':False,'attribution_result':'CAUSE_UNKNOWN',
        'engineering_result':'PENDING_DESIGN_REVIEW','exclusion_reasons':[],
        'proposal':copy.deepcopy(proposal),'measurement_fingerprint':fingerprint(package['measurements'])}
    if revoked:
        result['exclusion_reasons']=['EXCLUSION_REVOKED'];return result
    if not certificate:
        result['exclusion_reasons']=['NO_DETERMINISTIC_EXCLUSION_CERTIFICATE'];return result
    c=certificate
    reasons=[]
    if fingerprint(c) not in trusted_certificate_digests:
        reasons.append('CERTIFICATE_NOT_REGISTERED_BY_DETERMINISTIC_VERIFIER')
    if c.get('pair')!=package['pair'] or c.get('measurement_fingerprint')!=result['measurement_fingerprint']:
        reasons.append('CERTIFICATE_SCOPE_MISMATCH')
    if METHODS.get(c.get('kind'))!=c.get('verifier_method'):reasons.append('UNSUPPORTED_VERIFIER')
    bindings=c.get('three_layer_bindings') or []
    for side in ('a','b'):
        chain=[x for x in bindings if x.get('side')==side]
        if {x.get('transition') for x in chain}!={'STEP_TO_CATIA','CATIA_TO_EXPORT'}:
            reasons.append('THREE_LAYER_MAPPING_INCOMPLETE');continue
        for binding in chain:
            if binding.get('unique') is not True or len(set(binding.get('independent_features',[]))&
                {'position','bounds','volume_or_area','topology','local_geometry'})<3:
                reasons.append('MAPPING_NOT_CROSS_VERIFIED')
    refs=c.get('evidence') or []
    if not refs or evidence_root is None:reasons.append('MISSING_VERIFIER_EVIDENCE')
    else:
        root=Path(evidence_root).resolve()
        for ref in refs:
            path=(root/ref.get('path','')).resolve()
            if not path.is_relative_to(root) or not path.is_file():reasons.append('MISSING_VERIFIER_EVIDENCE');continue
            with path.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
            if digest!=ref.get('sha256'):reasons.append('EVIDENCE_CHANGED')
    if c.get('kind')=='DUPLICATE_EXPORT':
        if not(c.get('tracked_same_original_object') is True and c.get('independent_original_objects') is False
               and c.get('exact_equivalence_verified') is True):reasons.append('DUPLICATE_ORIGIN_NOT_PROVEN')
    else:
        source=c.get('source_pair_measurement') or {};derived=c.get('derived_pair_measurement') or {}
        if not(exact_result(source) and source['common_volume_mm3']==0 and exact_result(derived)
               and derived['common_volume_mm3']>0):reasons.append('SOURCE_ABSENCE_OR_DERIVED_PENETRATION_UNPROVEN')
        if c.get('kind')=='PLACEMENT_CHANGE' and c.get('measured_pose_delta_causes_local_overlap') is not True:
            reasons.append('POSE_CAUSALITY_UNPROVEN')
        if c.get('kind')=='ADDED_GEOMETRY' and c.get('new_geometry_contains_entire_overlap') is not True:
            reasons.append('LOCAL_GEOMETRY_CAUSALITY_UNPROVEN')
    if reasons:result['exclusion_reasons']=sorted(set(reasons));return result
    result.update(excluded=True,attribution_result='VERIFIED_CONVERSION_ARTIFACT',certificate=copy.deepcopy(c))
    return result
