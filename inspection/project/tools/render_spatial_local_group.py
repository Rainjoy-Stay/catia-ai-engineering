"""Triangulated visual support; measurements remain exact BREP evidence."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from OCP.BRep import BRep_Tool
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.TopLoc import TopLoc_Location
from OCP.TopAbs import TopAbs_FACE
from OCP.TopoDS import TopoDS
from catia_checker.occt_brep import OCCTBRepModel,_subshapes
from tools.review_surface_recovery_pilot import ROOT,digest

def main():
    out=ROOT/'artifacts/spatial_local_15'; scan=json.loads((out/'exterior_scan/batch_exterior_scan.json').read_text(encoding='utf-8'))
    result=json.loads((out/'local_analysis.json').read_text(encoding='utf-8'))
    fig=plt.figure(figsize=(11,7)); ax=fig.add_subplot(111,projection='3d'); model=OCCTBRepModel()
    for index,body in enumerate(scan['records']):
        record=body['records'][0]; sid=record['solid']['shape_id']; cache=Path(record['cache_file']); before=digest(cache)
        model.load_brep(sid,cache); shape=model._shape(sid); BRepMesh_IncrementalMesh(shape,.025,False,.25,True)
        triangles=[]
        for face in _subshapes(shape,TopAbs_FACE):
            location=TopLoc_Location(); mesh=BRep_Tool.Triangulation_s(TopoDS.Face_s(face),location)
            if mesh is None: continue
            for i in range(1,mesh.NbTriangles()+1):
                nodes=mesh.Triangle(i).Get(); points=[]
                for n in nodes:
                    p=mesh.Node(n).Transformed(location.Transformation()); points.append([p.X(),p.Y(),p.Z()])
                triangles.append(points)
        color=plt.get_cmap('tab20')(index)
        ax.add_collection3d(Poly3DCollection(triangles,facecolor=color,edgecolor='none',alpha=.75))
        x,y,z=record['solid']['centroid_mm']; ax.text(x,y,z,str(body['source_body_index']),fontsize=9,color='black')
        assert digest(cache)==before
    lo=result['bounds_mm']['min']; hi=result['bounds_mm']['max']; pad=.7
    ax.set_xlim(lo[0]-pad,hi[0]+pad); ax.set_ylim(lo[1]-pad,hi[1]+pad); ax.set_zlim(lo[2]-pad,hi[2]+pad)
    ax.set_box_aspect([hi[i]-lo[i]+2*pad for i in range(3)])
    ax.view_init(elev=34,azim=-65); ax.set_xlabel('X (mm)'); ax.set_ylabel('Y (mm)'); ax.set_zlabel('Z (mm)')
    ax.set_title('One spatial neighborhood: 12 Bodies / 66 exact pairs',pad=18)
    fig.text(.5,.02,'Numbers are CATIA Body indices. Triangulated preview only; interference uses exact BREP.',ha='center',fontsize=10)
    fig.savefig(out/'局部实体预览.png',dpi=180,bbox_inches='tight'); plt.close(fig)

if __name__=='__main__': main()
