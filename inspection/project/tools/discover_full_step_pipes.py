"""Read-only all-solid discovery; traversal IDs never imply CATIA Body identity."""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from OCP.STEPControl import STEPControl_Reader
from OCP.IFSelect import IFSelect_RetDone
from OCP.TopAbs import TopAbs_SOLID
from catia_checker.occt_brep import OCCTBRepModel, _subshapes
from standalone.step_pipe_semantics import VERSION, straight_candidate, bend_candidate, connection_candidates


def main():
    p=argparse.ArgumentParser(); p.add_argument('source',type=Path)
    p.add_argument('output',type=Path); a=p.parse_args(); a.output.mkdir(parents=True,exist_ok=True)
    formal=Path(__file__).resolve().parents[1]/'artifacts'/'step_filter_local_evidence'/'turbine_source_evidence_filtered.json'
    formal_hash=hashlib.sha256(formal.read_bytes()).hexdigest()
    source_hash=hashlib.sha256(a.source.read_bytes()).hexdigest()
    reader=STEPControl_Reader()
    if reader.ReadFile(str(a.source.resolve()))!=IFSelect_RetDone: raise RuntimeError('STEP read failed')
    print('STEP read complete',flush=True)
    if reader.TransferRoots()<=0: raise RuntimeError('STEP transfer failed')
    shapes=_subshapes(reader.OneShape(),TopAbs_SOLID)
    print('STEP transfer complete; solids:',len(shapes),flush=True)
    records=[]; candidates=[]; surface_totals=Counter()
    for index,shape in enumerate(shapes,1):
        sid=f'SOURCE_SOLID_{index:04d}'
        record={'solid_id':sid,'source_body_index':None,'source_entity_id':None,
                'identity_method':'FILE_SHA256_LOCAL_OCCT_REGISTRATION_ONLY',
                'source_sha256':source_hash,'status':'NOT_EVALUATED'}
        try:
            model=OCCTBRepModel(); solid=model.register_shape(sid,shape)
            ledger=model.solid_face_provenance(sid)
            faces=[model.describe(f) for f in ledger['face_ids']]
            types=dict(Counter((f.get('surface_features') or {}).get('surface_type','UNKNOWN') for f in faces))
            surface_totals.update(types)
            straight=straight_candidate(solid,faces); bend=bend_candidate(solid,faces)
            candidate=straight if straight['geometry_kind']!='UNDETERMINED' else bend
            opening_seeds=[]
            for face in faces:
                feature=face.get('surface_features') or {}
                for boundary in feature.get('circular_inner_boundaries') or []:
                    if boundary.get('closed') is True and boundary.get('exact_brep') is True:
                        opening_seeds.append({'face_id':face['shape_id'],**boundary})
            complex_seed=(candidate['geometry_kind']=='UNDETERMINED' and solid['valid'] is True
                          and len(opening_seeds)>=2 and types.get('CYLINDER',0)>=2)
            record.update({'candidate':candidate,'surface_type_counts':types,
                'opening_seeds':opening_seeds,'complex_review_seed':complex_seed,
                'face_count':solid['face_count'],'valid':solid['valid'],
                'bounds_mm':solid['bounds_mm'],'centroid_mm':solid['centroid_mm'],
                'recognition_reasons':{'straight':straight['reason'],'bend':bend['reason']}})
            if candidate['geometry_kind']!='UNDETERMINED' or complex_seed:
                if candidate['geometry_kind']!='UNDETERMINED': candidates.append(candidate)
                model.write_brep(sid,a.output/(sid+'.brep'))
                (a.output/(sid+'.json')).write_text(json.dumps({'solid':solid,'faces':faces,
                    'face_provenance':ledger,'candidate':candidate,'opening_seeds':opening_seeds,
                    'complex_review_seed':complex_seed},ensure_ascii=False,indent=2),encoding='utf-8')
        except Exception as error:
            record['error']=type(error).__name__+': '+str(error)
        records.append(record)
        if index%50==0:
            (a.output/'discovery_checkpoint.json').write_text(json.dumps(records,ensure_ascii=False),encoding='utf-8')
            print('Scanned',index,'of',len(shapes),'candidates',len(candidates),flush=True)
    unchanged=hashlib.sha256(formal.read_bytes()).hexdigest()==formal_hash
    source_unchanged=hashlib.sha256(a.source.read_bytes()).hexdigest()==source_hash
    if not unchanged or not source_unchanged: raise RuntimeError('Read-only hash audit failed')
    connections=connection_candidates(candidates)
    result={'schema_version':VERSION,'source_file':str(a.source.resolve()),'source_sha256':source_hash,
        'scope':'ALL_OCCT_TRANSFERRED_SOLIDS_IN_ORIGINAL_STEP','solid_count':len(shapes),
        'scanned_count':len(records),'error_count':sum('error' in r for r in records),
        'geometry_counts':dict(Counter(r.get('candidate',{}).get('geometry_kind','ERROR') for r in records)),
        'surface_type_totals':dict(surface_totals),'connection_candidate_count':len(connections),
        'complex_review_seed_count':sum(r.get('complex_review_seed',False) for r in records),
        'source_unchanged':source_unchanged,'interference_result_unchanged':unchanged,
        'catia_body_identity_verified':False,'engineering_pipe_confirmed':False,
        'records':records,'connections':connections}
    (a.output/'full_step_pipe_discovery.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('records','connections')},ensure_ascii=False),flush=True)


if __name__=='__main__': main()
