"""Find strict interior witnesses for one valid original pair; not engineering acceptance."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from catia_checker.occt_brep import OCCTBRepModel
from catia_checker.occt_session_cache import atomic_json,digest
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepClass3d import BRepClass3d_SolidClassifier
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_SOLID,TopAbs_IN
root=Path(sys.argv[1]).resolve();review=root/'shape-review';model=OCCTBRepModel()
triage=json.loads((review/'original-retry-triage.json').read_text(encoding='utf-8'))
targets=[r for r in triage['rows'] if r['category']=='VALID_SOLID_OVERLAP_NEEDS_WITNESS']
if len(targets)!=1:raise ValueError('Expected exactly one current valid overlap')
target=targets[0];hashes=[]
for key,label in zip(('A','B'),target['original_labels']):
    path=review/f'original-{label}/target.brep';hashes.append(digest(path));model.load_brep(key,path)
shapes=[model._shape(k) for k in ('A','B')]
if not all(BRepCheck_Analyzer(s).IsValid() for s in shapes):raise ValueError('Invalid input')
operation=BRepAlgoAPI_Common(*shapes)
if not operation.IsDone() or not BRepCheck_Analyzer(operation.Shape()).IsValid():raise ValueError('Invalid common')
explorer=TopExp_Explorer(operation.Shape(),TopAbs_SOLID);rows=[]
while explorer.More():
    solid=explorer.Current();props=GProp_GProps();BRepGProp.VolumeProperties_s(solid,props,1e-8,False,False)
    point=props.CentreOfMass();states={key:str(BRepClass3d_SolidClassifier(shape,point,1e-7).State())
        for key,shape in [('COMMON',solid),('A',shapes[0]),('B',shapes[1])]}
    rows.append({'point_mm':[point.X(),point.Y(),point.Z()],'states':states,
        'strict_internal_witness':all(v.endswith('TopAbs_IN') for v in states.values()),
        'adaptive_volume_mm3':props.Mass(),'classifier_tolerance_mm':1e-7})
    explorer.Next()
result={'pair':target['pair'],'original_labels':target['original_labels'],'original_brep_sha256':hashes,
    'rows':rows,'strict_internal_witness_count':sum(r['strict_internal_witness'] for r in rows),
    'source_modified':False,'screen_pass':False,'formal_engineering_acceptance':False,
    'limitation':'Interior witnesses establish local overlap, not whether a designed fit permits it'}
atomic_json(review/'original-valid-overlap-witness.json',result);print(json.dumps(result,ensure_ascii=True))
