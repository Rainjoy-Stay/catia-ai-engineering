"""Native DMU report with exhaustive conflict list and source coverage gaps."""
import json,csv,hashlib,sys,math
from pathlib import Path
from collections import Counter
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4,landscape
from reportlab.lib.utils import ImageReader
from docx import Document
from docx.shared import Cm,Pt,RGBColor
from docx.oxml.ns import qn
from PIL import Image
ROOT=Path(__file__).resolve().parents[2];F=ROOT/'output/全量原生DMU检查_20261012'
read=lambda name:json.loads((F/name).read_text(encoding='utf-8-sig'))
prep=read('preparation-audit.json');native=read('native-results.json');captures=read('capture-audit.json');registry={r['id']:r for r in prep['records']}
review=read('native-gsd-spa-single-part-review.json');review_map={tuple(sorted(r['pair'])):r for r in review['rows']}
scope=read('report-scope.json')
assert len(captures['jobs'])==scope['selected_count']
assert all(j['native']['type']=='CLASH' and j['native']['interference_depth_mm']>=scope['minimum_depth_mm'] for j in captures['jobs'])
font='C:/Windows/Fonts/msyh.ttc';pdfmetrics.registerFont(TTFont('YaHei',font,subfontIndex=0))
pdf=F/'涡轮发动机明显干涉检查报告.pdf';docx=F/'涡轮发动机明显干涉检查报告.docx';W,H=landscape(A4)
cv=canvas.Canvas(str(pdf),pagesize=(W,H),pageCompression=1);cv.setTitle('涡轮发动机明显干涉检查报告')
doc=Document();section=doc.sections[0];section.page_width=Cm(29.7);section.page_height=Cm(21);section.top_margin=Cm(.9);section.bottom_margin=Cm(.9);section.left_margin=Cm(1.2);section.right_margin=Cm(1.2)
for s in ['Normal','Title','Heading 1','Heading 2']:
 style=doc.styles[s];style.font.name='微软雅黑';style._element.rPr.rFonts.set(qn('w:eastAsia'),'微软雅黑');style.font.size=Pt(9 if s=='Normal' else 18);style.paragraph_format.space_after=Pt(3)
doc.styles['Title'].font.color.rgb=RGBColor(0,0,0)
page=0
def line(text,x,y,size=10,color=(.12,.19,.28)):
 cv.setFillColorRGB(*color);cv.setFont('YaHei',size);cv.drawString(x,y,str(text))
def wrap(text,x,y,width,size=10,leading=16):
 text=str(text);chunk=''
 for ch in text:
  if pdfmetrics.stringWidth(chunk+ch,'YaHei',size)>width:
   line(chunk,x,y,size);y-=leading;chunk=''
  chunk+=ch
 if chunk:line(chunk,x,y,size);y-=leading
 return y
def start(title):
 global page
 page+=1;line(title,32,H-32,18);line('CATIA 原生 DMU GSD SPA  |  生成日期 2026-10-13',32,18,8);line(str(page),W-45,18,8)
 if page>1:doc.add_page_break()
 doc.add_paragraph(title,'Title' if page==1 else 'Heading 1')
def paragraph(text,y):
 doc.add_paragraph(text);return wrap(text,32,y,W-64)
def image(path,x,y,w,h):
 if not path or not Path(path).exists():return False
 cv.drawImage(ImageReader(str(path)),x,y,width=w,height=h,preserveAspectRatio=True,anchor='c');return True
def end():cv.showPage()
start('涡轮发动机明显干涉检查报告');y=H-70
for t in [
 f"本报告展示CATIA原生DMU判为干涉且返回干涉深度不小于{scope['minimum_depth_mm']}mm的{scope['selected_count']}对，按深度降序。接触、小间隙和较浅干涉不进入主报告，原始3053对结果保留。开放面相交不等同于材料体积重叠。",
 f"源登记 {prep['registered_bodies']} 个 Body、{prep['registered_geometry']} 个几何集合元素。成功纳入 {len(prep['records'])} 个独立检查组件；覆盖缺口 {len(prep['errors'])} 项。",
 f"原生结果 {native['raw_conflict_count']} 对：Clash {native['counts'].get('CLASH',0)}、Contact {native['counts'].get('CONTACT',0)}、Clearance {native['counts'].get('CLEARANCE',0)}。结果未截断：{not native['truncated']}。",
 f"检查装配准备 {prep['elapsed_seconds']:.2f} 秒；原生工具计算及结果读取清理 {native['tool_seconds']:.2f} 秒。净距筛查值 0.1 mm，不作为批准工程净距。",
 '源模型未保存，检查派生件单独保存。图片为本轮 CATIA 原生截图；红框表示对象位置，不表示精确交集边界。']:
 y=paragraph(t,y)-5
