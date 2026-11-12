"""Point witnesses, not an exhaustive proof that an entire pair is separated."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from catia_checker.occt_brep import OCCTBRepModel
from catia_checker.occt_session_cache import atomic_json,digest
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.TopTools import TopTools_ListOfShape
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_SOLID,TopAbs_FACE,TopAbs_IN
from OCP.TopoDS import TopoDS
from OCP.BRepTools import BRepTools
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.gp import gp_Pnt,gp_Vec
from OCP.BRepClass3d import BRepClass3d_SolidClassifier
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
root=Path(sys.argv[1]).resolve();model=OCCTBRepModel()
pair_index=int(sys.argv[2]) if len(sys.argv)>2 else 3
source_review=json.loads((root/'shape-review/ten-original-pairs.json').read_text(encoding='utf-8'))['rows'][pair_index]
pair=source_review['pair'];labels=source_review['original_labels']
for key,identifier in zip(('A','B'),pair):
    paths=list((root/'occt-cache/pairs').rglob(identifier.replace('::','_')+'.brep'))
    if len(paths)!=1:raise ValueError('Cache ambiguous')
    path=paths[0]
    if digest(path)!=path.with_suffix('.sha256').read_text().strip():raise ValueError('Cache hash mismatch')
    model.load_brep(key,path)
for key,label in zip(('OA','OB'),labels):model.load_brep(key,root/f'shape-review/original-{label}/target.brep')
operation=BRepAlgoAPI_Common();args=TopTools_ListOfShape();args.Append(model._shape('A'));tools=TopTools_ListOfShape();tools.Append(model._shape('B'))
operation.SetArguments(args);operation.SetTools(tools);operation.Build()
if not operation.IsDone():raise RuntimeError('Common failed')
explorer=TopExp_Explorer(operation.Shape(),TopAbs_SOLID);rows=[]
while explorer.More():
    solid=explorer.Current();props=GProp_GProps();BRepGProp.VolumeProperties_s(solid,props,1e-8,False,False)
    point=props.CentreOfMass();states=[]
    for tolerance in (1e-7,1e-6,1e-5):
        states.append({'tolerance_mm':tolerance,'states':{key:str(BRepClass3d_SolidClassifier(shape,point,tolerance).State())
                       for key,shape in [('COMMON',solid),*[(key,model._shape(key)) for key in ('A','B','OA','OB')]]}})
    witnesses=[];tested=0;faces=TopExp_Explorer(solid,TopAbs_FACE)
    while faces.More() and len(witnesses)<3:
        face=TopoDS.Face_s(faces.Current());adaptor=BRepAdaptor_Surface(face);u0,u1,v0,v1=BRepTools.UVBounds_s(face)
        for uf in (.25,.5,.75):
            for vf in (.25,.5,.75):
                p=gp_Pnt();du=gp_Vec();dv=gp_Vec();adaptor.D1(u0+(u1-u0)*uf,v0+(v1-v0)*vf,p,du,dv)
                normal=du.Crossed(dv)
                if normal.SquareMagnitude()<1e-20:continue
                normal.Normalize()
                for offset in (-1e-5,-1e-6,-1e-7,1e-7,1e-6,1e-5):
                    sample=p.Translated(normal.Multiplied(offset));tested+=1
                    if BRepClass3d_SolidClassifier(solid,sample,1e-8).State()!=TopAbs_IN:continue
                    classifications={key:str(BRepClass3d_SolidClassifier(model._shape(key),sample,1e-7).State()) for key in ('A','B','OA','OB')}
                    witnesses.append({'point_mm':[sample.X(),sample.Y(),sample.Z()],'common_state':'IN',
                        'common_classifier_tolerance_mm':1e-8,'input_classifier_tolerance_mm':1e-7,'input_states':classifications})
                    if len(witnesses)>=3:break
                if len(witnesses)>=3:break
            if len(witnesses)>=3:break
        faces.Next()
    rows.append({'sample_basis':'ADAPTIVE_VOLUME_CENTROID_OF_COMMON_SOLID','point_mm':[point.X(),point.Y(),point.Z()],
                 'common_solid_volume_mm3':props.Mass(),'classifications':states,'surface_offset_samples_tested':tested,
                 'interior_witnesses':witnesses})
    explorer.Next()
result={'pair':pair,'rows':rows,
        'source_modified':False,'sampling_complete':False,'conversion_confirmed':False,
        'limitations':['交集重心不保证位于实体内，必须检查COMMON状态','内部采样点可证明局部穿透，但未采到不能证明不穿透',
                       '原始对照身份来自声明顺序与复制回执追踪，非工程原生身份认证']}
atomic_json(root/f'shape-review/local-penetration-pair-{pair_index:02d}.json',result)
if pair_index==3:atomic_json(root/'shape-review/local-penetration-b2s25-b25s15.json',result)
print(json.dumps({'pair':pair,'common_regions':len(rows),'witnesses':[r['interior_witnesses'] for r in rows]},ensure_ascii=False))
