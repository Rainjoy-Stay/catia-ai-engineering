"""Main-project adapter for exact large single-CATPart inspection."""

from __future__ import annotations

from pathlib import Path
import hashlib, json, os, subprocess, sys, tempfile
from contextlib import nullcontext
from .occt_session_cache import load_batch, identity, pair_file, preview_valid, mark_preview, ResidentControl
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from queue import Empty, Queue
from threading import Lock, Thread
from time import perf_counter
from typing import Any, Callable, Mapping

from standalone.large_single_part_analysis import analyze_large_single_part
from standalone.large_single_part_analysis.batching import MultiBatchBackend, merge_batch_manifests
from .models import CheckFinding, CheckStatus, Evidence, EvidenceKind, Severity
from .occt_brep import OCCTBRepModel
from standalone.step_interference_filter import filter_result
from .geometry_fingerprint import (canonical_geometry_features, geometry_fingerprint,
                                   match_geometry_records_with_labels)


class _PersistentPairWorker:
    """One killable OCCT process with an in-process BREP cache."""
    _prefix = "PAIR_RESULT "

    def __init__(self, script: Path):
        self.script = script
        self.process: subprocess.Popen[str] | None = None
        self.responses: Queue[str | None] = Queue()
        self._start()

    def _start(self) -> None:
        self.responses = Queue()
        self.process = subprocess.Popen(
            [sys.executable, "-u", str(self.script)], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1)
        Thread(target=self._read_stdout,args=(self.process,self.responses),daemon=True).start()

    def _read_stdout(self, process: subprocess.Popen[str],
                     responses: Queue[str | None]) -> None:
        if process.stdout is None:
            return
        for line in process.stdout:
            if line.startswith(self._prefix):
                responses.put(line[len(self._prefix):])
        responses.put(None)

    def _stop(self) -> None:
        process, self.process = self.process, None
        if process is None:
            return
        if process.poll() is None:
            process.terminate()
            try: process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill(); process.wait(timeout=2)
        for stream in (process.stdin, process.stdout):
            if stream:
                stream.close()

    def restart(self) -> None:
        self._stop(); self._start()

    def request(self, first: Path, second: Path, threshold_mm: float,
                timeout: float) -> dict[str, Any]:
        process = self.process
        if process is None or process.poll() is not None or process.stdin is None:
            self.restart(); process = self.process
        assert process is not None and process.stdin is not None
        try:
            process.stdin.write(json.dumps({"first":str(first),"second":str(second),
                                            "threshold_mm":threshold_mm})+"\n")
            process.stdin.flush()
            line = self.responses.get(timeout=timeout)
        except (BrokenPipeError, OSError, Empty) as exc:
            self.restart()
            if isinstance(exc, Empty):
                raise TimeoutError("persistent exact pair worker timed out") from exc
            raise RuntimeError("persistent exact pair worker stopped") from exc
        if line is None:
            self.restart()
            raise RuntimeError("persistent exact pair worker exited")
        response = json.loads(line)
        if not response.get("ok"):
            raise RuntimeError(str(response.get("error_type") or "OCCT worker error"))
        return dict(response["result"])

    def close(self) -> None:
        self._stop()


