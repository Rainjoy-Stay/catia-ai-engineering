from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from mpl_toolkits.mplot3d import proj3d
import numpy as np

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

from OCP.BRep import BRep_Tool
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPControl import STEPControl_Reader
from OCP.TopAbs import TopAbs_FACE, TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer
from OCP.TopLoc import TopLoc_Location
from OCP.TopoDS import TopoDS


ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "project" / "output" / "runs" / "STEP-ONLY-20260923-FIRST"
STEP = ROOT / "project" / "artifacts" / "full_project_check_step_20260923" / "MiniEngine_Current_D6_R15_G3_20260923.stp"
CHECK = RUN / "check.json"
OUT = RUN / "evidence"


def load_solids():
    reader = STEPControl_Reader()
    if reader.ReadFile(str(STEP)) != IFSelect_RetDone or reader.TransferRoots() <= 0:
        raise RuntimeError("STEP read failed")
    root = reader.OneShape()
    exp = TopExp_Explorer(root, TopAbs_SOLID)
    solids = []
    while exp.More():
        solids.append(exp.Current())
        exp.Next()
    return solids


def triangles(shape, deflection=0.8):
    BRepMesh_IncrementalMesh(shape, deflection, False, 0.35, True).Perform()
    result = []
    exp = TopExp_Explorer(shape, TopAbs_FACE)
    while exp.More():
        face = TopoDS.Face_s(exp.Current())
        loc = TopLoc_Location()
        tri = BRep_Tool.Triangulation_s(face, loc)
        if tri is not None:
            trsf = loc.Transformation()
            nodes = [tri.Node(i).Transformed(trsf) for i in range(1, tri.NbNodes() + 1)]
            for i in range(1, tri.NbTriangles() + 1):
                a, b, c = tri.Triangle(i).Get()
                result.append([(nodes[j-1].X(), nodes[j-1].Y(), nodes[j-1].Z()) for j in (a, b, c)])
        exp.Next()
    return result


def projected_box(fig, ax, points, pad=14):
    fig.canvas.draw()
    coords = []
    for x, y, z in points:
        u, v, _ = proj3d.proj_transform(x, y, z, ax.get_proj())
        coords.append(ax.transData.transform((u, v)))
    arr = np.asarray(coords)
    x0, y0 = arr.min(axis=0) - pad
    x1, y1 = arr.max(axis=0) + pad
    inv = fig.transFigure.inverted()
    (fx0, fy0), (fx1, fy1) = inv.transform([(x0, y0), (x1, y1)])
    return fx0, fy0, fx1-fx0, fy1-fy0


def shape_bbox_points(tris):
    arr = np.asarray(tris).reshape(-1, 3)
    lo, hi = arr.min(axis=0), arr.max(axis=0)
    return [(x, y, z) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]


