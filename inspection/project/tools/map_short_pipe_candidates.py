"""Spatial matches are diagnostic; unverified Body provenance stays unverified."""
import json
from pathlib import Path
from catia_checker.geometry_fingerprint import match_geometry_records, compare_geometry_features
from standalone.step_interference_filter import provenance


def main():
    artifacts=Path(__file__).resolve().parents[1]/'artifacts'
    directory=artifacts/'step_pipe_full_discovery'
    payload=json.loads((artifacts/'step_filter_local_evidence'/'turbine_source_evidence_filtered.json').read_text(encoding='utf-8'))
    shapes=payload['large_single_part_analysis']['batch_plan']['shapes']
    origins=provenance(shapes,payload['document'])['records']
    sources=[json.loads(p.read_text(encoding='utf-8'))['solid'] for p in sorted(directory.glob('SOURCE_SOLID_*.json'))]
    result=match_geometry_records(sources,shapes,target_id='shape_id')
    result['nearest_diagnostics']=[{'source_id':s['shape_id'],'nearest':sorted(
        ({'target_id':t['shape_id'],**compare_geometry_features(s,t)} for t in shapes),
        key=lambda item:item['score'])[:3]} for s in sources]
    for match in result['matches']:
        record=next(s for s in shapes if s['shape_id']==match['target_id'])
        origin=origins[match['target_id']]
        match['verified_body_key']=origin['body_key']
        match['source_body_index']=record.get('source_body_index') if origin['body_key'] else None
        match['unverified_legacy_body_index']=record.get('source_body_index') if not origin['body_key'] else None
    result.pop('target_records')
    result['engineering_pipe_confirmed']=False
    result['limits']='A unique STEP-to-batch shape match does not validate legacy label-only Body mapping'
    (directory/'short_candidate_spatial_mapping.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__': main()
