"""Render one overview and every overlap/contact pair in a spatial-box run."""
from __future__ import annotations
import json, sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from OCP.BRep import BRep_Tool
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.TopLoc import TopLoc_Location
from OCP.TopAbs import TopAbs_FACE
from OCP.TopoDS import TopoDS
from catia_checker.occt_brep import OCCTBRepModel, _subshapes

def triangles(shape):
    BRepMesh_IncrementalMesh(shape, .035, False, .3, True); result=[]
    for face in _subshapes(shape, TopAbs_FACE):
        loc=TopLoc_Location(); mesh=BRep_Tool.Triangulation_s(TopoDS.Face_s(face), loc)
        if mesh is None: continue
        for i in range(1, mesh.NbTriangles()+1):
            pts=[]
            for n in mesh.Triangle(i).Get():
                p=mesh.Node(n).Transformed(loc.Transformation());pts.append([p.X(),p.Y(),p.Z()])
            result.append(pts)
    return result

def frame(ax, items, pad=.5):
    lo=[min(x['solid']['bounds_mm']['min'][i] for x in items) for i in range(3)]
    hi=[max(x['solid']['bounds_mm']['max'][i] for x in items) for i in range(3)]
    spans=[max(hi[i]-lo[i],.5) for i in range(3)]
    ax.set_xlim(lo[0]-pad,hi[0]+pad);ax.set_ylim(lo[1]-pad,hi[1]+pad);ax.set_zlim(lo[2]-pad,hi[2]+pad)
    ax.set_box_aspect([s+2*pad for s in spans]);ax.set_xlabel('X mm');ax.set_ylabel('Y mm');ax.set_zlabel('Z mm');ax.view_init(27,-58)

def frame_bounds(ax, bounds, pad=.5):
    lo,hi=bounds['min'],bounds['max'];spans=[max(hi[i]-lo[i],.5) for i in range(3)]
    ax.set_xlim(lo[0]-pad,hi[0]+pad);ax.set_ylim(lo[1]-pad,hi[1]+pad);ax.set_zlim(lo[2]-pad,hi[2]+pad)
    ax.set_box_aspect([s+2*pad for s in spans]);ax.set_xlabel('X mm');ax.set_ylabel('Y mm');ax.set_zlabel('Z mm');ax.view_init(27,-58)

def wire_box(ax,bounds,color='#FFD400'):
    lo,hi=bounds['min'],bounds['max'];pts=[[x,y,z] for x in (lo[0],hi[0]) for y in (lo[1],hi[1]) for z in (lo[2],hi[2])]
    for i,p in enumerate(pts):
        for j,q in enumerate(pts):
            if j>i and sum(p[k]!=q[k] for k in range(3))==1: ax.plot([p[0],q[0]],[p[1],q[1]],[p[2],q[2]],color=color,lw=2.2)

def main():
    out=Path(sys.argv[1]);imgdir=out/'interference_screenshots';imgdir.mkdir(exist_ok=True)
    bodies=json.loads((out/'box_body_caches.json').read_text(encoding='utf-8'));analysis=json.loads((out/'spatial_box_analysis.json').read_text(encoding='utf-8'))
    model=OCCTBRepModel();by={}
    for x in bodies:model.load_brep(x['shape_id'],Path(x['cache_file']));by[x['index']]=x
    # overview
    fig=plt.figure(figsize=(11,7));ax=fig.add_subplot(111,projection='3d')
    for k,x in enumerate(bodies):
        if x['index']==1: continue
        alpha=.78
        ax.add_collection3d(Poly3DCollection(triangles(model._shape(x['shape_id'])),facecolor=plt.get_cmap('tab20')(k),edgecolor='none',alpha=alpha))
        bb=x['solid']['bounds_mm'];c=[(bb['min'][i]+bb['max'][i])/2 for i in range(3)];ax.text(*c,str(x['index']),fontsize=8)
    frame_bounds(ax,analysis['box_bounds_mm'],.35);ax.set_title('Expanded spatial box: 11 intersecting Bodies')
    fig.text(.5,.02,'Labels are CATIA Body indices. Exact decisions use B-Rep, not the tessellated view.',ha='center')
    fig.savefig(out/'空间框选总览.png',dpi=180,bbox_inches='tight');plt.close(fig)
    selected=[]
    for r in analysis['records']:
        vol=r.get('fact',{}).get('intersection_volume_mm3',0);cat=r['decision']['category']
        if vol<=0 and cat!='CONTACT_OR_COPLANAR':continue
        a,b=by[r['body_a']],by[r['body_b']];fig=plt.figure(figsize=(9.2,6.4));ax=fig.add_subplot(111,projection='3d')
        if a['index']!=1:
            ax.add_collection3d(Poly3DCollection(triangles(model._shape(a['shape_id'])),facecolor='#FFD400',edgecolor='#6B5A00',linewidth=.08,alpha=.72))
        ax.add_collection3d(Poly3DCollection(triangles(model._shape(b['shape_id'])),facecolor='#E53935',edgecolor='#6E1110',linewidth=.12,alpha=.68))
        common=r.get('overlap_evidence',{}).get('common_bounds_mm')
        if a['index']==1 and common: wire_box(ax,common)
        if a['index']==1: frame(ax,[b],.6)
        elif vol>0 and common: frame_bounds(ax,common,.45)
        else: frame(ax,[a,b],.35)
        kind='Positive-volume overlap' if vol>0 else 'Contact / coplanar'
        ax.set_title(f"{kind}: Body {a['index']} / Body {b['index']}\n{a['name']}  |  {b['name']}\ncommon volume = {vol:.9g} mm3")
        ax.legend(handles=[Line2D([0],[0],marker='s',color='w',label=f"Body {a['index']}",markerfacecolor='#FFD400',markersize=12),Line2D([0],[0],marker='s',color='w',label=f"Body {b['index']}",markerfacecolor='#E53935',markersize=12)],loc='upper right')
        target=imgdir/f"PAIR_{a['index']}_{b['index']}.png";fig.savefig(target,dpi=180,bbox_inches='tight');plt.close(fig)
        selected.append({'body_a':a['index'],'body_b':b['index'],'category':cat,'volume_mm3':vol,'image':str(target.resolve())})
    (out/'screenshot_index.json').write_text(json.dumps(selected,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'screenshot_count':len(selected)},ensure_ascii=False))
if __name__=='__main__':main()
