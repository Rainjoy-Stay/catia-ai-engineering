"""Generic report from current facts; preserves unresolved coverage explicitly."""
import json,sys,csv,zipfile,hashlib
from pathlib import Path
from collections import Counter
from PIL import Image,ImageDraw
import numpy as np
from docx import Document
from docx.shared import Cm
from docx.oxml.ns import qn
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader
O=Path(sys.argv[1]).resolve()
read=lambda n:json.loads((O/n).read_text(encoding='utf8'))
a=read('spatial_box_analysis.json');check=read('check.json');config=read('run-config.json');entities=read('all_entity_caches.json');routes=check.get('swept_route_review',{}).get('routes',[])
cap=read('capture-audit.json') if (O/'capture-audit.json').exists() else {'jobs':[],'restored':False}
pdfmetrics.registerFont(TTFont('CN','C:/Windows/Fonts/msyh.ttc'))
c=canvas.Canvas(str(O/'report.pdf'),pagesize=(595.28,841.89));doc=Document();doc.styles['Normal'].font.name='Microsoft YaHei';doc.styles['Normal']._element.rPr.rFonts.set(qn('w:eastAsia'),'Microsoft YaHei')
y=780
def page():
 global y
 c.setFont('CN',8);c.drawString(40,25,O.name+' | '+str(c.getPageNumber()));c.showPage();y=780
def line(s,heading=False):
 global y
 if y<65:page()
 if heading:doc.add_heading(str(s),level=2)
 else:doc.add_paragraph(str(s))
 size=14 if heading else 9
 chunks=[];current=''
 for char in str(s):
  if pdfmetrics.stringWidth(current+char,'CN',size)>515 and current:chunks.append(current);current=''
  current+=char
 if current:chunks.append(current)
 for chunk in chunks:
  if y<65:page()
  c.setFont('CN',size);c.drawString(40,y,chunk);y-=23 if heading else 16
def dual(job):
 global y
 if y<370:page()
 pictures=[]
 for role in ('context_image','detail_image'):
  raw=Path(job.get(role,''))
  if not raw.is_file():line('截图缺失：'+role);return
  im=Image.open(raw).convert('RGB');w,h=im.size
  # Same viewport rectangle for both; exclude tree, compass and bottom axes.
  crop=(int(w*.18),int(h*.20),int(w*.88),int(h*.92))
  im=im.crop(crop)
  locator=Path(job.get(role.replace('_image','_locator'),''))
  if locator.is_file():
   arr=np.asarray(Image.open(locator).convert('RGB').crop(crop));mask=(arr[:,:,0]>180)&(arr[:,:,1]>65)&(arr[:,:,1]<210)&(arr[:,:,2]<130);yy,xx=np.where(mask)
   if len(xx)>=30:
    box=(max(0,int(xx.min())-10),max(0,int(yy.min())-10),min(im.width-1,int(xx.max())+10),min(im.height-1,int(yy.max())+10));ImageDraw.Draw(im).rectangle(box,outline=(235,20,25),width=3)
   else:line('目标定位像素不足，定位框未生成，需复核截图。')
  output=O/'screenshots';output.mkdir(exist_ok=True)
  path=output/(job['id']+'_'+role+'.png');im.save(path);pictures.append(path)
 table=doc.add_table(rows=1,cols=2)
 for idx,path in enumerate(pictures):
  im=Image.open(path);ratio=im.height/im.width;height=240*ratio;c.drawImage(ImageReader(im),40+idx*257,y-height,width=240,height=height)
  table.cell(0,idx).paragraphs[0].add_run().add_picture(str(path),width=Cm(7.5))
 y-=height+22