def _finding(item: Mapping[str, Any], source: str,
             object_records: Mapping[str,Mapping[str,Any]] | None=None) -> CheckFinding:
    disposition = str(item["disposition"])
    status = {"PASS": CheckStatus.PASS, "FAIL": CheckStatus.FAIL}.get(
        disposition, CheckStatus.NOT_EVALUATED)
    labels = {"INTERNAL_SOLID_INTERFERENCE": "单CATPart内部实体穿模",
              "SURFACE_INTERSECTION":"面／壳相交，需要复核",
              "SURFACE_CONTACT":"面／壳接触，需要复核",
              "SURFACE_CLEAR":"面／壳候选距离检查完成",
              "SOLID_CONTACT": "单CATPart内部实体接触",
              "LOW_CLEARANCE": "单CATPart内部实体低净距",
              "CLEAR": "单CATPart内部实体间距正常"}
    code = str(item["code"])
    records=object_records or {}; record_a=dict(records.get(str(item["object_a"])) or {}); record_b=dict(records.get(str(item["object_b"])) or {})
    label=lambda geometry,record: (f"{record.get('source_body_name')} [Body #{record.get('source_body_index')}]" if record else geometry)
    object_a=label(str(item["object_a"]),record_a); object_b=label(str(item["object_b"]),record_b)
    return CheckFinding(
        issue_id=str(item["issue_id"]), rule_id=f"GEOMETRY.{code}",
        status=status, severity=Severity.S4 if status is CheckStatus.FAIL else Severity.S2,
        title=labels.get(code, code), message=(
            "OCCT精确公共体积确认两个独立Solid发生内部穿模。" if code == "INTERNAL_SOLID_INTERFERENCE"
            else "OCCT精确距离确认接触或低净距，需要核对是否为设计关系。" if disposition == "REVIEW"
            else "该空间候选未发现公共体积或受控净距问题。"),
        object_a=object_a, object_b=object_b,
        measured_value=float(item["intersection_volume_mm3"])
        if code == "INTERNAL_SOLID_INTERFERENCE" else float(item["minimum_distance_mm"]),
        unit="mm3" if code == "INTERNAL_SOLID_INTERFERENCE" else "mm",
        recommendation="在CATIA中定位对应Body并确认设计关系；非设计性重叠应修正源几何。",
        evidence=(Evidence(kind=EvidenceKind.CATIA_MEASUREMENT, source=source,
                           description="OCCT exact B-Rep internal Body evaluation",
                           object_paths=(object_a,object_b),
                           data=dict(item)),),
        metadata={"large_single_part": True, "geometry_disposition": disposition,
                  "geometry_object_a":str(item["object_a"]),"geometry_object_b":str(item["object_b"]),
                  "source_body_a":record_a or None,"source_body_b":record_b or None,
                  "mesh_used": False})


def inspect_large_single_part_file(path: str | Path, *,
                                   rules: Mapping[str, Any],
                                   progress: Callable[[dict[str, Any]], None] | None = None) -> dict[str, Any]:
    """Load STEP/IGES exactly and return standalone plus unified findings."""
    source = Path(path).resolve()
    model = OCCTBRepModel()
    if progress: progress({"stage": "OCCT_LOAD_START", "source": str(source)})
    config = rules.get("large_single_part") or {}
    manifest = model.load_iges(source) if source.suffix.lower() in {".igs", ".iges"} else model.load_step(
        source, lightweight=bool(config.get("lightweight_manifest", True)), progress=progress)
    if progress:
        progress({"stage": "OCCT_LOAD_COMPLETE",
                  "registered_shapes": len(manifest.get("shapes", []))})
    analysis = analyze_large_single_part(
        model, manifest,
        broad_phase_margin_mm=float(config.get("broad_phase_margin_mm", 0.0)),
        contact_tolerance_mm=float(config.get("contact_tolerance_mm", 1e-5)),
        interference_volume_tolerance_mm3=float(
            config.get("interference_volume_tolerance_mm3", 1e-6)),
        clearance_review_mm=float(config.get("clearance_review_mm", 0.0)),
        max_exact_pairs=int(config.get("max_exact_pairs", 10000)),
        progress=progress,
        progress_interval=int(config.get("progress_interval_pairs", 100)))
    findings = [_finding(item, "OCCT_EXACT_BREP") for item in analysis["findings"]]
    return {"schema_version": "large-single-part-main-bundle.v1.0",
            "source_file": str(source), "manifest": manifest, "analysis": analysis,
            "findings": [item.to_dict() for item in findings],
            "mesh_used": False, "source_modified": False}

