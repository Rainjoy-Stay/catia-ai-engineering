"""Adaptive surface mass audit; descriptor convergence is not identity proof."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from catia_checker.occt_brep import OCCTBRepModel
from catia_checker.occt_session_cache import atomic_json,digest
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
root=Path(sys.argv[1]).resolve();model=OCCTBRepModel();rows=[]
for index in (10,11,12):
    identifier=f'BATCH_0044::STEP_SHELL_{index:04d}'
    paths=list((root/'occt-cache/pairs').rglob(identifier.replace('::','_')+'.brep'))
    if len(paths)!=1:raise ValueError('Ambiguous cache')
    path=paths[0]
    if digest(path)!=path.with_suffix('.sha256').read_text().strip():raise ValueError('Cache changed')
    model.load_brep('S',path);samples=[]
    for epsilon in (1e-4,1e-6,1e-8):
        props=GProp_GProps();error=BRepGProp.SurfaceProperties_s(model._shape('S'),props,epsilon,False)
        cog=props.CentreOfMass()
        sample={'epsilon':epsilon,'estimated_relative_area_error':error,'area_mm2':props.Mass(),
            'centroid_mm':[cog.X(),cog.Y(),cog.Z()]}
        samples.append(sample);print(json.dumps({'shape_id':identifier,**sample}),flush=True)
    rows.append({'shape_id':identifier,'brep_sha256':digest(path),'samples':samples,
        'source_identity_verified':False})
atomic_json(root/'shape-review/contact-adaptive-surface-integration.json',{'rows':rows,
    'source_modified':False,'limitation':'Integration convergence does not prove shape identity'})
