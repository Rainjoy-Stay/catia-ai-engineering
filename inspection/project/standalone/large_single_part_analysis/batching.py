"""Exact global candidate planning across independently converted Body batches."""
from __future__ import annotations
from collections import defaultdict
from typing import Any, Mapping, Sequence
from .analyzer import build_spatial_candidates

def partition_body_names(names: Sequence[str], batch_size: int) -> list[list[str]]:
    if isinstance(batch_size,bool) or batch_size<1: raise ValueError("batch_size must be positive")
    if len(set(names))!=len(names): raise ValueError("Body names must be unique")
    return [list(names[i:i+batch_size]) for i in range(0,len(names),batch_size)]

def merge_batch_manifests(batches: Sequence[Mapping[str,Any]], *, margin_mm: float=0.0)->dict[str,Any]:
    shapes=[]; mapping={}; errors=[]
    for batch in batches:
        batch_id=str(batch.get("batch_id") or "")
        manifest=batch.get("manifest") or {}; root=str(manifest.get("root_shape_id") or "")
        if not batch_id: raise ValueError("batch_id is required")
        for item in manifest.get("shapes",[]):
            local=str(item.get("shape_id") or "")
            if not local or local==root: continue
            qualified=f"{batch_id}::{local}"
            record=dict(item); record["shape_id"]=qualified; record["batch_id"]=batch_id; record["local_shape_id"]=local
            if item.get('face_ids') is not None:
                record['face_ids'] = [f"{batch_id}::{face_id}" for face_id in item['face_ids']]
            shapes.append(record); mapping[qualified]={"batch_id":batch_id,"local_shape_id":local}
        errors.extend(batch.get("errors") or [])
    broad=build_spatial_candidates(shapes,margin_mm=margin_mm)
    groups=defaultdict(list)
    for first,second in broad["pairs"]:
        key=tuple(sorted((mapping[first]["batch_id"],mapping[second]["batch_id"])))
        groups[key].append([first,second])
    return {"schema_version":"large-single-part-batch-plan.v1.0","shape_count":len(shapes),
      "batch_count":len(batches),"mapping":mapping,"shapes":shapes,"broad_phase":broad,
      "candidate_batch_groups":[{"batch_ids":list(key),"pairs":pairs} for key,pairs in sorted(groups.items())],
      "errors":errors,"coverage_complete":not errors and not broad["skipped"],"mesh_used":False}

class MultiBatchBackend:
    """Route qualified shape ids to exact backends without merging STEP roots."""
    def __init__(self, backends: Mapping[str,Any], mapping: Mapping[str,Mapping[str,str]]):
        self.backends=dict(backends); self.mapping=dict(mapping)
    def _resolve(self, shape_id: str):
        item=self.mapping[shape_id]; return self.backends[item["batch_id"]],item["local_shape_id"]
    def distance(self, first: str, second: str):
        a,la=self._resolve(first); b,lb=self._resolve(second)
        if a is b: return a.distance(la,lb)
        return a.distance_to(la,b,lb)
    def common_volume(self, first: str, second: str):
        a,la=self._resolve(first); b,lb=self._resolve(second)
        if a is b: return a.common_volume(la,lb)
        return a.common_volume_to(la,b,lb)
    def surface_pair_fact(self,first: str,second: str,**kwargs):
        a,la=self._resolve(first); b,lb=self._resolve(second)
        if a is b: return a.surface_pair_fact(la,lb,**kwargs)
        combined=type(a)(); combined.register_shape('A',a._shape(la)); combined.register_shape('B',b._shape(lb))
        return combined.surface_pair_fact('A','B',**kwargs)
