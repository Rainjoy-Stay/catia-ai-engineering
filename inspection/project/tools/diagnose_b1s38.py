"""Read-only topology diagnostics for the flagged cached solid."""
import json,sys
from pathlib import Path
from collections import Counter
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from catia_checker.occt_brep import OCCTBRepModel
from catia_checker.occt_session_cache import atomic_json,digest
from OCP.BRepCheck import BRepCheck_Analyzer,BRepCheck_NoError
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_FACE,TopAbs_EDGE,TopAbs_WIRE,TopAbs_SHELL

root=Path(sys.argv[1]).resolve();identifier='BATCH_0001::STEP_SOLID_0038'
paths=list((root/'occt-cache'/'pairs').rglob(identifier.replace('::','_')+'.brep'))
if len(paths)!=1:raise ValueError('Ambiguous cached shape')
path=paths[0]
if digest(path)!=path.with_suffix('.sha256').read_text(encoding='ascii').strip():raise ValueError('Cache hash mismatch')
model=OCCTBRepModel();model.load_brep('A',path);shape=model._shape('A');check=BRepCheck_Analyzer(shape)
errors=[];counts={}
for label,kind in [('FACE',TopAbs_FACE),('EDGE',TopAbs_EDGE),('WIRE',TopAbs_WIRE),('SHELL',TopAbs_SHELL)]:
    explorer=TopExp_Explorer(shape,kind);index=0
    while explorer.More():
        index+=1;sub=explorer.Current();result=check.Result(sub);statuses=[]
        if result is not None:
            statuses.extend(str(s) for s in result.Status() if s!=BRepCheck_NoError)
            result.InitContextIterator()
            while result.MoreShapeInContext():
                statuses.extend(str(s) for s in result.StatusOnShape() if s!=BRepCheck_NoError)
                result.NextShapeInContext()
        if statuses:errors.append({'kind':label,'traversal_index':index,'codes':sorted(set(statuses))})
        explorer.Next()
    counts[label]=index
registry=json.loads((root/'registry.json').read_text(encoding='utf-8'));record=registry['objects'][identifier]
checkpoint=json.loads((root/'checkpoint.json').read_text(encoding='utf-8'))
related=[x for x in checkpoint['completed_pairs'] if identifier in x['pair']]
output={'shape_id':identifier,'cache_sha256':digest(path),'valid':check.IsValid(),'topology_occurrences':counts,
 'errors':errors,'error_counts':dict(Counter(code for e in errors for code in e['codes'])),
 'source_mapping':{k:record.get(k) for k in ('source_name','source_body_name','source_body_index','mapping_method')},
 'completed_related_pairs':len(related),'related_positive_volume_pairs':sum((x['fact'].get('common',{}).get('intersection_volume_mm3') or 0)>0 for x in related),
 'conversion_confirmed':False,'excluded':False,'source_modified':False}
atomic_json(root/'shape-review'/'b1s38-topology.json',output)
print(json.dumps({k:v for k,v in output.items() if k!='errors'},ensure_ascii=False))