def inspect_large_single_part_batches(paths: list[str | Path], *, rules: Mapping[str,Any],
                                      progress: Callable[[dict[str,Any]],None] | None=None)->dict[str,Any]:
    """Load independent STEP chunks, then evaluate one global exact candidate set."""
    config=rules.get("large_single_part") or {}; models={}; batches=[]
    for index,value in enumerate(paths,1):
        batch_id=f"BATCH_{index:04d}"; model=OCCTBRepModel()
        if progress: progress({"stage":"BATCH_LOAD_START","batch_id":batch_id,"batch_count":len(paths)})
        manifest=model.load_step(value,lightweight=True,progress=progress); models[batch_id]=model
        batches.append({"batch_id":batch_id,"manifest":manifest})
        if progress: progress({"stage":"BATCH_LOAD_COMPLETE","batch_id":batch_id,"solid_count":len(manifest["shapes"])-1})
    plan=merge_batch_manifests(batches,margin_mm=float(config.get("broad_phase_margin_mm",0.0)))
    manifest={"source_file":"BATCHED_STEP","root_shape_id":"","shapes":plan["shapes"]}
    analysis=analyze_large_single_part(MultiBatchBackend(models,plan["mapping"]),manifest,
      broad_phase_margin_mm=float(config.get("broad_phase_margin_mm",0.0)),
      contact_tolerance_mm=float(config.get("contact_tolerance_mm",1e-5)),
      interference_volume_tolerance_mm3=float(config.get("interference_volume_tolerance_mm3",1e-6)),
      clearance_review_mm=float(config.get("clearance_review_mm",0.0)),max_exact_pairs=int(config.get("max_exact_pairs",10000)),
      progress=progress,progress_interval=int(config.get("progress_interval_pairs",100)))
    findings=[_finding(item,"OCCT_EXACT_BREP_BATCHED") for item in analysis["findings"]]
    return {"schema_version":"large-single-part-batched-main-bundle.v1.0","batch_plan":plan,
      "analysis":analysis,"findings":[x.to_dict() for x in findings],"mesh_used":False,"source_modified":False}

