"""Compare area integration and shared topology without changing geometry."""
import sys,json
from pathlib import Path
from time import perf_counter
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from catia_checker.occt_brep import OCCTBRepModel
from catia_checker.occt_session_cache import atomic_json,digest
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.TopExp import TopExp,TopExp_Explorer
from OCP.TopAbs import TopAbs_FACE,TopAbs_SHELL
from OCP.TopTools import TopTools_IndexedMapOfShape
root=Path(sys.argv[1]).resolve();paths=list((root/'occt-cache'/'pairs').rglob('BATCH_0001_STEP_SOLID_0038.brep'))
if len(paths)!=1:raise ValueError('Cache ambiguity')
path=paths[0]
if digest(path)!=path.with_suffix('.sha256').read_text(encoding='ascii').strip():raise ValueError('Cache mismatch')
model=OCCTBRepModel();model.load_brep('A',path);shape=model._shape('A');mapping=TopTools_IndexedMapOfShape();TopExp.MapShapes_s(shape,TopAbs_FACE,mapping)
output={'unique_faces':mapping.Extent(),'area_tests':[],'shells':[],'source_modified':False}
target=root/'shape-review'/'b1s38-area-audit.json'
for eps,shared in [(None,False),(None,True),(1e-4,True),(1e-6,True)]:
    props=GProp_GProps();started=perf_counter()
    if eps is None:BRepGProp.SurfaceProperties_s(shape,props,shared,False);error=None
    else:error=BRepGProp.SurfaceProperties_s(shape,props,eps,shared)
    row={'eps':eps,'skip_shared':shared,'area_mm2':props.Mass(),'reported_integration_error':error,'elapsed_seconds':perf_counter()-started}
    output['area_tests'].append(row);atomic_json(target,output);print(json.dumps(row),flush=True)
exp=TopExp_Explorer(shape,TopAbs_SHELL)
while exp.More():
    shell=exp.Current();props=GProp_GProps();BRepGProp.SurfaceProperties_s(shell,props,True,False)
    faces=TopTools_IndexedMapOfShape();TopExp.MapShapes_s(shell,TopAbs_FACE,faces)
    output['shells'].append({'index':len(output['shells'])+1,'orientation':str(shell.Orientation()),'unique_faces':faces.Extent(),'area_default_mm2':props.Mass()});exp.Next()
atomic_json(target,output)
