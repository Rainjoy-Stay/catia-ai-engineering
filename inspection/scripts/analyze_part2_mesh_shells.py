from __future__ import annotations
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
path = root / "project" / "artifacts" / "part2_spatial_mesh_20260922.json"
data = json.loads(path.read_text(encoding="utf-8"))
v = data["vertices"]; t = data["triangles"]
parent = list(range(len(v)))
def find(x):
    while parent[x] != x:
        parent[x] = parent[parent[x]]; x = parent[x]
    return x
def union(a, b):
    a, b = find(a), find(b)
    if a != b: parent[b] = a
for a,b,c in t: union(a,b); union(b,c)
groups = {}
for tri in t: groups.setdefault(find(tri[0]), []).append(tri)
rows=[]
for tris in groups.values():
    ids=sorted({i for tri in tris for i in tri}); pts=[v[i] for i in ids]
    volume=0.0
    for a,b,c in tris:
        p,q,r=v[a],v[b],v[c]
        volume += (p[0]*(q[1]*r[2]-q[2]*r[1]) - p[1]*(q[0]*r[2]-q[2]*r[0]) + p[2]*(q[0]*r[1]-q[1]*r[0]))/6.0
    rows.append({"vertices":len(ids),"triangles":len(tris),"signed_volume_mm3":volume,
                 "bounds":{"min":[min(p[i] for p in pts) for i in range(3)],
                           "max":[max(p[i] for p in pts) for i in range(3)]}})
rows.sort(key=lambda x:-x["triangles"])
print(json.dumps({"component_count":len(rows),"components":rows},ensure_ascii=False,indent=2))
