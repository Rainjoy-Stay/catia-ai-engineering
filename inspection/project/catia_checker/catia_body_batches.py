"""Read-only source transaction that exports CATIA Bodies in disposable STEP batches."""
from __future__ import annotations
from pathlib import Path
import hashlib
import json
import os
import time
from typing import Any, Callable

def _atomic_json(path: Path, payload: Any)->None:
    temporary=path.with_suffix(path.suffix+'.pending')
    with temporary.open('w',encoding='utf-8') as stream:
        json.dump(payload,stream,ensure_ascii=False,indent=2)
        stream.flush(); os.fsync(stream.fileno())
    temporary.replace(path)

def persist_export_batch(directory: Path, path: Path, records: list[dict],
                         completed: list[dict], source: dict, timings: dict)->dict:
    """Commit a batch only after its STEP and exact source records are durable.

    This is an export receipt, NOT permission to reuse it against a changed model.
    """
    with path.open('rb') as stream:
        digest=hashlib.file_digest(stream,'sha256').hexdigest()
    receipt={'batch_id':path.stem,'file':path.name,'size_bytes':path.stat().st_size,
             'sha256':digest,'body_mapping':records,'timings_seconds':timings}
    _atomic_json(directory/(path.stem+'.mapping.json'),receipt)
    _atomic_json(directory/'export-checkpoint.json',{
        'schema_version':1,'source':source,'completed_batches':[*completed,receipt],
        'reuse_requires_source_verification':True})
    return receipt

