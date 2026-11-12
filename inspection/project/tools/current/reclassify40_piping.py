import json,sys,math,hashlib
from pathlib import Path
from collections import Counter
W=Path(__file__).resolve().parents[3];O=Path(sys.argv[1]).resolve();P=W/'project';sys.path.insert(0,str(P))
from catia_checker.occt_brep import OCCTBRepModel,_mass_properties
from standalone.step_pipe_semantics.exterior import straight_exterior_candidate,curved_exterior_candidate
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_FACE,TopAbs_IN
from OCP.TopoDS import TopoDS
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepClass3d import BRepClass3d_SolidClassifier
from OCP.gp import gp_Pnt
entities=json.loads((O/'all_entity_caches.json').read_text(encoding='utf8'));old=json.loads((O/'pipe-recognition.json').read_text(encoding='utf8'));byindex={r['source_body_index']:r for r in old};rows=[];updates=[]
for entity in entities:
 if entity['geometry_kind']!='SOLID':continue
 m=OCCTBRepModel();sid=entity['shape_id'];m.load_brep(sid,entity['cache_file']);shape=m._shape(sid);record=m.describe(sid);types=[];tori=[];cylinders=[];e=TopExp_Explorer(shape,TopAbs_FACE)
 while e.More():
  face=TopoDS.Face_s(e.Current());a=BRepAdaptor_Surface(face);kind=str(a.GetType()).split('.')[-1];types.append(kind)
  if kind=='GeomAbs_Torus':
   t=a.Torus();tori.append({'major_radius_mm':t.MajorRadius(),'minor_radius_mm':t.MinorRadius(),'face_index':len(types)})
  if kind=='GeomAbs_Cylinder':cylinders.append(a.Cylinder().Radius())
  e.Next()
 r=byindex[entity['index']];candidate=r['candidate'];review={'shape_id':sid,'source_body_index':entity['index'],'name':entity['name'],'source_sha256':hashlib.sha256(Path(entity['cache_file']).read_bytes()).hexdigest(),'face_types':dict(Counter(types)),'cylinder_radii_mm':sorted(set(round(x,8) for x in cylinders)),'torus_supports':tori,'classification':'UNDETERMINED_NON_PIPE_COMPOSITE','reason':'复合几何未证明贯通内腔、开口端口或连续圆截面路线；不得把孔口圆角作为管弯。','centerline_status':'NOT_RECONSTRUCTED','bend_radius_check':'NOT_EVALUATED_NO_CONFIRMED_ROUTE'}
 if candidate['geometry_kind']=='STRAIGHT_CYLINDRICAL_EXTERIOR_CANDIDATE':
  diameter=candidate['outer_diameter_mm'];length=candidate['length_mm'];expected=math.pi*(diameter/2)**2*length;volume=_mass_properties(shape)['volume_mm3'];fill=volume/expected;ends=candidate['end_plane_axis_centers_mm'];mid=[sum(x)/2 for x in zip(*ends)];state=BRepClass3d_SolidClassifier(shape,gp_Pnt(*mid),1e-7).State();solid=math.isclose(fill,1,rel_tol=1e-6,abs_tol=1e-7) and state==TopAbs_IN
  review.update(full_cylinder_volume_mm3=expected,measured_volume_mm3=volume,volume_fill_ratio=fill,axis_midpoint_state=str(state),axis_endpoints_mm=ends,outer_diameter_mm=diameter,length_mm=length)
  if solid:
   review.update(classification='EXCLUDED_SOLID_PIN_ROD_OR_DISC',reason='实体体积与完整实心圆柱一致，轴心采样位于材料内部，两端为封闭平面；无贯通流道。按实心销杆或圆盘类排除管路，具体紧固件用途未恢复。',centerline_status='SOLID_SYMMETRY_AXIS_ONLY_NOT_PIPE_ROUTE',bend_radius_check='NOT_APPLICABLE_EXCLUDED_NON_PIPE')
   candidate={**candidate,'geometry_kind':'UNDETERMINED','reason':'EXCLUDED_SOLID_PIN_ROD_OR_DISC','excluded_from_pipe_recognition':True,'previous_exterior_kind':r['candidate']['geometry_kind']}
 else:
  # Exact analytic circular-bend recognition: require whole-body end/area/volume consistency.
  if len(types)<=12 and tori:
   faces=[m.describe(f) for f in m.solid_face_provenance(sid)['face_ids']];bend=curved_exterior_candidate(record,faces)
   review['analytic_bend_attempt']=bend
   if bend['geometry_kind']!='UNDETERMINED':
    review.update(classification='CURVED_EXTERIOR_REQUIRES_BORE_PROOF',centerline_status='ANALYTIC_CENTERLINE_CANDIDATE',centerline_bend_radius_mm=bend['centerline_bend_radius_mm'],reason='全对象圆弧外形一致，但须证明内腔与开口端口才能作为管路进行半径合规判定。');candidate=bend
  elif tori:review['analytic_bend_rejection']='COMPOSITE_WITH_LOCAL_TORI_NOT_SINGLE_PIPE_BEND'
 r.update(candidate=candidate,valid=record['valid'],face_count=record['face_count'],pipe_review=review);updates.append(r);rows.append(review);print(entity['index'],review['classification'],'tori',len(tori),flush=True)
result={'scope':'本轮40个实体；不把用户允许的开放参考面认作管路','reviewed_solid_count':len(rows),'counts':dict(Counter(r['classification'] for r in rows)),'confirmed_pipe_count':0,'confirmed_centerline_count':0,'bend_radius_measurements':[],'rows':rows,'limits':'缺少工程管路用途和规格；不能用局部圆角大半径冒充中心线弯曲半径。'}
(O/'pipe-recognition.json').write_text(json.dumps(updates,ensure_ascii=False,indent=2),encoding='utf8');(O/'管路复核及中心线半径检查.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');c=json.loads((O/'check.json').read_text(encoding='utf8'));c['pipe_recognition']=updates;c['pipe_review']=result;(O/'check.json').write_text(json.dumps(c,ensure_ascii=False,indent=2),encoding='utf8');print('PIPE_REVIEW_COMPLETE',result['counts'],flush=True)