image(F/'full-model-native.jpg',190,42,460,max(100,y-65));doc.add_picture(str(F/'full-model-native.jpg'),width=Cm(19));end()
start('检查范围与可信度');y=H-70
texts=[
 'DMU 对全部纳入组件执行一次 Between All，包含实体与面壳。SPA 在源几何引用上复核最小距离；GSD 在独立副本上创建面壳冲突交线。本轮没有调用 OCCT。独立组件采用结果无链接复制，使用 SPA 核对面积和位置。',
 'Sag 使用本机设置，本轮未核定其数值。接触与微小相交可能因三角化和容差被归为 Contact；无冲突结果不能证明满足精确零重叠或全部工程标准。',
 '原生 Clash 记录为几何风险，Contact 和 Clearance 保留工程复核。不把历史人工放行规则、旧计算或旧截图当成本轮结果。',
 '本报告仅覆盖原生空间干涉筛查。管路用途、中心线弯曲半径、壁厚、流道、材料、防火、运动及维护性没有在本轮重新检查，保持未评价。',
 '整体定位图显示完整检查模型，局部图只保留对象双方；两图等大且居中，橙色为A、青色为B。截图异常保持待复核。',
 '基线变化：之前64对象为局部范围，本轮是全模型范围，不能直接用计数差表示新增或已解决问题。',
 f"SPA 完成 {sum(r['spa']['status']=='COMPLETE' for r in review['rows'])} 对，错误 {sum(r['spa']['status']=='ERROR' for r in review['rows'])} 对；GSD 交线完成 {sum(r['gsd']['status']=='COMPLETE' for r in review['rows'])} 对，未成功 {sum(r['gsd']['status']=='ERROR' for r in review['rows'])} 对。",
 f"截图条目 {len(captures['jobs'])}，待复核 {sum(j['status']!='OK' for j in captures['jobs'])}；显示状态恢复记录 {captures.get('restored')}。"]
for t in texts:y=paragraph(t,y)-10
end()
rows=[]
for j in captures['jobs']:
 n=j['native'];a,b=j['objects'];status='WARN_NATIVE_GEOMETRY' if n['type']=='CLASH' else 'NOT_EVALUATED_ENGINEERING'
 rows.append({'Issue ID':j['issue_id'],'原生类型':n['type'],'对象A':a['name'],'对象B':b['name'],'来源A':a['source_path'],'来源B':b['source_path'],'原生值mm':n.get('value_mm'),'报告状态':status,'截图状态':j['status']})
with (F/'全部冲突清单.csv').open('w',encoding='utf-8-sig',newline='') as f:
 writer=csv.DictWriter(f,fieldnames=list(rows[0]) if rows else ['Issue ID']);writer.writeheader();writer.writerows(rows)
for offset in range(0,len(rows),17):
 start('问题总览');y=H-66
 for r in rows[offset:offset+17]:
  text=f"{r['Issue ID']}  {r['原生类型']}  {r['对象A']} / {r['对象B']}  {r['原生值mm']} mm"
  line(text[:125],32,y,8);y-=25;doc.add_paragraph(text)
 end()
for j in captures['jobs']:
 n=j['native'];a,b=j['objects'];start(j['issue_id']+' '+('原生干涉' if n['type']=='CLASH' else '接触待复核' if n['type']=='CONTACT' else '间隙待复核'))
 y=H-60
 for t in [f"A {a['name']}  B {b['name']}  原生值 {n.get('value_mm')} mm",a['source_path']+' / '+b['source_path']]:
  line(t[:145],32,y,9);y-=15;doc.add_paragraph(t)
 note='开放面冲突需复核交线与材料边界；不能用穿透指标断言实体公共体积。' if a['kind']=='SURFACE' or b['kind']=='SURFACE' else '原生网格几何风险；设计允许性及精确公共体积需专项复核。'
 evidence=review_map.get(tuple(sorted(j['object_ids'])),{})
 if evidence.get('spa',{}).get('status')=='COMPLETE':note+=' SPA 最小距离 '+str(round(evidence['spa']['minimum_distance_mm'],6))+' mm。'
 if evidence.get('gsd',{}).get('status')=='COMPLETE':note+=' GSD 交线已生成。'
 elif evidence.get('gsd',{}).get('status')=='ERROR':note+=' GSD 交线未成功，保持待复核。'
 line(note,32,y,9);doc.add_paragraph(note)
 for role,yy in [('context',H/2+3),('detail',42)]:
  info=j[role];path=info.get('annotated') or info.get('raw')
  label=('整体定位图' if role=='context' else '局部细节图')+('  截图待复核' if info['status']!='OK' or j['status']!='OK' else '')
  image(path,70,yy,W-140,190);line(label,32,yy+192,9)
  doc.add_paragraph(label);p=doc.add_paragraph();p.paragraph_format.space_after=Pt(0)
  run=p.add_run();run.add_picture(str(path),width=Cm(15.5),height=Cm(6.4))
 end()
if prep['errors']:
 for offset in range(0,len(prep['errors']),12):
  start('覆盖缺口与执行异常');y=H-65
  for r in prep['errors'][offset:offset+12]:
   text=r['id']+' '+r['name']+' '+str(r['error']);y=wrap(text,32,y,W-64,9,14)-8;doc.add_paragraph(text)
  end()
cv.save();doc.save(docx)
(F/'report-generation.json').write_text(json.dumps({'pdf':str(pdf),'docx':str(docx),'pdf_pages':page,'issue_pages':len(captures['jobs']),'capture_needs_review':sum(j['status']!='OK' for j in captures['jobs']),'coverage_errors':len(prep['errors'])},ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({'pages':page,'issues':len(rows)},ensure_ascii=False))