def render(issue, solids, view_name, elev, azim):
    a_id, b_id = issue["metadata"]["geometry_object_a"], issue["metadata"]["geometry_object_b"]
    ia, ib = int(a_id.rsplit("_", 1)[1]) - 1, int(b_id.rsplit("_", 1)[1]) - 1
    ta, tb = triangles(solids[ia]), triangles(solids[ib])
    fig = plt.figure(figsize=(12, 8), dpi=150, facecolor="white")
    ax = fig.add_subplot(111, projection="3d")
    ax.add_collection3d(Poly3DCollection(ta, facecolor="#4C78A8", edgecolor="#24435C", linewidth=0.12, alpha=0.38))
    ax.add_collection3d(Poly3DCollection(tb, facecolor="#F2A541", edgecolor="#805111", linewidth=0.12, alpha=0.52))
    all_pts = np.asarray(ta + tb).reshape(-1, 3)
    lo, hi = all_pts.min(axis=0), all_pts.max(axis=0)
    center, span = (lo + hi) / 2, max((hi - lo).max(), 1.0) * 0.58
    ax.set_xlim(center[0]-span, center[0]+span); ax.set_ylim(center[1]-span, center[1]+span); ax.set_zlim(center[2]-span, center[2]+span)
    ax.set_box_aspect((1, 1, 1)); ax.view_init(elev=elev, azim=azim)
    ax.set_xlabel("X mm"); ax.set_ylabel("Y mm"); ax.set_zlabel("Z mm")
    ax.set_title(f"{issue['issue_id']}  {a_id} ↔ {b_id}\n蓝色=对象A  橙色=对象B  红框=精确几何定位区域", fontsize=12, pad=16)
    evidence_points = []
    if issue["status"] == "FAIL":
        common = BRepAlgoAPI_Common(solids[ia], solids[ib]).Shape()
        tc = triangles(common, 0.35)
        if tc:
            ax.add_collection3d(Poly3DCollection(tc, facecolor="#D7191C", edgecolor="#8B0000", linewidth=0.35, alpha=0.95))
            evidence_points = shape_bbox_points(tc)
    else:
        geom = next(e["data"] for e in issue["evidence"] if e.get("kind") == "GEOMETRY")
        # Closest points are copied from the exact pair record below in main.
        p1, p2 = geom["closest_point_a_mm"], geom["closest_point_b_mm"]
        ax.plot([p1[0], p2[0]], [p1[1], p2[1]], [p1[2], p2[2]], color="#D7191C", linewidth=4, marker="o", markersize=5)
        delta = max(float(issue["measured_value"]), 1.0) * 0.5
        evidence_points = [tuple(np.asarray(p1)+d) for d in ((-delta,-delta,-delta),(delta,delta,delta))] + [tuple(np.asarray(p2)+d) for d in ((-delta,-delta,-delta),(delta,delta,delta))]
    if evidence_points:
        x, y, w, h = projected_box(fig, ax, evidence_points)
        rect = Rectangle((x, y), w, h, transform=fig.transFigure, fill=False, edgecolor="#D7191C", linewidth=3.5)
        fig.patches.append(rect)
        fig.text(x, min(0.97, y+h+0.008), issue["issue_id"], color="white", fontsize=9,
                 bbox=dict(facecolor="#D7191C", edgecolor="#D7191C", pad=3))
    ax.text2D(0.02, 0.02, f"实测: {issue['measured_value']:.6g} {issue['unit']}\n定位依据: OCCT 精确 B-Rep 公共体积/最近点坐标\n网格仅用于显示，不参与判定", transform=ax.transAxes, fontsize=9,
              bbox=dict(facecolor="white", edgecolor="#999999", alpha=0.9))
    path = OUT / f"{issue['issue_id']}_{view_name}_marked.png"
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


def main():
    payload = json.loads(CHECK.read_text(encoding="utf-8"))
    exact = json.loads((RUN / "step_exact.json").read_text(encoding="utf-8"))
    pair_index = {(x["object_a"], x["object_b"]): x for x in exact["pair_facts"]}
    solids = load_solids(); OUT.mkdir(parents=True, exist_ok=True)
    for issue in payload["findings"]:
        if issue["status"] not in {"FAIL", "WARN"}:
            continue
        a, b = issue["metadata"]["geometry_object_a"], issue["metadata"]["geometry_object_b"]
        fact = pair_index.get((a, b)) or pair_index.get((b, a))
        geom = next(e["data"] for e in issue["evidence"] if e.get("kind") == "GEOMETRY")
        if fact:
            geom["closest_point_a_mm"] = fact["closest_point_a_mm"]
            geom["closest_point_b_mm"] = fact["closest_point_b_mm"]
        for view, elev, azim in (("isometric", 24, -48), ("front", 0, -90)):
            path = render(issue, solids, view, elev, azim)
            issue["evidence"].append({
                "kind": "SCREENSHOT", "path": str(path),
                "description": f"{view} 精确定位图：红框由公共体积或最近点坐标投影生成；网格仅用于显示",
                "data": {"view": view, "location_method": "OCCT_EXACT_BREP_COORDINATE_PROJECTION"},
            })
    payload["audit"]["screenshot_evidence_missing"] = []
    payload["audit"]["screenshot_method"] = "STEP_ONLY_OCCT_EXACT_LOCATION_WITH_TESSELLATED_DISPLAY"
    CHECK.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"rendered {len(list(OUT.glob('*_marked.png')))} images")


if __name__ == "__main__":
    main()
