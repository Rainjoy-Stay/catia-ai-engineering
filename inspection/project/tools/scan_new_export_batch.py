"""Explicit single-Body STEP -> all Solid -> Face provenance, exterior only."""
import concurrent.futures
from collections import Counter
import json
import subprocess
import sys
from pathlib import Path
from tools.review_surface_recovery_pilot import digest

PROJECT_ROOT=Path(__file__).resolve().parents[1]

def bend_finding(candidate,body_index):
    if candidate.get('centerline_bend_radius_mm') is None or candidate.get('outer_diameter_mm') is None:
        return None
    from catia_checker.routing_rules import evaluate_bend_radius
    rules=json.loads((PROJECT_ROOT/'config'/'rules-active.json').read_text(encoding='utf-8'))
    route={'name':f'STEP_BODY_{body_index:06d}',
           'diameter_mm':candidate['outer_diameter_mm'],
           'bend_radii_mm':[candidate['centerline_bend_radius_mm']],
           'measurement_source':'OCCT_EXACT_BREP_BSPLINE_CENTERLINE',
           'pipe_semantics_confirmed':False}
    return evaluate_bend_radius(route,rules).to_dict()

def worker(step,body_index,output):
    from OCP.STEPControl import STEPControl_Reader
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.TopAbs import TopAbs_SOLID
    from catia_checker.occt_brep import OCCTBRepModel,_subshapes
    from standalone.step_pipe_semantics.exterior import exterior_candidate
    before=digest(step); reader=STEPControl_Reader()
    if reader.ReadFile(str(step))!=IFSelect_RetDone: raise RuntimeError('STEP read failed')
    if not reader.TransferRoots():
        assert digest(step)==before
        output.write_text(json.dumps({'geometry_source':'CATIA_NEW_SINGLE_BODY_EXPORT_NOT_ORIGINAL_STEP',
            'source_body_index':body_index,'source_step_file':str(step),'source_step_sha256':before,
            'solid_count':None,'body_split_into_multiple_solids':False,'status':'NOT_EVALUATED',
            'geometry_transfer_status':'NOT_EVALUATED','transferable_root_count':reader.NbRootsForTransfer(),
            'reason':'STEP_ROOT_TRANSFER_PRODUCED_NO_GEOMETRY_NOT_PROOF_OF_EMPTY_BODY','records':[]},
            ensure_ascii=False,indent=2),encoding='utf-8')
        return
    solids=_subshapes(reader.OneShape(),TopAbs_SOLID); model=OCCTBRepModel(); records=[]
    for index,shape in enumerate(solids,1):
        sid=f'NEW_BODY_{body_index:06d}::SOLID_{index:04d}'; model.register_shape(sid,shape)
        solid=model.describe(sid); provenance=model.solid_face_provenance(sid)
        faces=[model.describe(fid) for fid in provenance['face_ids']]
        cache=output.with_name(f'BODY_{body_index:06d}_SOLID_{index:04d}.brep'); model.write_brep(sid,cache)
        candidate=exterior_candidate(solid,faces,shape=shape)
        records.append({'solid':solid,'face_provenance':provenance,'faces':faces,
            'candidate':candidate,'bend_radius_rule_finding':bend_finding(candidate,body_index),
            'cache_file':str(cache),'cache_sha256':digest(cache)})
    assert digest(step)==before
    result={'geometry_source':'CATIA_NEW_SINGLE_BODY_EXPORT_NOT_ORIGINAL_STEP','source_body_index':body_index,
        'source_step_file':str(step),'source_step_sha256':before,'solid_count':len(solids),
        'body_split_into_multiple_solids':len(solids)>1,'status':'NOT_EVALUATED','records':records}
    if not solids:
        from OCP.TopExp import TopExp
        from OCP.TopTools import TopTools_IndexedMapOfShape
        from catia_checker.brep_validity_evidence import validity_evidence
        root=f'NEW_BODY_{body_index:06d}::EXPORT_ROOT'; shape=reader.OneShape(); model.register_shape(root,shape)
        root_cache=output.with_name(f'BODY_{body_index:06d}_ROOT.brep'); model.write_brep(root,root_cache)
        inventory=TopTools_IndexedMapOfShape(); TopExp.MapShapes_s(shape,inventory)
        counts=Counter(str(inventory.FindKey(i).ShapeType()).split('.')[-1] for i in range(1,inventory.Extent()+1))
        result['non_solid_geometry']={'shape_id':root,'status':'NOT_EVALUATED','root_shape_type':str(shape.ShapeType()),
            'unique_subshape_counts':dict(counts),'face_count':counts.get('TopAbs_FACE',0),
            'cache_file':str(root_cache),'cache_sha256':digest(root_cache),'root_volume_mm3':None,
            'solid_interference_evaluation':'NOT_EVALUATED','validity':validity_evidence(shape,root),
            'design_cavity_confirmed':False,'engineering_pipe_confirmed':False}
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')

def main():
    if len(sys.argv)==4: worker(Path(sys.argv[1]),int(sys.argv[2]),Path(sys.argv[3])); return
    audit_path=Path(sys.argv[1]); audit=json.loads(audit_path.read_text(encoding='utf-8'))
    out=audit_path.parent.parent/'exterior_scan'; out.mkdir(exist_ok=True); tasks=[]
    for file in audit['batch_files']:
        step=Path(file); mappings=[r for r in audit['body_mapping']
            if (r.get('source_step_file')==str(step) if 'source_step_file' in r else r['batch_id']==step.stem)]
        assert len(mappings)==1,'Only explicit one-Body-per-file export is supported'
        tasks.append((step,int(mappings[0]['source_body_index'])))
    def run(task):
        step,index=task; target=out/f'BODY_{index:06d}.json'
        try:
            p=subprocess.run([sys.executable,__file__,str(step),str(index),str(target)],capture_output=True,text=True,timeout=45)
            if p.returncode: raise RuntimeError(f'EXIT_{p.returncode}: {p.stderr[-500:]}')
            return json.loads(target.read_text(encoding='utf-8'))
        except Exception as exc: return {'source_body_index':index,'status':'NOT_EVALUATED','error':str(exc),'records':[]}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool: records=list(pool.map(run,tasks))
    kinds={}
    for r in records:
        for solid in r['records']:
            kind=solid['candidate']['geometry_kind']; kinds[kind]=kinds.get(kind,0)+1
    summary={'status':'NOT_EVALUATED','geometry_source':'CATIA_NEW_IMPORT_EXPORT_SEPARATE_BASELINE',
        'body_count':len(tasks),'worker_errors':sum('error' in r for r in records),'geometry_counts':kinds,
        'split_body_indices':[r['source_body_index'] for r in records if r.get('body_split_into_multiple_solids')],
        'zero_solid_body_indices':[r['source_body_index'] for r in records if r.get('solid_count')==0],
        'engineering_pipe_confirmed':False,'design_cavity_confirmed':False,'records':records}
    (out/'batch_exterior_scan.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k!='records'},ensure_ascii=False))

if __name__=='__main__': main()
