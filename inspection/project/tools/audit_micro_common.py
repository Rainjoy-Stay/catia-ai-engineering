"""Local diagnostic only: tolerance sensitivity, bounds, and integral convergence."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from catia_checker.occt_brep import OCCTBRepModel
from catia_checker.occt_session_cache import atomic_json,digest
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.TopTools import TopTools_ListOfShape
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_FACE,TopAbs_SOLID
from OCP.TopoDS import TopoDS
from OCP.BRep import BRep_Tool
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.Bnd import Bnd_OBB
from OCP.BRepBndLib import BRepBndLib
root=Path(sys.argv[1]).resolve();pair=['BATCH_0002::STEP_SOLID_0025','BATCH_0025::STEP_SOLID_0015']
model=OCCTBRepModel();paths=[];tolerances=[]
for identifier,key in zip(pair,('A','B')):
    matches=list((root/'occt-cache/pairs').rglob(identifier.replace('::','_')+'.brep'))
    if len(matches)!=1:raise ValueError('Cache ambiguous')
    path=matches[0]
    if digest(path)!=path.with_suffix('.sha256').read_text().strip():raise ValueError('Cache hash mismatch')
    model.load_brep(key,path);paths.append({'path':str(path),'sha256':digest(path)})
    explorer=TopExp_Explorer(model._shape(key),TopAbs_FACE);values=[]
    while explorer.More():
        values.append(BRep_Tool.Tolerance_s(TopoDS.Face_s(explorer.Current())));explorer.Next()
    tolerances.append({'min_face_tolerance_mm':min(values),'max_face_tolerance_mm':max(values)})
rows=[]
for fuzzy in (0.0,1e-7,1e-6):
    operation=BRepAlgoAPI_Common();args=TopTools_ListOfShape();args.Append(model._shape('A'));tools=TopTools_ListOfShape();tools.Append(model._shape('B'))
    operation.SetArguments(args);operation.SetTools(tools);operation.SetFuzzyValue(fuzzy);operation.Build()
    if not operation.IsDone():raise RuntimeError('Common failed')
    common=operation.Shape();props=GProp_GProps();BRepGProp.SurfaceProperties_s(common,props)
    row={'fuzzy_mm':fuzzy,'common_valid':BRepCheck_Analyzer(common).IsValid(),'common_area_mm2':props.Mass(),'volumes':[]}
    count=0;explorer=TopExp_Explorer(common,TopAbs_SOLID)
    while explorer.More():count+=1;explorer.Next()
    row['solid_count']=count
    if count:
        obb=Bnd_OBB();BRepBndLib.AddOBB_s(common,obb,False,True,False)
        row['obb_dimensions_mm']=[2*obb.XHSize(),2*obb.YHSize(),2*obb.ZHSize()]
        row['obb_is_thickness_proof']=False
    for epsilon in (None,1e-6,1e-8):
        volume=GProp_GProps()
        if epsilon is None:BRepGProp.VolumeProperties_s(common,volume)
        else:BRepGProp.VolumeProperties_s(common,volume,float(epsilon),False,False)
        row['volumes'].append({'epsilon':epsilon,'volume_mm3':volume.Mass()})
    rows.append(row)
output={'pair':pair,'inputs':paths,'input_face_tolerances':tolerances,'rows':rows,
        'diagnostic_fuzzy_values_not_acceptance_tolerances':True,'conversion_confirmed':False,'excluded':False,'source_modified':False}
atomic_json(root/'shape-review/micro-common-b2s25-b25s15.json',output);print(json.dumps(output,ensure_ascii=False))
