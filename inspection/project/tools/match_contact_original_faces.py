"""Descriptor candidates only; no automatic identity or conversion verdict."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from catia_checker.occt_brep import OCCTBRepModel
from catia_checker.occt_session_cache import atomic_json, digest
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_FACE
from OCP.BRepBndLib import BRepBndLib
from OCP.Bnd import Bnd_Box
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps

root = Path(sys.argv[1]).resolve()
registry = json.loads((root/'registry.json').read_text(encoding='utf-8'))['objects']
model = OCCTBRepModel()
original = root/'shape-review/original-3068/target.brep'
model.load_brep('O', original)
targets = [registry[f'BATCH_0044::STEP_SHELL_{n:04d}'] for n in (10,11,12)]
ranked = [[] for _ in targets]
explorer = TopExp_Explorer(model._shape('O'), TopAbs_FACE)
index = 0
while explorer.More():
    index += 1
    face = explorer.Current()
    box = Bnd_Box(); BRepBndLib.Add_s(face, box)
    bounds = list(box.Get())
    props = GProp_GProps(); BRepGProp.SurfaceProperties_s(face, props)
    for target, candidates in zip(targets, ranked):
        expected = target['bounds_mm']['min'] + target['bounds_mm']['max']
        delta = max(abs(a-b) for a,b in zip(bounds, expected))
        area_delta = abs(props.Mass()-target['surface_area_mm2'])
        candidates.append({'face_traversal_index': index, 'max_bound_delta_mm':delta,
            'area_delta_mm2':area_delta, 'area_mm2':props.Mass()})
    explorer.Next()
result = {'original_brep_sha256':digest(original), 'original_face_count':index,
    'rows':[{'shape_id':t['shape_id'], 'nearest_descriptors':sorted(c,key=lambda x:x['max_bound_delta_mm'])[:5],
        'source_identity_verified':False} for t,c in zip(targets,ranked)],
    'source_modified':False, 'limitation':'Traversal indexes and similar descriptors are not certified source identities'}
atomic_json(root/'shape-review/contact-original-face-candidates.json',result)
print(json.dumps(result,ensure_ascii=False))
