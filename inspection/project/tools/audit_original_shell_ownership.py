"""Read-only audit of raw STEP void shell ownership; no repairs or PASS claims."""
import json,re,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from catia_checker.occt_session_cache import atomic_json,digest
from OCP.STEPControl import STEPControl_Reader
from OCP.IFSelect import IFSelect_RetDone
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_SOLID,TopAbs_SHELL,TopAbs_FACE
from OCP.BRepCheck import BRepCheck_Analyzer

root=Path(sys.argv[1]).resolve();source=Path('F:/涡轮发动机_爱给网_aigei_com/涡轮发动机.stp')
before=digest(source);raw=source.read_text(encoding='utf-8')
records=re.findall(r'^\s*#(\d+)\s*=\s*([A-Z_]+|\()',raw,re.M)
index_by_label={int(label):i for i,(label,_) in enumerate(records,1)}
declarations={int(label):body for label,body in re.findall(r'^\s*#(\d+)\s*=\s*(.*?);',raw,re.M|re.S)}
reader=STEPControl_Reader()
if reader.ReadFile(str(source))!=IFSelect_RetDone:raise RuntimeError('Read failed')
data=reader.StepModel()
if len(records)!=data.NbEntities():raise RuntimeError('Cardinality mismatch')
def transfer(label):
    index=index_by_label[label]
    for i in range(max(1,index-2),min(len(records),index+2)+1):
        kind=records[i-1][1];actual=data.Value(i).DynamicType().Name().split('_',1)[1]
        if kind!='(' and kind.replace('_','').lower()!=actual.replace('_','').lower():raise RuntimeError('Ordinal mismatch')
    reader.ClearShapes()
    if not reader.TransferOne(index):raise RuntimeError(f'Transfer failed #{label}')
    return reader.OneShape()
def children(shape,kind):
    e=TopExp_Explorer(shape,kind);rows=[]
    while e.More():rows.append(e.Current());e.Next()
    return rows
whole=transfer(3066);solids=children(whole,TopAbs_SOLID)
whole_shells=[children(s,TopAbs_SHELL) for s in solids]
rows=[]
for label in [39930,*range(3073,3082)]:
    declaration=declarations[label];refs=[int(n) for n in re.findall(r'#(\d+)',declaration)]
    shell_label=refs[-1] if declaration.startswith('ORIENTED_CLOSED_SHELL') else label
    shape=transfer(label);faces=children(shape,TopAbs_FACE)
    shells=children(shape,TopAbs_SHELL)
    owners=[i for i,s in enumerate(solids,1) if any(face.IsSame(f) for face in faces for f in children(s,TopAbs_FACE))]
    exact_shell_owners=[i for i,ss in enumerate(whole_shells,1) if any(a.IsSame(b) for a in shells for b in ss)]
    row={'source_label':label,'declaration':declaration,'closed_shell_label':shell_label,
         'raw_face_reference_count':len(re.findall(r'#\d+',declarations[shell_label])),
         'face_occurrences':len(faces),'shell_occurrences':len(shells),'valid':BRepCheck_Analyzer(shape).IsValid(),
         'orientation':str(shape.Orientation()),'shared_face_owner_solids':owners,'same_shell_owner_solids':exact_shell_owners}
    rows.append(row);print(json.dumps(row),flush=True)
after=digest(source)
if before!=after:raise RuntimeError('Source changed during audit')
result={'source_sha256':before,'source_modified':False,'geometry_repaired':False,'screen_pass':False,
        'whole_solid_count':len(solids),'whole_shell_count':sum(map(len,whole_shells)),
        'whole_solid_face_counts':[len(children(s,TopAbs_FACE)) for s in solids],'rows':rows,
        'identity_basis':'DECLARATION_ORDER_WITH_CARDINALITY_AND_NEIGHBOR_TYPE_CHECKS',
        'limitation':'Shared topology ownership describes OCCT transfer, not certified material/cavity semantics.'}
atomic_json(root/'shape-review'/'original-shell-ownership.json',result)