line('CATIA 空间框实体与面壳检查报告',True)
line('模型：'+str(check['document']))
line(f"范围：{len(entities)} 个导入对象；唯一对象对 {a['pair_count']}；净距筛查 {config['clearance_mm']} mm")
line('结果：'+json.dumps(check['counts'],ensure_ascii=False))
line('实体正公共体积超过记录容差判几何未通过。面壳交线、无效输入或证据不足保留未评价；工程允许性单独复核。')
line('来源、覆盖与限制',True)
for name in ['full-export-audit.json','full-body-mapping-audit.json','selected-body-import-audit.json','surface-import-audit.json']:
 v=read(name);compact={k:x for k,x in v.items() if k not in ('selected','all_finite_records','mapping','batch_files')};line(name+'：'+json.dumps(compact,ensure_ascii=False,default=str))
line('源模型未自动保存。管形识别不证明流道、壁厚或设计用途。接口、支撑、软管、热区、防火、运动和维护包络缺少定义时未评价。')
line('截图状态：'+('已拍摄并恢复源显示' if cap.get('restored') else '证据不完整，未取得成功拍摄与恢复审计'))
line('管形识别与中心线',True)
line(f"模型几何扫描 {check.get('swept_route_review',{}).get('scanned_object_count',0)} 个对象，识别 {len(routes)} 条连续管形路线；已排除非管路不列独立页面。")
for r in routes:
 line(r['shape_id']+' / '+r['source_name'],True);line('来源：'+r['source_path'])
 line(f"截面D约 {r['diameter_mm']:.4f} mm；采样路线L约 {r['length_mm']:.4f} mm；局部R估计范围 {r.get('radius_range_mm')} mm")
 line('截面拟合最大残差 '+str(r['max_circle_residual_mm'])+' mm；工程半径合规未评价。')
 job=next((j for j in cap['jobs'] if j['id']=='PIPE_'+str(r['source_body_index'])),None)
 if job:dual(job)
line('未通过及待复核对象对',True)
rows=sorted(a['records'],key=lambda r:(r['decision']['status']=='PASS',str(r['object_a']),str(r['object_b'])))
for r in rows:
 if r['decision']['status']=='PASS':continue
 line(r['object_a']+' / '+r['object_b']+'：'+r['decision']['status'],True)
 line(r['name_a']+' / '+r['name_b']);line('测量：'+json.dumps(r.get('fact',{}),ensure_ascii=False));line(r['decision']['reason'])
 job=next((j for j in cap['jobs'] if set(map(str,j.get('source_indices',[])))=={str(r['body_a']),str(r['body_b'])}),None)
 if job:dual(job)
 if r.get('error'):line('计算错误：'+r['error'])
line('完整逐对记录',True);line('全部对象对（包括包围盒排除与精算）见同目录 pairs.csv、spatial_box_analysis.json 和 check.json。')
page();c.save();doc.save(O/'report.docx')
with (O/'pairs.csv').open('w',encoding='utf-8-sig',newline='') as f:
 writer=csv.writer(f);writer.writerow(['object_a','object_b','name_a','name_b','status','reason','distance_mm','volume_mm3','aabb_lower_bound_mm','error'])
 for r in rows:writer.writerow([r['object_a'],r['object_b'],r['name_a'],r['name_b'],r['decision']['status'],r['decision']['reason'],r.get('fact',{}).get('minimum_distance_mm'),r.get('fact',{}).get('intersection_volume_mm3'),r.get('aabb_distance_lower_bound_mm'),r.get('error')])
with zipfile.ZipFile(O/'screenshots.zip','w',zipfile.ZIP_DEFLATED) as z:
 for file in (O/'screenshots').glob('*.png') if (O/'screenshots').exists() else []:z.write(file,file.name)
(O/'delivery.json').write_text(json.dumps({'files':{n:hashlib.sha256((O/n).read_bytes()).hexdigest() for n in ('report.pdf','report.docx','pairs.csv','screenshots.zip')},'counts':check['counts'],'screenshots_complete':bool(cap.get('restored'))},ensure_ascii=False,indent=2),encoding='utf8')
print('REPORT_COMPLETE',flush=True)
