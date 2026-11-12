import json,sys,math,hashlib
from pathlib import Path
from collections import defaultdict,Counter
import numpy as np
W=Path(__file__).resolve().parents[3];O=Path(sys.argv[1]).resolve()
sys.path.insert(0,str(W/'project'))
from catia_checker.occt_brep import OCCTBRepModel
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_FACE
from OCP.TopoDS import TopoDS
from OCP.BRepAdaptor import BRepAdaptor_Surface
def circle(points):
 p=np.array(points);mean=p.mean(0);_,s,vt=np.linalg.svd(p-mean,full_matrices=False);xy=(p-mean)@vt[:2].T
 A=np.column_stack([2*xy,np.ones(len(p))]);x=np.linalg.lstsq(A,(xy*xy).sum(1),rcond=None)[0];r=math.sqrt(max(0,x[2]+x[0]**2+x[1]**2));c=mean+x[:2]@vt[:2]
 conic=np.linalg.lstsq(np.column_stack([xy[:,0]**2,xy[:,0]*xy[:,1],xy[:,1]**2,xy[:,0],xy[:,1]]),np.ones(len(p)),rcond=None)[0]
 Q=np.array([[conic[0],conic[1]/2],[conic[1]/2,conic[2]]]);ec=-.5*np.linalg.solve(Q,conic[3:]);scale=1+ec@Q@ec;ev=np.linalg.eigvalsh(Q/scale)
 axes=1/np.sqrt(np.maximum(ev,1e-20));ellipse_error=float(np.max(np.abs(np.sqrt(np.maximum(np.einsum('ni,ij,nj->n',xy-ec,Q/scale,xy-ec),0))-1))*min(axes))
 angles=np.sort(np.arctan2(xy[:,1]-ec[1],xy[:,0]-ec[0]));gap=float(np.max(np.diff(np.r_[angles,angles[0]+2*math.pi])))
 return c,r,float(np.max(np.abs(np.linalg.norm(p-c,axis=1)-r))),float(np.max(np.abs((p-mean)@vt[2]))),ellipse_error,float(max(axes)/min(axes)),gap
def radius(a,b,c):
 u=b-a;v=c-b;w=c-a;cross=np.linalg.norm(np.cross(u,v));turn=math.degrees(math.acos(float(np.clip(np.dot(u,v)/max(1e-30,np.linalg.norm(u)*np.linalg.norm(v)),-1,1))))
 return np.linalg.norm(u)*np.linalg.norm(v)*np.linalg.norm(w)/(2*cross) if cross>1e-15 else 1e30,turn