def inspect_large_single_part_batches_isolated(paths: list[str | Path], *, rules: Mapping[str,Any],
                                               progress: Callable[[dict[str,Any]],None] | None=None,
                                               pair_timeout_seconds: float | None=None,
                                               pair_retry_timeout_seconds: float | None=None,
                                               max_pair_retries: int | None=None,
                                               checkpoint_path: str | Path | None=None,
                                               run_budget_seconds: float | None=None,
                                               max_pair_workers: int | None=None,
                                               body_mapping: list[Mapping[str,Any]] | None=None)->dict[str,Any]:
    """Evaluate every candidate in a killable process using per-Solid BREP caches."""
    config=rules.get("large_single_part") or {}; models={}; batches=[]; mapping_errors=[]; source_records={}
    monitor_directory=os.environ.get("CATIA_MONITOR_DIRECTORY")
    session_identity=identity(paths,body_mapping) if monitor_directory else None
    persistent_cache=Path(monitor_directory)/'occt-cache' if monitor_directory else None
    for index,value in enumerate(paths,1):
        batch_id=f"BATCH_{index:04d}"; model=OCCTBRepModel()
        if progress: progress({"stage":"BATCH_LOAD_START","batch_id":batch_id,"batch_count":len(paths)})
        manifest=load_batch(model,value,persistent_cache/'batches',progress) if persistent_cache else model.load_step(value,lightweight=True,progress=progress)
        expected=[dict(x) for x in (body_mapping or []) if str(x.get("batch_id"))==batch_id]; solids=[x for x in manifest["shapes"] if x["shape_id"]!=manifest["root_shape_id"]]
        if expected and all(x.get('source_kind')=='GEOMETRICAL_SET_ELEMENT' for x in expected) and len({tuple(x.get('source_set_indices',[])) for x in expected})==1:
            for shape in solids:
                shape.update({'source_set_path':expected[0].get('source_set_path'),'source_set_indices':expected[0].get('source_set_indices'),
                              'group_mapping_method':'EXACT_EXPORT_SCOPE_SINGLE_GEOMETRICAL_SET'})
        if body_mapping is not None and len(expected)!=len(solids):
            mapping_errors.append({"code":"BODY_SOLID_MAPPING_COUNT_MISMATCH","batch_id":batch_id,"expected_bodies":len(expected),"actual_solids":len(solids)})
        if body_mapping is not None:
            fingerprint_ready=all(len(canonical_geometry_features(record))>=2 for record in expected)
            if fingerprint_ready:
                matched=match_geometry_records_with_labels(
                    solids,expected,source_id="shape_id",target_id="source_body_index",
                    source_label="source_name",target_label="source_body_name",
                    tolerances={"relative_volume":1e-4,"relative_area":1e-4,"centroid_mm":1e-3,"bounds_mm":1e-3})
                expected_by_index={str(x.get("source_body_index")):x for x in expected}
                solid_by_id={str(x.get("shape_id")):x for x in solids}
                for item in matched["matches"]:
                    solid=solid_by_id[item["source_id"]]; record=expected_by_index[item["target_id"]]
                    solid.update({"source_body_index":record.get("source_body_index"),"source_body_name":record.get("source_body_name"),
                                  'source_path':record.get('source_path'),'source_kind':record.get('source_kind'),
                                  "mapping_method":item["mapping_method"],"mapping_score":item["score"],
                                  "geometry_fingerprint":geometry_fingerprint(solid)})
                if not matched["is_complete"]:
                    mapping_errors.append({"code":"BODY_SOLID_FINGERPRINT_AMBIGUOUS","batch_id":batch_id,
                                           "unresolved":matched["unresolved"]})
            elif len(solids)==len(expected) and not any(x.get('source_kind')=='GEOMETRICAL_SET_ELEMENT' for x in expected):
                for solid,record in zip(solids,expected):
                    solid.update({"source_body_index":record.get("source_body_index"),"source_body_name":record.get("source_body_name"),"mapping_method":"LEGACY_ORDER_FALLBACK_NO_FINGERPRINT"})
                mapping_errors.append({"code":"BODY_SOLID_FINGERPRINT_UNAVAILABLE","batch_id":batch_id})
            else:
                mapping_errors.append({'code':'SURFACE_SOURCE_MAPPING_UNVERIFIED','batch_id':batch_id,
                                       'source_records':expected})
        models[batch_id]=model; batches.append({"batch_id":batch_id,"manifest":manifest})
        if progress: progress({"stage":"BATCH_LOAD_COMPLETE","batch_id":batch_id,"solid_count":len(manifest["shapes"])-1})
    plan=merge_batch_manifests(batches,margin_mm=float(config.get("broad_phase_margin_mm",0.0)))
    source_records={x["shape_id"]:{"source_body_index":x.get("source_body_index"),"source_body_name":x.get("source_body_name"),"batch_id":x.get("batch_id"),"local_shape_id":x.get("local_shape_id"),"mapping_method":x.get("mapping_method")} for x in plan["shapes"] if x.get("source_body_index") is not None}
    monitor_directory=os.environ.get("CATIA_MONITOR_DIRECTORY")
    if monitor_directory:
        registry={"objects":{x['shape_id']:dict(x) for x in plan['shapes']},"catia_bodies":[x for x in (body_mapping or []) if x.get('source_kind')!='GEOMETRICAL_SET_ELEMENT'],
                  'catia_geometry':[x for x in (body_mapping or []) if x.get('source_kind')=='GEOMETRICAL_SET_ELEMENT'],"mapping_errors":mapping_errors,
                  "candidates":plan["broad_phase"]["pairs"]}
        registry_path=Path(monitor_directory)/"registry.json"
        registry_path.write_text(json.dumps(registry,ensure_ascii=False),encoding="utf-8")
        try:
            from .monitor_preview import export_preview
            if preview_valid(monitor_directory,session_identity):
                if progress:progress({'stage':'PREVIEW_CACHE_HIT','operation':'源文件和网格校验通过，复用三维显示网格'})
            else:
                if progress:progress({"stage":"PREVIEW_START","operation":"生成 OCCT 显示网格"})
                export_preview(models,plan,monitor_directory)
                mark_preview(monitor_directory,session_identity)
            if progress:progress({"stage":"PREVIEW_COMPLETE","operation":"三维显示预览已就绪"})
        except Exception as exc:
            if progress:progress({"stage":"PREVIEW_ERROR","message":str(exc)})
    timeout=float(pair_timeout_seconds if pair_timeout_seconds is not None else config.get("pair_timeout_seconds",30)); retry_timeout=float(pair_retry_timeout_seconds if pair_retry_timeout_seconds is not None else config.get("pair_retry_timeout_seconds",90)); max_retries=int(max_pair_retries if max_pair_retries is not None else config.get("max_pair_retries",20)); workers=int(max_pair_workers if max_pair_workers is not None else config.get("max_pair_workers",2));
    contact_tolerance=float(config.get("contact_tolerance_mm",1e-5)); checkpoint_interval_pairs=max(1,int(config.get("checkpoint_interval_pairs",25))); checkpoint_interval_seconds=max(0.1,float(config.get("checkpoint_interval_seconds",10.0))); persistent_workers=bool(config.get("persistent_pair_workers",True))
    if workers<1: raise ValueError("max_pair_workers must be positive")
    facts={}; timed_out=set(); failed=set(); deferred=set(); pairs=plan["broad_phase"]["pairs"][:int(config.get("max_exact_pairs",10000))]
    fingerprint=hashlib.sha256(json.dumps([{"shape_id":x.get("shape_id"),"bounds_mm":x.get("bounds_mm"),"source_name":x.get("source_name")} for x in plan["shapes"]],sort_keys=True,separators=(",",":")).encode()).hexdigest()
    checkpoint=Path(checkpoint_path).resolve() if checkpoint_path else None
    # Adding surface scope need not discard proven unchanged solid-pair facts.
    # Match the entire legacy Body-only fingerprint, not names or bounds alone
    # per individual pair, then admit only existing pairs and applicable facts.
    legacy_shapes=[]
    body_batches={str(x.get('batch_id')) for x in (body_mapping or []) if x.get('source_kind')!='GEOMETRICAL_SET_ELEMENT'}
    for batch in batches:
        if batch['batch_id'] not in body_batches: continue
        records=[x for x in plan['shapes'] if x['batch_id']==batch['batch_id']]
        for kind in ('SOLID','SHELL','FACE'):
            members=[x for x in records if x.get('geometry_kind')==kind]
            if members: legacy_shapes.extend(members);break
    legacy_fingerprint=hashlib.sha256(json.dumps([{'shape_id':x.get('shape_id'),'bounds_mm':x.get('bounds_mm'),'source_name':x.get('source_name')} for x in legacy_shapes],sort_keys=True,separators=(',',':')).encode()).hexdigest() if legacy_shapes else None
    if checkpoint and checkpoint.is_file():
        try:
            saved=json.loads(checkpoint.read_text(encoding="utf-8"))
            if saved.get("geometry_fingerprint")==fingerprint or (legacy_fingerprint is not None and saved.get('geometry_fingerprint')==legacy_fingerprint):
                admitted={tuple(sorted(pair)) for pair in pairs};shape_records={x['shape_id']:x for x in plan['shapes']}
                for item in saved.get("completed_pairs",[]):
                    key=tuple(sorted(item['pair']));fact=item['fact']
                    if key not in admitted: continue
                    if any(not shape_records[name].get('solid_count') for name in key) and not fact.get('surface'): continue
                    facts[key]=fact
        except Exception:
            facts={}
    resumed_count=len(facts)
    if progress: progress({"stage":"CHECKPOINT_LOADED","geometry_fingerprint":fingerprint,"resumed_pair_count":resumed_count,"checkpoint":str(checkpoint) if checkpoint else None})
    class CachedBackend:
        def distance(self,a,b):
            key=tuple(sorted((a,b)))
            if key in timed_out: raise TimeoutError("exact pair timed out")
            if key in failed or key in deferred: raise RuntimeError("exact pair worker failed")
            return facts[key]["distance"]
        def common_volume(self,a,b): return facts[tuple(sorted((a,b)))]["common"]
        def surface_pair_fact(self,a,b,**kwargs): return facts[tuple(sorted((a,b)))]['surface']
    cache_context=nullcontext(str(persistent_cache/'pairs'/session_identity)) if persistent_cache else tempfile.TemporaryDirectory(prefix="occt-pair-cache-")
    with cache_context as directory:
        cache=Path(directory); needed={item for pair in pairs for item in pair}; files={}
        for qualified in sorted(needed):
            item=plan["mapping"][qualified]; path=cache/(qualified.replace("::","_")+".brep")
            pair_file(models[item["batch_id"]],item["local_shape_id"],path); files[qualified]=path
        worker=Path(__file__).resolve().parents[1]/"tools"/"inspect_cached_brep_pair.py"
        worker_server=Path(__file__).resolve().parents[1]/"tools"/"serve_cached_brep_pairs.py"
        pairs=sorted(pairs,key=lambda pair:(files[pair[0]].stat().st_size+files[pair[1]].stat().st_size,tuple(pair)))
        progress_lock=Lock(); checkpoint_lock=Lock()
        worker_pool: Queue[_PersistentPairWorker] | None=None; pair_workers: list[_PersistentPairWorker]=[]
        if persistent_workers:
            worker_pool=Queue()
            for _ in range(workers):
                pair_worker=_PersistentPairWorker(worker_server); pair_workers.append(pair_worker); worker_pool.put(pair_worker)
        checkpoint_state={"dirty_pairs":0,"last_saved_at":perf_counter()}
        def save_checkpoint(*,force=False):
            if not checkpoint: return
            if not force and checkpoint_state["dirty_pairs"]<checkpoint_interval_pairs and perf_counter()-checkpoint_state["last_saved_at"]<checkpoint_interval_seconds: return
            checkpoint.parent.mkdir(parents=True,exist_ok=True); temporary=checkpoint.with_suffix(checkpoint.suffix+".tmp")
            payload={"schema_version":"large-single-part-checkpoint.v1.0","geometry_fingerprint":fingerprint,"completed_pairs":[{"pair":list(key),"fact":value} for key,value in sorted(facts.items())]}
            temporary.write_text(json.dumps(payload,ensure_ascii=False),encoding="utf-8"); os.replace(temporary,checkpoint)
            checkpoint_state["dirty_pairs"]=0; checkpoint_state["last_saved_at"]=perf_counter()
        def emit(event):
            if progress:
                with progress_lock: progress(event)
        def execute(first,second,index,limit,stage,budget_limited=False):
            key=tuple(sorted((first,second))); output=cache/f"pair_{stage}_{index:06d}.json"
            emit({"stage":f"EXACT_PAIR_{stage}_START","index":index,"total":len(pairs),"object_a":first,"object_b":second,"timeout_seconds":limit,"max_workers":workers})
            try:
                if worker_pool is not None:
                    pair_worker=worker_pool.get()
                    try: value=pair_worker.request(files[first],files[second],contact_tolerance,limit)
                    finally: worker_pool.put(pair_worker)
                else:
                    done=subprocess.run([sys.executable,str(worker),str(files[first]),str(files[second]),"--output",str(output),"--common-volume-distance-threshold-mm",str(contact_tolerance)],capture_output=True,text=True,timeout=limit)
                    if done.returncode or not output.is_file(): raise RuntimeError("exact pair worker failed")
                    value=json.loads(output.read_text(encoding="utf-8"))
                with checkpoint_lock:
                    facts[key]=value; checkpoint_state["dirty_pairs"]+=1; save_checkpoint()
                timed_out.discard(key); failed.discard(key)
            except (subprocess.TimeoutExpired,TimeoutError):
                if budget_limited: deferred.add(key)
                else: timed_out.add(key)
            except Exception:
                failed.add(key); timed_out.discard(key)
            emit({"stage":f"EXACT_PAIR_{stage}_COMPLETE","index":index,"total":len(pairs),"status":"DEFERRED" if key in deferred else "TIMEOUT" if key in timed_out else "ERROR" if key in failed else "COMPLETE","max_workers":workers})
        deadline=(perf_counter()+float(run_budget_seconds)) if run_budget_seconds is not None else None
        pause_file=Path(monitor_directory)/'pause-request.json' if monitor_directory else None
        resident=ResidentControl(monitor_directory,emit,lambda:identity(paths,body_mapping)==session_identity) if monitor_directory and os.environ.get('CATIA_OCCT_KEEP_RESIDENT')=='1' else None
        if resident:resident.publish('RUNNING',workers)
        paused=False
        def execute_many(pool,selected,limit,stage):
            nonlocal paused,workers,deadline,worker_pool
            offset=0; running=set()
            while offset<len(selected) or running:
                if pause_file and pause_file.exists() and not paused:
                    paused=True
                    emit({'stage':'PAUSING','operation':'暂停请求已接收，等待当前对象对结束并保存检查点'})
                if paused:
                    if resident:
                        if running:
                            done,running=wait(running,return_when=FIRST_COMPLETED)
                            for future in done:future.result()
                            continue
                        workers,budget=resident.hold(workers,save_checkpoint)
                        if persistent_workers:
                            while len(pair_workers)>workers:pair_workers.pop().close()
                            while len(pair_workers)<workers:pair_workers.append(_PersistentPairWorker(worker_server))
                            worker_pool=Queue()
                            for pair_worker in pair_workers:worker_pool.put(pair_worker)
                        deadline=perf_counter()+budget*60;paused=False
                    else:
                        deferred.update(tuple(sorted(pair)) for pair in selected[offset:])
                        offset=len(selected)
                while offset<len(selected) and len(running)<workers:
                    if deadline is not None and perf_counter()>=deadline:
                        if resident:
                            pause_file.write_text('{}',encoding='utf-8');break
                        deferred.update(tuple(sorted(pair)) for pair in selected[offset:]); offset=len(selected); break
                    effective=limit if deadline is None else max(0.05,min(limit,deadline-perf_counter()))
                    first,second=selected[offset]; offset+=1
                    running.add(pool.submit(execute,first,second,offset,effective,stage,effective<limit))
                if running:
                    done,running=wait(running,return_when=FIRST_COMPLETED)
                    for future in done: future.result()
        pending_pairs=[pair for pair in pairs if tuple(sorted(pair)) not in facts]
        if progress: progress({"stage":"CHECKPOINT_RESUME_PLAN","total_pairs":len(pairs),"resumed_pairs":resumed_count,"pending_pairs":len(pending_pairs)})
        try:
            with ThreadPoolExecutor(max_workers=32 if resident else workers,thread_name_prefix="occt-pair") as pool:
                execute_many(pool,pending_pairs,timeout,"PRIMARY")
                retry_pairs=[] if paused else [pair for pair in pairs if tuple(sorted(pair)) in timed_out][:max_retries]
                if deadline is not None and perf_counter()>=deadline: deferred.update(tuple(sorted(pair)) for pair in retry_pairs); retry_pairs=[]
                if progress: progress({"stage":"EXACT_PAIR_RETRY_PLAN","timeout_count":len(timed_out),"retry_count":len(retry_pairs),"retry_timeout_seconds":retry_timeout})
                execute_many(pool,retry_pairs,retry_timeout,"RETRY")
        finally:
            for pair_worker in pair_workers: pair_worker.close()
            if resident:resident.publish('ENDED',workers)
        with checkpoint_lock: save_checkpoint(force=True)
    manifest={"source_file":"BATCHED_STEP","root_shape_id":"","shapes":plan["shapes"]}
    analysis=analyze_large_single_part(CachedBackend(),manifest,broad_phase_margin_mm=float(config.get("broad_phase_margin_mm",0.0)),contact_tolerance_mm=float(config.get("contact_tolerance_mm",1e-5)),interference_volume_tolerance_mm3=float(config.get("interference_volume_tolerance_mm3",1e-6)),clearance_review_mm=float(config.get("clearance_review_mm",0.0)),max_exact_pairs=int(config.get("max_exact_pairs",10000)),progress=None)
    for item in analysis["errors"]:
        if tuple(sorted((item["object_a"],item["object_b"]))) in deferred: item["code"]="EXACT_PAIR_DEFERRED_BUDGET"
    analysis["coverage_complete"]=not analysis["truncated"] and not analysis["errors"] and not analysis['broad_phase']['skipped']
    if mapping_errors: analysis["errors"].extend(mapping_errors); analysis["coverage_complete"]=False
    findings=[_finding(item,"OCCT_EXACT_BREP_PAIR_ISOLATED",source_records) for item in analysis["findings"]]
    methods=sorted({str(item.get("mapping_method")) for item in source_records.values() if item.get("mapping_method")})
    return {"schema_version":"large-single-part-pair-isolated.v1.0","batch_plan":plan,"analysis":analysis,"findings":[x.to_dict() for x in findings],"body_traceability":{"mapping_method":"+".join(methods) if methods else None,"mapped_solid_count":len(source_records),"mapping_errors":mapping_errors,"is_complete":not mapping_errors and (body_mapping is None or len(source_records)==len(body_mapping))},"pair_timeout_seconds":timeout,"pair_retry_timeout_seconds":retry_timeout,"retry_count":len(retry_pairs),"max_pair_workers":workers,"persistent_pair_workers":persistent_workers,"run_budget_seconds":run_budget_seconds,"budget_deferred_count":len(deferred),"geometry_fingerprint":fingerprint,"resumed_pair_count":resumed_count,"checkpoint_path":str(checkpoint) if checkpoint else None,"mesh_used":False,"source_modified":False}


