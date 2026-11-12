"""Compare selected STEP entities and singleton CATIA exports against batch exports."""
import argparse
import json
import re
import math
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from reverify_bulk_transfer import adaptive_properties, independent_geometry, transferred_shape_names
from OCP.STEPControl import STEPControl_Reader
from OCP.IFSelect import IFSelect_RetDone
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_FACE,TopAbs_EDGE,TopAbs_SHELL
from OCP.StepToTopoDS import StepToTopoDS_Builder
from OCP.StepData import StepData_Factors
from catia_checker.occt_brep import _bounds, _mass_properties

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'project/output/path-comparison-20261001'
PILOT=ROOT/'project/output/bulk-copy-pilot/retry'
INDICES=(1,2,3,5,9,31,38)

def measure(shape, adaptive=True):
    analyzer=BRepCheck_Analyzer(shape); errors=[];counts={}
    for kind,title in ((TopAbs_SHELL,'shell'),(TopAbs_FACE,'face'),(TopAbs_EDGE,'edge')):
        explorer=TopExp_Explorer(shape,kind);seen=[]
        while explorer.More():
            sub=explorer.Current()
            if not any(sub.IsSame(s) for s in seen):
                seen.append(sub)
                status=[str(v) for v in analyzer.Result(sub).Status()]
                bad=[v for v in status if not v.endswith('BRepCheck_NoError')]
                if bad: errors.append({'kind':title,'index':len(seen),'status':bad})
            explorer.Next()
        counts[title]=len(seen)
    return {'valid_topology':bool(analyzer.IsValid()),'topology_counts':counts,
        'local_status_errors':errors,'bounds_mm':_bounds(shape),'default':_mass_properties(shape),
        'adaptive_1e8':adaptive_properties(shape,1e-8) if adaptive else None}

def reader_for(path):
    reader=STEPControl_Reader()
    if reader.ReadFile(str(path))!=IFSelect_RetDone: raise RuntimeError('Read failed: '+str(path))
    return reader