entities=json.loads((O/'all_entity_caches.json').read_text(encoding='utf8'));audit=[];routes=[]
for ent in entities:
 m=OCCTBRepModel();m.load_brep(ent['shape_id'],ent['cache_file']);e=TopExp_Explorer(m._shape(ent['shape_id']),TopAbs_FACE);groups=defaultdict(list);face_count=0;planes=0
 while e.More():
  face_count+=1;a=BRepAdaptor_Surface(TopoDS.Face_s(e.Current()));kind=str(a.GetType()).split('.')[-1]
  if kind=='GeomAbs_Plane':planes+=1
  if kind=='GeomAbs_BSplineSurface':
   for direction in ['V','U']:
    lo,hi=(a.FirstVParameter(),a.LastVParameter()) if direction=='V' else (a.FirstUParameter(),a.LastUParameter())
    if math.isfinite(lo+hi) and hi>lo:groups[(direction,round(lo,6),round(hi,6))].append((face_count,a))
  e.Next()
 item={'shape_id':ent['shape_id'],'geometry_kind':ent['geometry_kind'],'source_index':ent['index'],'face_count':face_count,'attempts':[]}
 for (direction,lo,hi),group in groups.items():
  if len(group)<2:
   a=group[0][1]
   if not (a.IsUClosed() if direction=='V' else a.IsVClosed()):continue
  centers=[];radii=[];residuals=[];planarity=[];ellipse_errors=[];axis_ratios=[];angle_gaps=[]
  stations=int(__import__("os").environ.get("CATIA_ROUTE_STATIONS","201"))
  step=max(1,round((stations-1)/40))
  try:
   for t in np.linspace(.001,.999,stations):
    points=[]
    for _,a in group:
     start,end=(a.FirstVParameter(),a.LastVParameter()) if direction=='V' else (a.FirstUParameter(),a.LastUParameter());q=start+t*(end-start)
     c0,c1=(a.FirstUParameter(),a.LastUParameter()) if direction=='V' else (a.FirstVParameter(),a.LastVParameter())
     for s in np.linspace(c0,c1,17):points.append(a.Value(float(s),float(q)).Coord() if direction=='V' else a.Value(float(q),float(s)).Coord())
    c,r,err,flat,ellipse_err,axis_ratio,gap=circle(points);centers.append(c);radii.append(r);residuals.append(err);planarity.append(flat);ellipse_errors.append(ellipse_err);axis_ratios.append(axis_ratio);angle_gaps.append(gap)
  except (ValueError,np.linalg.LinAlgError,OverflowError) as exc:
   item['attempts'].append({'direction':direction,'face_indices':[i for i,_ in group],'accepted':False,'error':str(exc)});continue
  c=np.array(centers);length=float(np.linalg.norm(np.diff(c,axis=0),axis=1).sum());diameter=float(2*np.median(radii));variation=float((max(radii)-min(radii))/max(1e-20,np.median(radii)));err=max(residuals);flat=max(planarity)
  round_section=err<max(.005,diameter*.005);oval_section=max(ellipse_errors)<max(.005,diameter*.015) and err<diameter*.02 and max(axis_ratios)<1.15
  # A pipe can be embedded in a composite Body together with fittings. Do not require all faces to belong to the sweep.
  accepted=diameter>0 and length/diameter>10 and variation<.03 and (round_section or oval_section) and flat<max(.005,diameter*.005) and max(angle_gaps)<.5
  attempt={'direction':direction,'face_indices':[i for i,_ in group],'diameter_mm':diameter,'length_mm':length,'radius_relative_range':variation,'max_circle_residual_mm':err,'max_ellipse_residual_mm':max(ellipse_errors),'max_section_axis_ratio':max(axis_ratios),'max_section_angular_gap_radians':max(angle_gaps),'section_kind':'CIRCULAR' if round_section else 'SLIGHTLY_OVAL','max_section_planarity_error_mm':flat,'accepted':accepted};item['attempts'].append(attempt)
  if not accepted:continue
  bends=[]
  for i in range(2*step,stations-2*step):
   r1,turn=radius(c[i-step],c[i],c[i+step]);r2,turn2=radius(c[i-2*step],c[i],c[i+2*step]);delta=abs(r1-r2)/max(r1,r2)
   if turn>1 and turn2>2 and delta<.1:bends.append({'station':i,'center_mm':c[i].tolist(),'radius_mm':float(r1),'wider_window_radius_mm':float(r2),'relative_window_difference':float(delta)})
  route={**attempt,'shape_id':ent['shape_id'],'source_body_index':ent['index'],'source_name':ent['name'],'source_path':ent['source_path'],'source_sha256':hashlib.sha256(Path(ent['cache_file']).read_bytes()).hexdigest(),'centerline_points_mm':c.tolist(),'bend_samples':bends,'minimum_stable_bend_radius_mm':min((b['radius_mm'] for b in bends),default=None),'classification':'SWEPT_CIRCULAR_TUBING_GEOMETRY','bore_status':'NOT_PROVEN_IMPORTED_END_CAPS','engineering_radius_status':'NOT_EVALUATED_NO_SPEC','method':'对模型曲面两种参数方向扫描；沿路线201站、每片截面17点拟合3D圆，校核半径恒定、平面性和截面周向覆盖。中心线由截面圆心重建；局部半径用两种采样窗口交叉核对。'}
  route['route_id']=ent['shape_id']+'_ROUTE_'+str(len([x for x in routes if x['shape_id']==ent['shape_id']])+1)
  route['composite_body_region']=len(group)<face_count-4
  routes.append(route)
 audit.append(item);print(ent['shape_id'],'accepted',any(a['accepted'] for a in item['attempts']),flush=True)
result={'station_count':stations,'scope':'当前空间框全部登记实体与面壳；模型几何统一扫描，无截图位置输入','scanned_object_count':len(audit),'routes':routes,'scan_audit':audit,'limitations':'外形管路已识别；导入模型内腔和工程用途未独立确认。半径为稳定采样估计；没有规格或材料下限，不判半径合规通过。'}
(O/'样条管路中心线检查.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
pipes=json.loads((O/'pipe-recognition.json').read_text(encoding='utf8'))
for r in pipes:
 route=next((x for x in routes if x['source_body_index']==r['source_body_index']),None)
 if route:r['candidate']={'geometry_kind':'SWEPT_CIRCULAR_TUBING_GEOMETRY','outer_diameter_mm':route['diameter_mm'],'length_mm':route['length_mm'],'length_diameter_ratio':route['length_mm']/route['diameter_mm']};r['swept_route']=route
(O/'pipe-recognition.json').write_text(json.dumps(pipes,ensure_ascii=False,indent=2),encoding='utf8')
check=json.loads((O/'check.json').read_text(encoding='utf8'));check['pipe_recognition']=pipes;check['swept_route_review']=result;(O/'check.json').write_text(json.dumps(check,ensure_ascii=False,indent=2),encoding='utf8')
print('ROUTES',[(r['shape_id'],r['diameter_mm'],r['length_mm'],r['minimum_stable_bend_radius_mm']) for r in routes],flush=True)