def build_large_single_part_result(bundle: Mapping[str, Any], *, document: str,
                                   rules: Mapping[str, Any], run_id: str,
                                   generated_at: str) -> dict[str, Any]:
    findings = list(bundle["findings"])
    statuses = ("PASS", "WARN", "FAIL", "NOT_EVALUATED", "EXEMPTED", "ERROR")
    counts = {status: sum(item["status"] == status for item in findings) for status in statuses}
    analysis = bundle["analysis"]
    deferred_errors=sum(item.get("code")=="EXACT_PAIR_DEFERRED_BUDGET" for item in analysis.get("errors") or [])
    counts["ERROR"] += len(analysis.get("errors") or [])-deferred_errors
    counts["NOT_EVALUATED"] += deferred_errors
    not_checked = ([f"{analysis['shell_or_surface_count']}个Shell/Surface未按Solid公共体积裁决"]
                   if analysis["shell_or_surface_count"] else [])
    degraded = ([] if analysis["coverage_complete"] else
                ["候选截断或精确计算异常，内部相交覆盖不完整"])
    total_pairs=int(analysis.get("exact_pair_count") or 0)
    completed_pairs=len(analysis.get("findings") or [])
    error_pairs=len(analysis.get("errors") or [])
    resumed_pairs=min(int(bundle.get("resumed_pair_count") or 0),completed_pairs)
    pending_pairs=max(0,total_pairs-completed_pairs)
    resume_status={"total_candidate_pairs":total_pairs,"completed_pairs":completed_pairs,
      "newly_completed_pairs":max(0,completed_pairs-resumed_pairs),"resumed_pairs":resumed_pairs,
      "timeout_pairs":sum(item.get("code")=="EXACT_PAIR_TIMEOUT" for item in analysis.get("errors") or []),
      "deferred_by_budget_pairs":sum(item.get("code")=="EXACT_PAIR_DEFERRED_BUDGET" for item in analysis.get("errors") or []),
      "failed_pairs":sum(item.get("code") not in {"EXACT_PAIR_TIMEOUT","EXACT_PAIR_DEFERRED_BUDGET"} for item in analysis.get("errors") or []),
      "pending_pairs":pending_pairs,"completion_percent":round(100*completed_pairs/total_pairs,2) if total_pairs else 100.0,
      "needs_resume":bool(pending_pairs or error_pairs or analysis.get("truncated")),
      "checkpoint_path":bundle.get("checkpoint_path"),"geometry_fingerprint":bundle.get("geometry_fingerprint")}
    payload = {
        "schema_version": "1.1.0", "document": document,
        "ruleset_id": rules["ruleset_id"], "applied_rules": dict(rules),
        "run_id": run_id, "generated_at": generated_at,
        "source": {"method": "OCCT_EXACT_BREP_LARGE_SINGLE_PART",
                   "computation_type": "AABB_BROAD_PHASE_EXACT_CANDIDATES",
                   "root_product": document, "truncated": analysis["truncated"],
                   "cleanup_verified": True, "source_saved_by_tool": False},
        "counts": counts, "findings": findings, "large_single_part_analysis": dict(bundle),
        "resume_status":resume_status,
        "confidence_budget": {"checked": ["大型单CATPart内部Solid精确相交"],
                              "not_checked": not_checked, "assumptions": [],
                              "degraded": degraded,
                              "is_complete": not not_checked and not degraded},
        "audit": {"geometry_authority": "OCCT exact B-Rep", "llm_role": "none",
                  "source_model_modified": False, "exceptions": analysis["errors"],
                  "mesh_used": False},
    }
    return filter_result(payload)