def original(path, raw=False):
    audit=json.loads((PILOT/'benchmark.json').read_text(encoding='utf-8'))
    selected=[r for r in audit['source_records'] if r['source_body_index'] in INDICES]
    ids={int(r['source_body_name'].split('#')[-1]):r for r in selected}
    text=path.read_text(encoding='utf-8',errors='strict')
    positions={int(match.group(1)):(position,match.group(2))
        for position,match in enumerate(re.finditer(r'^#(\d+)\s*=\s*([A-Z_]+)',text,re.M),1)
        if int(match.group(1)) in ids}
    print('READ_ORIGINAL',flush=True); reader=reader_for(path);model=reader.StepModel();rows=[]
    print('READ_COMPLETE '+str(model.NbEntities()),flush=True)
    print('TRANSFER_ROOTS_START',flush=True)
    if not raw and reader.TransferRoots()<=0:raise RuntimeError('Original roots transfer failed')
    print('TRANSFER_ROOTS_COMPLETE',flush=True)
    shapes_by_entity={}
    for kind,shape in ([] if raw else independent_geometry(reader.OneShape())):
        entity=reader.WS().TransferReader().EntityFromShapeResult(shape,1)
        if entity is not None:
            number=model.Number(entity)
            shapes_by_entity.setdefault(number,[]).append(shape)
    print('REVERSE_ENTITY_SAMPLE '+str(list(shapes_by_entity)[:12]),flush=True)
    for ident in ids:
        n=model.NextNumberForLabel('#'+str(ident),0,True)
        if not n:raise RuntimeError('Missing original entity label: '+str(ident))
        entity=model.Value(n)
        if positions[ident][0]!=n:raise RuntimeError('Original file entity order mismatch')
        if positions[ident][1] not in ('BREP_WITH_VOIDS','MANIFOLD_SOLID_BREP'):
            raise RuntimeError('Original entity is not a solid')
        record=ids[ident]
        if raw:
            factors=StepData_Factors();factors.InitializeFactors(1.0,math.pi/180,1.0)
            builder=StepToTopoDS_Builder()
            builder.Init(entity,reader.WS().TransferReader().TransientProcess(),factors)
            if not builder.IsDone():raise RuntimeError('Raw solid translation failed')
            shape=builder.Value()
            rows.append({'source_body_index':record['source_body_index'],'source_name':record['source_body_name'],
                'original_entity_id':ident,'original_entity_type':entity.DynamicType().Name(),**measure(shape,adaptive=False)})
            print('RAW_ORIGINAL_BODY '+str(record['source_body_index']),flush=True)
            (OUT/'raw-original-step-partial.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
            continue
        candidates=shapes_by_entity.get(n,[])
        direct=reader.WS().TransferReader().ShapeResult(entity)
        print('ASSOCIATION '+str(ident)+' index='+str(n)+' reverse='+str(len(candidates))+' direct_null='+str(direct.IsNull()),flush=True)
        if not candidates and not direct.IsNull():candidates=[direct]
        if len(candidates)!=1:
            binder=reader.WS().TransferReader().TransientProcess().Find(entity)
            print('BINDER '+str(type(binder))+' '+str(binder.DynamicType().Name() if binder else None),flush=True)
            raise RuntimeError('Missing/ambiguous transferred solid: '+str(ident))
        shape=candidates[0]
        rows.append({'source_body_index':record['source_body_index'],'source_name':record['source_body_name'],
            'original_entity_id':ident,'original_entity_type':entity.DynamicType().Name(),**measure(shape,adaptive=False)})
        print('ORIGINAL_BODY '+str(record['source_body_index']),flush=True)
        (OUT/'original-step-partial.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
        if len(rows)==len(selected):break
    if len(rows)!=len(selected): raise RuntimeError('Incomplete original entity mapping')
    (OUT/('raw-original-step.json' if raw else 'original-step.json')).write_text(json.dumps({'path':str(path),'mapping_method':'EXACT_CATIA_BREP_ENTITY_ID',
        'normal_reader_import_equivalence_verified':not raw,'translation':'STEP_TO_TOPODS_BUILDER' if raw else 'STEP_CONTROL_READER',
        'geometry':rows,'engineering_pass':False},ensure_ascii=False,indent=2),encoding='utf-8')

def exports():
    rows=[]
    for index in INDICES:
        audit=json.loads((OUT/('body-'+str(index))/'benchmark.json').read_text(encoding='utf-8'))
        case=audit['cases'][0]
        if case['status']!='COMPLETE': raise RuntimeError('Singleton incomplete')
        reader=reader_for(case['step_path']);reader.TransferRoots()
        items=independent_geometry(reader.OneShape())
        if len(items)!=1:raise RuntimeError('Not singleton')
        label=transferred_shape_names(reader,items)[0]
        if label['name']!='SOURCE_BODY_'+str(index).zfill(6):raise RuntimeError('Wrong singleton label')
        rows.append({'source_body_index':index,'source_name':label['name'],**measure(items[0][1])})
        print('SINGLETON_BODY '+str(index),flush=True)
    (OUT/'singleton-step.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    reader=reader_for(PILOT/'bulk.stp');reader.TransferRoots();items=independent_geometry(reader.OneShape())
    bulk=[]
    for (_,shape),identity in zip(items,transferred_shape_names(reader,items)):
        index=int(identity['name'].split('_')[-1])
        if index in INDICES:
            bulk.append({'source_body_index':index,'source_name':identity['name'],**measure(shape)})
            print('BULK_BODY '+str(index),flush=True)
    (OUT/'bulk-step.json').write_text(json.dumps(bulk,ensure_ascii=False,indent=2),encoding='utf-8')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--original',type=Path);parser.add_argument('--raw',action='store_true');args=parser.parse_args()
    if args.original:original(args.original,args.raw)
    else:exports()
