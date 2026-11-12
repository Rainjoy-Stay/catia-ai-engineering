"""Isolated Body copy benchmark. Identity is never inferred from paste order."""
import json
import math
import time
from pathlib import Path


def unique_copy_matches(source_records, copied_records):
    result=[]; used=set()
    for source in source_records:
        candidates=[i for i,copied in enumerate(copied_records)
                    if source['source_body_name']==copied.get('original_body_name')]
        if not candidates:
            candidates=[i for i,copied in enumerate(copied_records)
                        if source['source_body_name'] in copied['identity_names']]
        if len(candidates)!=1 or candidates[0] in used:
            raise ValueError('Copied identity missing or ambiguous: '+source['source_body_name'])
        used.add(candidates[0]); result.append((source,copied_records[candidates[0]]))
    if len(used)!=len(copied_records):
        raise ValueError('Unexpected copied Body')
    return result


def same_measurements(first, second):
    scalars=all(math.isfinite(first[k]) and math.isfinite(second[k]) and
               math.isclose(first[k],second[k],rel_tol=1e-6,abs_tol=1e-6)
               for k in ('volume_mm3','surface_area_mm2'))
    if first.get('centroid_verified') or second.get('centroid_verified'):
        return scalars and bool(first.get('centroid_verified') and second.get('centroid_verified')) and all(abs(a-b)<=1e-4 for a,b in zip(first['centroid_mm'],second['centroid_mm']))
    return scalars


def measurements(doc, body):
    measurable=doc.GetWorkbench('SPAWorkbench').GetMeasurable(doc.Part.CreateReferenceFromObject(body))
    return {'volume_mm3':float(measurable.Volume)*1e9,
            'surface_area_mm2':float(measurable.Area)*1e6, **centroid_facts(measurable)}


def centroid_facts(measurable):
    import pythoncom
    try:
        values=measurable._oleobj_.InvokeTypes(measurable._oleobj_.GetIDsOfNames('GetCOG'),0,
            pythoncom.DISPATCH_METHOD,(pythoncom.VT_EMPTY,0),
            ((pythoncom.VT_BYREF|pythoncom.VT_ARRAY|pythoncom.VT_VARIANT,3),),
            (float('nan'),float('nan'),float('nan')))
        if len(values)==3 and all(math.isfinite(float(v)) for v in values):
            return {'centroid_mm':[float(v) for v in values],'centroid_verified':True,
                    'centroid_method':'SPA_GETCOG_EXPLICIT_INOUT_SIGNATURE'}
        return {'centroid_verified':False,'centroid_error':'COM output not populated'}
    except Exception as exc:
        return {'centroid_verified':False,'centroid_error':str(exc)}


def capture_spatial_facts(conn, source_name, body_indices, output_path):
    conn.ensure_connected(); doc=conn.active_document
    if str(doc.Name)!=source_name: raise ValueError('Active document mismatch')
    path=Path(output_path).resolve()
    if path.exists(): raise ValueError('Overwrite prohibited')
    if not body_indices or len(body_indices)>80 or len(set(body_indices))!=len(body_indices) or any(type(i)!=int or not 1<=i<=int(doc.Part.Bodies.Count) for i in body_indices):
        raise ValueError('Invalid Body subset')
    records=[]
    for index in body_indices:
        body=doc.Part.Bodies.Item(index)
        spa=doc.GetWorkbench('SPAWorkbench').GetMeasurable(doc.Part.CreateReferenceFromObject(body))
        record={'source_body_index':index,'source_body_name':str(body.Name), **centroid_facts(spa)}
        records.append(record)
    result={'source_document':source_name,'records':records,'source_modified':False,
            'all_centroids_verified':all(r['centroid_verified'] for r in records)}
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return json.dumps({'output':str(path),'all_centroids_verified':result['all_centroids_verified']})


