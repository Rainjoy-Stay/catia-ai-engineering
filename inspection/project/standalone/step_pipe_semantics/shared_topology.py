"""Shared boundary evidence requires independently replayed Face identity."""
from OCP.TopAbs import TopAbs_EDGE
from catia_checker.occt_brep import _subshapes
from catia_checker.geometry_fingerprint import compare_geometry_features


def verify_seed_topology(model,seeds,saved_faces):
    saved={f['shape_id']:f for f in saved_faces}
    referenced={s['torus_face_id'] for s in seeds}
    referenced.update(fid for s in seeds for fid in s['cylinder_face_ids'])
    identities={}; edges={}
    for fid in sorted(referenced):
        current=model.describe(fid)
        comparison=compare_geometry_features(saved[fid],current)
        identities[fid]=comparison
        if comparison['compatible']: edges[fid]=_subshapes(model._shape(fid),TopAbs_EDGE)
    results=[]
    for seed in seeds:
        result={**seed,'topology_verified':False,'shared_edge_cylinder_face_ids':[],
                'topology_method':'OCCT_SHARED_EDGE_IDENTITY_WITH_VERIFIED_FACE_REPLAY'}
        ids=[seed['torus_face_id'],*seed['cylinder_face_ids']]
        if not all(identities[fid]['compatible'] for fid in ids):
            result['reason']='FACE_CACHE_IDENTITY_UNCONFIRMED'
        else:
            adjacent=[fid for fid in seed['cylinder_face_ids']
                      if any(a.IsSame(b) for a in edges[fid] for b in edges[seed['torus_face_id']])]
            result['shared_edge_cylinder_face_ids']=adjacent
            result['topology_verified']=bool(adjacent)
            result['reason']='SHARED_EDGE_CONFIRMED' if adjacent else 'SUPPORT_TANGENCY_WITHOUT_SHARED_EDGE'
        results.append(result)
    return {'seeds':results,'face_identity_checks':identities}