def export_body_batches(app: Any, source_doc: Any, directory: Path, *, batch_size: int=40,
                        body_indices: list[int] | None=None,
                        include_geometrical_sets: bool=True,
                        progress: Callable[[dict],None] | None=None)->dict:
    if batch_size<1: raise ValueError("batch_size must be positive")
    part=source_doc.Part; before=(bool(source_doc.Saved),int(part.Bodies.Count)); directory.mkdir(parents=True,exist_ok=True)
    spa=source_doc.GetWorkbench("SPAWorkbench")
    selected=body_indices or list(range(1,before[1]+1))
    if len(set(selected))!=len(selected) or any(i<1 or i>before[1] for i in selected): raise ValueError("body_indices must be unique valid 1-based indices")
    outputs=[]; body_records=[]; receipts=[]
    source={'document':str(source_doc.Name),'path':str(getattr(source_doc,'FullName','') or ''),
            'saved':before[0],'body_count':before[1],'selected_indices':selected,'batch_size':batch_size}
    try:
        for start in range(0,len(selected),batch_size):
            indices=selected[start:start+batch_size]; target=app.Documents.Add("Part")
            batch_id=f"BATCH_{len(outputs)+1:04d}"
            started=time.monotonic(); record_start=len(body_records)
            try:
                # Cosmetic temporary product naming is not geometry authority.
                # Some CATIA sessions reject this COM setter; do not abort export.
                try: target.Product.PartNumber=batch_id
                except Exception as exc:
                    if progress: progress({'stage':'CATIA_BATCH_NAME_WARNING','batch_id':batch_id,'error':str(exc)})
                target_part=target.Part
                for position,index in enumerate(indices):
                    source_doc.Activate(); source_sel=source_doc.Selection; source_sel.Clear(); body=part.Bodies.Item(index); source_sel.Add(body); source_sel.Copy(); source_sel.Clear()
                    target.Activate(); dest=target_part.MainBody if position==0 else target_part.Bodies.Add(); dest.Name=f"SOURCE_BODY_{index:06d}"
                    target_sel=target.Selection; target_sel.Clear(); target_sel.Add(dest)
                    try: target_sel.PasteSpecial("CATPrtResultWithOutLink")
                    except Exception: target_sel.PasteSpecial("CATPrtResult")
                    target_sel.Clear()
                    record={"source_body_index":index,"source_body_name":str(body.Name),"batch_id":batch_id,"batch_body_name":str(dest.Name)}
                    measurable=spa.GetMeasurable(part.CreateReferenceFromObject(body))
                    try: record["volume_mm3"]=float(measurable.Volume)*1e9
                    except Exception: pass
                    try: record["surface_area_mm2"]=float(measurable.Area)*1e6
                    except Exception: pass
                    try:
                        cog=[0.0,0.0,0.0]; returned=measurable.GetCOG(cog)
                        values=returned if isinstance(returned,(tuple,list)) and len(returned)==3 else cog
                        if values != cog or any(float(x)!=0 for x in values):
                            record['centroid_mm']=[float(x) for x in values]
                            record['centroid_verified']=True
                        else:
                            record['centroid_verified']=False
                            record['centroid_limitation']='SPA_ZERO_VECTOR_UNVERIFIED'
                    except Exception: pass
                    body_records.append(record)
                copied=time.monotonic()
                target_part.Update(); updated=time.monotonic()
                path=directory/f"{batch_id}.stp"; target.ExportData(str(path.resolve()),"stp")
                exported=time.monotonic()
                if not path.is_file() or path.stat().st_size<=0: raise RuntimeError(f"{batch_id} export produced no STEP")
                timings={'copy_and_measure':copied-started,'update':updated-copied,'step_export':exported-updated}
                receipt=persist_export_batch(directory,path,body_records[record_start:],receipts,source,timings)
                receipts.append(receipt)
                _atomic_json(directory/'body-mapping.json',body_records)
                outputs.append(path)
                if progress: progress({"stage":"CATIA_BATCH_EXPORT_COMPLETE","batch_id":batch_id,"batch_number":len(outputs),"body_count":len(indices),"size_bytes":path.stat().st_size,'timings_seconds':timings,'export_checkpoint':str(directory/'export-checkpoint.json')})
            finally:
                try: target.Close()
                finally: source_doc.Activate()
    finally:
        try: source_doc.Selection.Clear()
        except Exception: pass
    after=(bool(source_doc.Saved),int(part.Bodies.Count))
    if after!=before: raise RuntimeError("Source CATPart state changed during batch export")
    extra=export_geometrical_sets(app,source_doc,directory,batch_size=batch_size,
        start_batch=len(outputs),progress=progress) if include_geometrical_sets and body_indices is None else {'batch_files':[],'mapping':[],'errors':[],'element_count':0}
    outputs.extend(extra['batch_files']);body_records.extend(extra['mapping'])
    _atomic_json(directory/'body-mapping.json',body_records)
    return {"batch_files":outputs,"body_mapping":body_records,"exported_body_count":len(selected),"full_source_coverage":len(selected)==before[1] and not extra['errors'],"source_saved_before":before[0],"source_saved_after":bool(source_doc.Saved),"source_body_count_before":before[1],"source_body_count_after":int(part.Bodies.Count),"source_modified":False,
            'geometrical_set_element_count':extra['element_count'],'surface_export_errors':extra['errors'],
            'geometrical_sets_included':include_geometrical_sets and body_indices is None}

def iter_geometrical_elements(part):
    """Index-based paths distinguish duplicate CATIA names; no name search."""
    def walk(collection,parent,indices):
        if collection is None:
            return
        for index in range(1,int(collection.Count)+1):
            group=collection.Item(index); path=parent+'/'+str(group.Name); keys=[*indices,index]
            shapes=group.HybridShapes
            for number in range(1,int(shapes.Count)+1 if shapes is not None else 1):
                element=shapes.Item(number)
                yield element,{'source_body_index':'G'+'.'.join(map(str,keys))+':E'+str(number),
                    'source_body_name':str(element.Name),'source_path':path+'/'+str(element.Name),
                    'source_set_path':path,'source_set_indices':keys,'source_element_index':number,
                    'source_kind':'GEOMETRICAL_SET_ELEMENT'}
            try: nested=group.HybridBodies
            except Exception: nested=None
            if nested is not None: yield from walk(nested,path,keys)
    yield from walk(part.HybridBodies,'Part',[])
    try: ordered=part.OrderedGeometricalSets
    except Exception: ordered=None
    if ordered is not None: yield from walk(ordered,'Part/OrderedGeometricalSets',[0])
    for index in range(1,int(part.Bodies.Count)+1):
        body=part.Bodies.Item(index)
        try: groups=body.HybridBodies
        except Exception: continue
        yield from walk(groups,'Part/Body#'+str(index)+'/'+str(body.Name),[index,0])

