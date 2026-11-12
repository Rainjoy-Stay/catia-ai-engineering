import json
from pathlib import Path


def main():
    art=Path(__file__).resolve().parents[1]/'artifacts'; directory=art/'step_full_exterior_scan'
    payload=json.loads((directory/'full_exterior_scan.json').read_text(encoding='utf-8'))
    records=payload['records']; ids=[r['solid_id'] for r in records]
    assert len(ids)==len(set(ids))==payload['solid_count']==payload['scanned_count']
    face_count=0; checked=0
    for record in records:
        if 'error' in record: continue
        detail=json.loads((directory/record['detail_file']).read_text(encoding='utf-8'))
        faces=detail['faces']; face_ids=[f['shape_id'] for f in faces]
        assert len(face_ids)==len(set(face_ids))==detail['solid']['face_count']
        assert set(face_ids)==set(detail['face_provenance']['face_ids'])
        assert detail['source_sha256']==payload['source_sha256']
        assert record['source_body_index'] is None
        assert record['candidate']['design_cavity_confirmed'] is False
        assert record['candidate']['wall_thickness_mm'] is None
        face_count+=len(faces); checked+=1
    formal=json.loads((art/'step_filter_local_evidence'/'turbine_source_evidence_filtered.json').read_text(encoding='utf-8'))
    previous=[f for f in formal['findings'] if f.get('metadata',{}).get('pre_filter_status')=='FAIL']
    assert len(previous)==23 and all(f['status']=='NOT_EVALUATED' for f in previous)
    audit={'solid_snapshots_checked':checked,'face_records_checked':face_count,
           'unique_local_face_ids_and_ownership_verified':True,
           'body_identity_not_invented':True,'cavity_or_wall_not_invented':True,
           'former_23_still_not_evaluated':True,'scope':'REGISTRATION_AND_SNAPSHOT_COMPLETENESS_NOT_DESIGN_VALIDATION'}
    (directory/'snapshot_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(audit))


if __name__=='__main__': main()
