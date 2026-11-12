"""Bounded, isolated review of morphology candidates; original run is untouched."""
import argparse,json,sys,subprocess,hashlib
from pathlib import Path
from time import perf_counter
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from catia_checker.occt_session_cache import atomic_json,digest

def worker(first,second,output):
    from catia_checker.occt_brep import OCCTBRepModel
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    model=OCCTBRepModel();model.load_brep('A',first);model.load_brep('B',second)
    started=perf_counter();records=[model.describe(i) for i in ('A','B')]
    shapes=[model._shape(i) for i in ('A','B')]
    operation=BRepAlgoAPI_Common()
    # Use the deferred constructor, so Build executes only once.
    from OCP.TopTools import TopTools_ListOfShape
    args=TopTools_ListOfShape();args.Append(shapes[0]);tools=TopTools_ListOfShape();tools.Append(shapes[1]);operation.SetArguments(args);operation.SetTools(tools);operation.Build()
    if not operation.IsDone():raise RuntimeError('Boolean common failed')
    common=operation.Shape();area=GProp_GProps();volume=GProp_GProps()
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopAbs import TopAbs_SOLID
    explorer=TopExp_Explorer(common,TopAbs_SOLID);solid_count=0
    while explorer.More():solid_count+=1;explorer.Next()
    BRepGProp.SurfaceProperties_s(common,area);BRepGProp.VolumeProperties_s(common,volume)
    atomic_json(output,{'elapsed_seconds':perf_counter()-started,'records':records,
        'input_valid':[BRepCheck_Analyzer(s).IsValid() for s in shapes],
        'common_valid':BRepCheck_Analyzer(common).IsValid(),'common_area_mm2':area.Mass(),
        'common_volume_raw_mm3':volume.Mass(),'common_solid_count':solid_count,
        'note':'开放壳体的 VolumeProperties 不适用，不能用于实体穿透判定'})

def main():
    parser=argparse.ArgumentParser();parser.add_argument('directory',type=Path);parser.add_argument('--worker',nargs=3);parser.add_argument('--continue-review',action='store_true');a=parser.parse_args()
    if a.worker:worker(*a.worker);return
    root=a.directory.resolve();triage=json.loads((root/'shape-triage-pilot.json').read_text(encoding='utf-8'))
    shells=[x for x in triage['rows'] if x['category']=='COINCIDENT_SURFACE_CANDIDATE']
    small=sorted([x for x in triage['rows'] if x['category']=='SMALL_OVERLAP_CANDIDATE'],key=lambda x:x['evidence']['common_volume_mm3'])[:3]
    out=root/'shape-review';out.mkdir(exist_ok=True);rows=[]
    if a.continue_review:
        old=json.loads((out/'review.json').read_text(encoding='utf-8'))
        seen={tuple(x['pair']) for x in old['rows']}
        pending=sorted([x for x in triage['rows'] if x['category']=='SMALL_OVERLAP_CANDIDATE' and tuple(x['pair']) not in seen],key=lambda x:x['evidence']['common_volume_mm3'])
        small=pending[:6]+pending[-6:] if len(pending)>12 else pending
        shells=[];out=out/'round-2';out.mkdir(exist_ok=True)
    for index,item in enumerate(shells+small):
        row={'pair':item['pair'],'hypothesis':item['category'],'excluded':False,'conversion_confirmed':False,
             'original_evidence':item['evidence']}
        try:
            paths=[]
            for identifier in item['pair']:
                candidates=list((root/'occt-cache'/'pairs').rglob(identifier.replace('::','_')+'.brep'))
                if len(candidates)!=1:raise ValueError('Cache identity ambiguous or missing')
                path=candidates[0]
                if digest(path)!=path.with_suffix('.sha256').read_text(encoding='ascii').strip():raise ValueError('Cache hash mismatch')
                paths.append(path)
            result=out/f'pair-{index:03d}.json'
            subprocess.run([sys.executable,__file__,str(root),'--worker',*map(str,paths),str(result)],timeout=20,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
            row.update(status='RECOMPUTED',details=json.loads(result.read_text(encoding='utf-8')))
        except subprocess.TimeoutExpired:row.update(status='TIMEOUT',note='独立复核超过 20 秒，保留待确认')
        except Exception as exc:row.update(status='ERROR',note=str(exc))
        rows.append(row);print(json.dumps({'pair':row['pair'],'status':row['status']},ensure_ascii=False),flush=True)
    atomic_json(out/'review.json',{'scope':'small-overlap low/high extremes' if a.continue_review else '3 coincident shell pairs + 3 smallest overlap samples',
        'triage_checkpoint_sha256':triage['checkpoint_sha256'],'rows':rows,'automatic_exclusions':0,
        'source_comparison_performed':False,'source_modified':False})
if __name__=='__main__':main()