def benchmark_batch_copy(conn, source_name, body_indices, output_directory, copy_modes=None):
    modes=copy_modes or ['individual','bulk']
    if not modes or len(set(modes))!=len(modes) or any(m not in ('individual','bulk') for m in modes):
        raise ValueError('Invalid copy modes')
    conn.ensure_connected(); source=conn.active_document
    if str(source.Name)!=source_name:
        raise ValueError('Active document mismatch')
    count=int(source.Part.Bodies.Count)
    if not body_indices or len(body_indices)>80 or len(set(body_indices))!=len(body_indices) or any(type(i)!=int or not 1<=i<=count for i in body_indices):
        raise ValueError('Require 1 to 80 unique valid exact Body indices')
    output=Path(output_directory).resolve(); audit_file=output/'benchmark.json'
    if audit_file.exists() or any((output/(mode+'.stp')).exists() for mode in ('individual','bulk')):
        raise ValueError('Existing trial output; overwrite prohibited')
    output.mkdir(parents=True,exist_ok=True)
    before=(bool(source.Saved),count,int(source.Part.HybridBodies.Count))
    bodies={i:source.Part.Bodies.Item(i) for i in body_indices}
    records=[{'source_body_index':i,'source_body_name':str(bodies[i].Name),
              'source_path':'Part/Body#'+str(i)+'/'+str(bodies[i].Name),
              **measurements(source,bodies[i])} for i in body_indices]
    if len(set(r['source_body_name'] for r in records))!=len(records):
        raise ValueError('Subset has duplicate names; select uniquely identifiable Bodies')
    audit={'source_document':source_name,'body_indices':body_indices,
           'release':str(conn.app.SystemConfiguration.Release),
           'formal_check_executed':False,'full_model_coverage':False,
           'source_records':records,'cases':[],'status':'RUNNING'}
    def save(): audit_file.write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
    save(); selection=source.Selection
    try:
        for mode in modes:
            target=None; case={'mode':mode,'phase':'CREATE_TEMPORARY_PART','status':'RUNNING'}
            audit['cases'].append(case); save()
            total_start=time.perf_counter()
            try:
                target=conn.app.Documents.Add('Part')
                case['temporary_document']=str(target.Name)
                case['phase']='COPY_PASTE'; save()
                copy_start=time.perf_counter()
                if mode=='bulk':
                    source.Activate(); selection.Clear()
                    # Reverse order intentionally: later mapping must use identities, not order.
                    for index in reversed(body_indices): selection.Add(bodies[index])
                    selection.Copy(); selection.Clear(); target.Activate()
                    dest=target.Selection; dest.Clear(); dest.Add(target.Part)
                    dest.PasteSpecial('CATPrtResultWithOutLink'); dest.Clear()
                    case['copy_calls']=1; case['paste_calls']=1; case['copy_document_activations']=2
                else:
                    for position,index in enumerate(body_indices):
                        source.Activate(); selection.Clear(); selection.Add(bodies[index])
                        selection.Copy(); selection.Clear(); target.Activate()
                        body=target.Part.MainBody if position==0 else target.Part.Bodies.Add()
                        body.Name=records[position]['source_body_name']
                        dest=target.Selection; dest.Clear(); dest.Add(body)
                        dest.PasteSpecial('CATPrtResultWithOutLink'); dest.Clear()
                    case['copy_calls']=len(body_indices); case['paste_calls']=len(body_indices)
                    case['copy_document_activations']=len(body_indices)*2
                case['copy_paste_seconds']=time.perf_counter()-copy_start
                case['phase']='UPDATE_AND_VERIFY'; save()
                started=time.perf_counter(); target.Part.Update()
                case['update_seconds']=time.perf_counter()-started
                started=time.perf_counter(); copied=[]
                for i in range(1,int(target.Part.Bodies.Count)+1):
                    body=target.Part.Bodies.Item(i)
                    if int(body.Shapes.Count)==0: continue
                    copied.append({'body':body,'original_body_name':str(body.Name),
                        'identity_names':[str(body.Name),*[str(body.Shapes.Item(j).Name) for j in range(1,int(body.Shapes.Count)+1)]]})
                case['nonempty_body_count']=len(copied)
                case['copied_identities']=[{k:v for k,v in item.items() if k!='body'} for item in copied]
                matches=unique_copy_matches(records,copied)
                mapping=[]
                for record,copy in matches:
                    facts=measurements(target,copy['body'])
                    if not same_measurements(record,facts):
                        raise ValueError('Geometry measurement mismatch: '+record['source_body_name'])
                    label='SOURCE_BODY_'+str(record['source_body_index']).zfill(6)
                    copy['body'].Name=label
                    # Unique export label on owned result feature enables independent STEP remapping.
                    copy['body'].Shapes.Item(int(copy['body'].Shapes.Count)).Name=label
                    mapping.append({**record,'batch_body_name':label,
                                    'target_original_name':copy['original_body_name'],
                                    'mapping_method':'UNIQUE_COPIED_NAME_AND_SPA_VOLUME_AREA',
                                    'target_measurements':facts})
                case['mapping']=mapping; case['mapping_verified']=True
                case['verification_seconds']=time.perf_counter()-started
                case['phase']='STEP_EXPORT'; save()
                target.Part.Update(); started=time.perf_counter(); step=output/(mode+'.stp')
                target.ExportData(str(step),'stp')
                case['step_export_seconds']=time.perf_counter()-started
                if not step.is_file() or not step.stat().st_size:
                    raise RuntimeError('Empty STEP export')
                case.update(step_path=str(step),step_bytes=step.stat().st_size,status='COMPLETE',phase='EXPORTED')
                case['total_seconds']=time.perf_counter()-total_start
                save()
            except Exception as exc:
                case.update(status='ERROR',error=str(exc)); raise
            finally:
                # Only close the disposable document created by this case.
                if target is not None: target.Close()
                source.Activate(); selection.Clear()
                save()
        audit['status']='COMPLETE'
        if len(audit['cases'])==2:
            first,second=audit['cases']
            audit['copy_speedup']=first['copy_paste_seconds']/max(second['copy_paste_seconds'],1e-9)
            audit['total_speedup']=first['total_seconds']/max(second['total_seconds'],1e-9)
    except Exception as exc:
        audit.update(status='ERROR',error=str(exc)); raise
    finally:
        source.Activate(); selection.Clear()
        audit['source_state_unchanged']=before==(bool(source.Saved),int(source.Part.Bodies.Count),int(source.Part.HybridBodies.Count))
        save()
        if not audit['source_state_unchanged']: raise RuntimeError('Source state changed')
    return json.dumps({'status':audit['status'],'audit_path':str(audit_file),
                       'copy_speedup':audit.get('copy_speedup'),'total_speedup':audit.get('total_speedup')})


