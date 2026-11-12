"""Localize imported BREP defects without repairing or editing any shape."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from catia_checker.occt_brep import OCCTBRepModel
from catia_checker.occt_session_cache import atomic_json,digest
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_FACE,TopAbs_WIRE,TopAbs_SOLID
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepBndLib import BRepBndLib
from OCP.Bnd import Bnd_Box
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.TopoDS import TopoDS

root=Path(sys.argv[1]).resolve();review=root/'shape-review';model=OCCTBRepModel();rows=[]
def shapes(shape,kind):
    explorer=TopExp_Explorer(shape,kind);items=[]
    while explorer.More():items.append(explorer.Current());explorer.Next()
    return items
def bounds(shape):
    box=Bnd_Box();BRepBndLib.Add_s(shape,box,False)
    values=box.Get();return {'min':list(values[:3]),'max':list(values[3:])}
for label in (3066,38522):
    directory=review/f'original-{label}';path=directory/'target.brep'
    audit=json.loads((directory/'audit.json').read_text(encoding='utf-8'));model.load_brep('S',path);shape=model._shape('S')
    solids=shapes(shape,TopAbs_SOLID);components=[{'index':i,'valid':BRepCheck_Analyzer(s).IsValid(),
        'face_count':len(shapes(s,TopAbs_FACE)),'bounds_mm':bounds(s)} for i,s in enumerate(solids,1)]
    lookup={'FACE':shapes(shape,TopAbs_FACE),'WIRE':shapes(shape,TopAbs_WIRE)};defects=[]
    for error in audit['errors']:
        subshape=lookup[error['kind']][error['traversal_index']-1]
        owners=[i for i,s in enumerate(solids,1) if any(subshape.IsSame(c) for c in shapes(s,TopAbs_FACE if error['kind']=='FACE' else TopAbs_WIRE))]
        row={**error,'bounds_mm':bounds(subshape),'owner_solid_indices':owners}
        if error['kind']=='FACE':row['surface_type']=str(BRepAdaptor_Surface(TopoDS.Face_s(subshape)).GetType())
        defects.append(row)
    rows.append({'label':label,'brep_sha256':digest(path),'components':components,'defects':defects})
result={'rows':rows,'source_modified':False,'geometry_repaired':False,
    'limitation':'Localized defects in OCCT-transferred geometry are not proof of intrinsic raw STEP invalidity'}
atomic_json(review/'original-major-defect-localization.json',result);print(json.dumps(result,ensure_ascii=True))