def export_geometrical_sets(app,source_doc,directory,*,batch_size=40,start_batch=0,progress=None,bulk_copy=False):
    elements=list(iter_geometrical_elements(source_doc.Part));outputs=[];mapping=[];errors=[];receipts=[]
    try: receipts=json.loads((directory/'export-checkpoint.json').read_text(encoding='utf-8'))['completed_batches']
    except (OSError,ValueError,KeyError): pass
    before=(bool(source_doc.Saved),int(source_doc.Part.Bodies.Count));spa=source_doc.GetWorkbench('SPAWorkbench')
    chunks=[]
    for element in elements:
        if not chunks or len(chunks[-1])>=batch_size or chunks[-1][-1][1]['source_set_indices']!=element[1]['source_set_indices']: chunks.append([])
        chunks[-1].append(element)
    for chunk in chunks:
        target=app.Documents.Add('Part');batch_id=f'BATCH_{start_batch+len(outputs)+1:04d}'
        records=[];started=time.monotonic()
        try:
            group=target.Part.HybridBodies.Add();group.Name='Inspection surfaces'
            if bulk_copy:
                source_doc.Activate();sel=source_doc.Selection;sel.Clear()
                for element,identity in chunk:sel.Add(element)
                sel.Copy();sel.Clear();target.Activate();sel=target.Selection;sel.Clear();sel.Add(group)
                sel.PasteSpecial('CATPrtResultWithOutLink');sel.Clear()
                if int(group.HybridShapes.Count)!=len(chunk):raise RuntimeError('Surface bulk copy count mismatch')
            for element,identity in chunk:
                if not bulk_copy:
                    source_doc.Activate();sel=source_doc.Selection;sel.Clear();sel.Add(element);sel.Copy();sel.Clear()
                    target.Activate();sel=target.Selection;sel.Clear();sel.Add(group);sel.PasteSpecial('CATPrtResultWithOutLink');sel.Clear()
                record={**identity,'batch_id':batch_id}
                try: record['surface_area_mm2']=float(spa.GetMeasurable(source_doc.Part.CreateReferenceFromObject(element)).Area)*1e6
                except Exception: record['measurement_limitation']='AREA_UNAVAILABLE'
                records.append(record)
            target.Part.Update();path=directory/(batch_id+'.stp');target.ExportData(str(path.resolve()),'stp')
            if not path.is_file() or path.stat().st_size==0: raise RuntimeError('Empty surface STEP')
            receipt=persist_export_batch(directory,path,records,receipts,{'document':str(source_doc.Name),'scope':'GEOMETRICAL_SETS'},{'total':time.monotonic()-started})
            receipts.append(receipt);outputs.append(path);mapping.extend(records)
            if progress: progress({'stage':'CATIA_SURFACE_EXPORT_COMPLETE','batch_id':batch_id,'element_count':len(records),'operation':'几何图形集、面与壳导出'})
        except Exception as exc:
            errors.append({'batch_id':batch_id,'code':'SURFACE_EXPORT_FAILED','error':str(exc),
                           'source_paths':[identity['source_path'] for _,identity in chunk]})
            if progress: progress({'stage':'CATIA_SURFACE_EXPORT_ERROR',**errors[-1]})
        finally:
            target.Close();source_doc.Activate();source_doc.Selection.Clear()
        _atomic_json(directory/'surface-export-coverage.json',{'registered':len(elements),'exported':len(mapping),'errors':errors,'mapping':mapping})
    if before!=(bool(source_doc.Saved),int(source_doc.Part.Bodies.Count)): raise RuntimeError('Source changed during surface export')
    return {'batch_files':outputs,'mapping':mapping,'errors':errors,'element_count':len(elements)}