def export_surface_batches(conn, source_name, output_directory, start_batch=0, verify_body_audit=None):
    """Export all exact indexed geometric elements using the existing audit backend."""
    import sys
    conn.ensure_connected();source=conn.active_document
    if str(source.Name)!=source_name:raise ValueError('Active document mismatch')
    root=Path(__file__).resolve().parents[4]
    sys.path.insert(0,str(root/'project'))
    from catia_checker.catia_body_batches import export_geometrical_sets
    directory=Path(output_directory).resolve()
    if verify_body_audit:
        cached=json.loads(Path(verify_body_audit).read_text(encoding='utf-8'))
        records=cached['body_mapping']
        count=int(source.Part.Bodies.Count)
        if cached['source']!=source_name or len(records)!=count or sorted(r['source_body_index'] for r in records)!=list(range(1,count+1)):
            raise ValueError('Cached source coverage mismatch')
        for record in records:
            body=source.Part.Bodies.Item(record['source_body_index'])
            if str(body.Name)!=record['source_body_name'] or not same_measurements(record,measurements(source,body)):
                raise ValueError('Cached source geometry mismatch: '+str(record['source_body_index']))
        (directory.parent/'recovery-source-verification.json').write_text(json.dumps({
            'verified_body_count':count,'method':'INDEX_NAME_SPA_VOLUME_AREA_CENTROID',
            'limitation':'Measurement equivalence is not a full topological equivalence proof',
            'source_modified':False},ensure_ascii=False,indent=2),encoding='utf-8')
    if any(directory.glob('*.stp')) or (directory/'surface-export-coverage.json').exists():
        raise ValueError('Existing surface output; overwrite prohibited')
    directory.mkdir(parents=True,exist_ok=True)
    audit=export_geometrical_sets(conn.app,source,directory,start_batch=start_batch,bulk_copy=True)
    audit['batch_files']=[str(p) for p in audit['batch_files']]
    (directory/'surface-audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
    return json.dumps({'audit_path':str(directory/'surface-audit.json'),'exported':len(audit['mapping']),
        'errors':len(audit['errors']),'source_modified':False})
