"""Transfer only STEP entity #3067; do not transfer all roots or alter CATIA."""
import json,sys,re
from pathlib import Path
from collections import Counter
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from catia_checker.occt_session_cache import atomic_json,digest
from catia_checker.occt_brep import OCCTBRepModel
from OCP.STEPControl import STEPControl_Reader
from OCP.IFSelect import IFSelect_RetDone
from OCP.BRepCheck import BRepCheck_Analyzer,BRepCheck_NoError
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_FACE,TopAbs_EDGE,TopAbs_WIRE,TopAbs_SHELL
root=Path(sys.argv[1]).resolve();source=Path('F:/涡轮发动机_爱给网_aigei_com/涡轮发动机.stp')
target_label=int(sys.argv[2]) if len(sys.argv)>2 else 3067
output=root/'shape-review'/f'original-{target_label}';output.mkdir(exist_ok=True)
print('READ_ORIGINAL_STEP',flush=True);reader=STEPControl_Reader()
if reader.ReadFile(str(source))!=IFSelect_RetDone:raise RuntimeError('STEP read failed')
data=reader.StepModel();entity=None
print(json.dumps({'stage':'STEP_MODEL_READ','entity_count':data.NbEntities()},ensure_ascii=False),flush=True)
labels=[];breps=[]
for index in range(1,min(12,data.NbEntities())+1):
    candidate=data.Value(index)
    ident=data.IdentLabel(candidate)
    label=data.StringLabel(candidate).ToCString()
    if index<=12:labels.append({'index':index,'ident':ident,'label':label,'type':candidate.DynamicType().Name()})
atomic_json(output/'reader-label-diagnostic.json',{'entity_count':data.NbEntities(),'first_entities':labels,'target_found':False})
print(json.dumps({'first_entities':labels},ensure_ascii=False),flush=True)
source_records=re.findall(r'^\s*#(\d+)\s*=\s*([A-Z_]+|\()',source.read_text(encoding='utf-8',errors='strict'),re.MULTILINE)
if len(source_records)!=data.NbEntities():raise RuntimeError('Source/model entity cardinality differs; ordinal fallback prohibited')
target_index=next((i for i,(label,kind) in enumerate(source_records,1) if label==str(target_label)),0)
if target_index:
    entity=data.Value(target_index)
    # The reader discarded numeric labels; source declaration order is a trace,
    # not a certified entity association. Verify nearby declaration types.
    neighbors=[]
    for i in range(target_index-2,target_index+3):
        label,kind=source_records[i-1];actual=data.Value(i).DynamicType().Name()
        normalized=actual.split('_',1)[1].replace('_','').lower()
        if kind.replace('_','').lower()!=normalized:raise RuntimeError('Reader/source declaration order mismatch')
        neighbors.append({'index':i,'source_label':label,'source_type':kind,'reader_type':actual})
    print(json.dumps({'ordinal_trace':neighbors,'target_index':target_index},ensure_ascii=False),flush=True)
atomic_json(output/'reader-label-diagnostic.json',{'entity_count':data.NbEntities(),'first_entities':labels,
    'original_numeric_labels_retained':False,'ordinal_trace':neighbors if target_index else [],
    'target_index':target_index,'target_found':entity is not None,'identity_certified':False})
if entity is None:raise RuntimeError('Exact STEP entity #3067 unresolved; see reader-label-diagnostic.json')
entity_type=entity.DynamicType().Name()
if not any(kind in entity_type for kind in ('BrepWithVoids','ManifoldSolidBrep')):raise RuntimeError('Unexpected entity type '+entity_type)
print(f'TRANSFER_ENTITY_{target_label}_ONLY',flush=True)
from OCP.StepRepr import StepRepr_HArray1OfRepresentationItem
representation=data.Value(4)
if representation.DynamicType().Name()!='StepShape_AdvancedBrepShapeRepresentation':raise RuntimeError('Unexpected representation context')
membership=[data.Number(representation.ItemsValue(i)) for i in range(1,representation.NbItems()+1)]
print(json.dumps({'target_model_number':data.Number(entity),'representation_items':membership[:12],
    'item_count':representation.NbItems(),'target_void_count':entity.NbVoids() if hasattr(entity,'NbVoids') else None},ensure_ascii=False),flush=True)
print('TRANSFER_ONE_BY_NATIVE_MODEL_INDEX',flush=True)
# Number(Value(index)) returns zero in this binding build. Use the native
# integer-index API to avoid round-tripping copied transient wrappers.
if not reader.TransferOne(target_index):
    atomic_json(output/'transfer-status.json',{'status':'TARGET_TRANSFER_FAILED','target_index':target_index,
        'source_label':target_label,'identity_basis':'DECLARATION_ORDER_WITH_NEIGHBOR_TYPE_CHECKS',
        'source_intrinsic_invalidity_proven':False,'all_roots_transferred':False,'source_modified':False})
    raise RuntimeError('Targeted transfer failed; requires transfer-context investigation')
shape=reader.OneShape()
if shape.IsNull():raise RuntimeError('No target BREP')
model=OCCTBRepModel();record=model.register_shape(f'ORIGINAL_{target_label}',shape);model.write_brep(f'ORIGINAL_{target_label}',output/'target.brep')
print('CHECK_ORIGINAL_TOPOLOGY',flush=True);check=BRepCheck_Analyzer(shape);errors=[];counts={}
for label,kind in [('FACE',TopAbs_FACE),('EDGE',TopAbs_EDGE),('WIRE',TopAbs_WIRE),('SHELL',TopAbs_SHELL)]:
    explorer=TopExp_Explorer(shape,kind);index=0
    while explorer.More():
        index+=1;result=check.Result(explorer.Current());codes=[]
        if result is not None:
            codes.extend(str(s) for s in result.Status() if s!=BRepCheck_NoError);result.InitContextIterator()
            while result.MoreShapeInContext():
                codes.extend(str(s) for s in result.StatusOnShape() if s!=BRepCheck_NoError);result.NextShapeInContext()
        if codes:errors.append({'kind':label,'traversal_index':index,'codes':sorted(set(codes))})
        explorer.Next()
    counts[label]=index
result={'source_file':str(source),'source_sha256':digest(source),'step_entity':target_label,'step_entity_type':entity_type,
 'record':record,'valid':check.IsValid(),'topology_occurrences':counts,'errors':errors,
 'error_counts':dict(Counter(c for e in errors for c in e['codes'])),
 'basis':'ORIGINAL_STEP_TRANSFERRED_BY_OCCT','actual_target_label':target_label,'raw_step_intrinsic_validity_proven':False,
 'source_modified':False,'all_roots_transferred':False,
 'transfer_scope':'NATIVE_TRANSFER_ONE_MODEL_INDEX',
 'entity_identity_basis':'DECLARATION_ORDER_WITH_CARDINALITY_AND_NEIGHBOR_TYPE_CHECKS'}
atomic_json(output/'audit.json',result)
print(json.dumps({k:v for k,v in result.items() if k not in ('record','errors')},ensure_ascii=False),flush=True)
