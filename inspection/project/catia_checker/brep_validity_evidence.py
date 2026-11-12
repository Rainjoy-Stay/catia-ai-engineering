"""Read-only OCCT validity diagnostics; no healing or engineering disposition."""
from OCP.BRepCheck import BRepCheck_Analyzer,BRepCheck_NoError
from OCP.TopExp import TopExp
from OCP.TopTools import TopTools_IndexedMapOfShape

def validity_evidence(shape,solid_id):
    analyzer=BRepCheck_Analyzer(shape); shapes=TopTools_IndexedMapOfShape(); TopExp.MapShapes_s(shape,shapes)
    issues=[]; errors=[]
    def codes(statuses): return [str(s).split('.')[-1] for s in statuses if s!=BRepCheck_NoError]
    for index in range(1,shapes.Extent()+1):
        subshape=shapes.FindKey(index)
        try:
            result=analyzer.Result(subshape)
            if result is None: continue
            own=codes(result.Status()); contexts=[]
            result.InitContextIterator()
            while result.MoreShapeInContext():
                statuses=codes(result.StatusOnShape())
                if statuses:
                    context=result.ContextualShape(); owner=shapes.FindIndex(context)
                    contexts.append({'context_id':f'{solid_id}::CHECK_SUBSHAPE_{owner:06d}' if owner else None,
                                     'context_type':str(context.ShapeType()),'statuses':statuses})
                result.NextShapeInContext()
            if own or contexts:
                issues.append({'subshape_id':f'{solid_id}::CHECK_SUBSHAPE_{index:06d}',
                               'subshape_type':str(subshape.ShapeType()),'statuses':own,'contexts':contexts})
        except Exception as exc: errors.append({'index':index,'error':str(exc)})
    return {'solid_id':solid_id,'status':'NOT_EVALUATED','kernel_valid':bool(analyzer.IsValid()),
            'diagnostic_complete':not errors,'subshape_count':shapes.Extent(),'issues':issues,'diagnostic_errors':errors,
            'geometry_modified':False,'limits':'Kernel validity is geometry evidence; no healing, source blame or engineering compliance inferred'}
