import argparse
import json
from pathlib import Path
from catia_checker.occt_brep import OCCTBRepModel
from catia_checker.geometry_fingerprint import compare_geometry_features
from standalone.step_pipe_semantics.grouped_finite_route import grouped_finite_route_evidence


def main():
    p=argparse.ArgumentParser(); p.add_argument('detail',type=Path); p.add_argument('topology',type=Path)
    p.add_argument('output',type=Path); a=p.parse_args()
    detail=json.loads(a.detail.read_text(encoding='utf-8'))
    topology=json.loads(a.topology.read_text(encoding='utf-8'))
    sid=detail['solid']['shape_id']; model=OCCTBRepModel(); model.load_brep(sid,a.detail.with_suffix('.brep'))
    model.solid_face_provenance(sid)
    torus_checks={f['shape_id']:compare_geometry_features(f,model.describe(f['shape_id']))
        for f in detail['faces'] if (f.get('surface_features') or {}).get('surface_type')=='TORUS'}
    eligible=[fid for fid,c in torus_checks.items() if c['compatible']]
    records=[]
    for index,seed in enumerate(topology['seeds']):
        if not seed['topology_verified']: continue
        evidence=grouped_finite_route_evidence(model,seed,eligible,sample_only_complete_boundary=True)
        records.append({'seed_index':index,'seed':seed,'finite_evidence':evidence})
    a.output.write_text(json.dumps({'records':records,'additional_torus_face_identity_checks':torus_checks},
        ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__': main()
