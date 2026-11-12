"""Test numerical integration separately from changes to geometry."""
import json,sys,math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from catia_checker.occt_brep import OCCTBRepModel
from catia_checker.occt_session_cache import atomic_json,digest
from catia_checker.integration_stability import assess_integrations
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
root=Path(sys.argv[1]).resolve()
audit=json.loads((root/'shape-review/live-candidate-audit.json').read_text(encoding='utf-8'));rows=[]
for record in audit['rows']:
    identifier=record['shape_id']
    if identifier=='BATCH_0001::STEP_SOLID_0038':continue
    matches=list((root/'occt-cache/pairs').rglob(identifier.replace('::','_')+'.brep'))
    if len(matches)!=1:raise ValueError('Cache identity ambiguous')
    path=matches[0]
    if digest(path)!=path.with_suffix('.sha256').read_text().strip():raise ValueError('Cache hash mismatch')
    model=OCCTBRepModel();model.load_brep('A',path);shape=model._shape('A')
    source=record['live_source'];row={'shape_id':identifier,'live_source':source,'integrations':[]}
    for epsilon in (1e-4,1e-6,1e-8):
        props=GProp_GProps();error=BRepGProp.VolumeProperties_s(shape,props,float(epsilon),False,False)
        cog=props.CentreOfMass();centroid=[cog.X(),cog.Y(),cog.Z()]
        row['integrations'].append({'epsilon':epsilon,'estimated_relative_error':error,'volume_mm3':props.Mass(),
            'centroid_mm':centroid,'relative_volume_delta':abs(props.Mass()/source['volume_mm3']-1),
            'centroid_delta_mm':math.dist(centroid,source['centroid_mm'])})
    row['stability']=assess_integrations(row['integrations'])
    rows.append(row);atomic_json(root/'shape-review/adaptive-volume-audit.json',{'rows':rows,'geometry_changed':False})
    print(json.dumps({'shape_id':identifier,'integrations':row['integrations']},ensure_ascii=False),flush=True)
