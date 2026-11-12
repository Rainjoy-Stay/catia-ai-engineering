"""One landscape PDF from verified native geometry and equally sized real views."""
import json,csv,hashlib,math
from pathlib import Path
from datetime import datetime
from collections import Counter
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4,landscape
from reportlab.lib.utils import ImageReader
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];F=ROOT/'output/全量原生DMU检查_20261012'
read=lambda p:json.loads((F/p).read_text(encoding='utf-8-sig'))
idx=read('resume-image-index.json');scope=read('resume-scope.json');prep=read('preparation-audit.json');native=read('native-results.json');exact=read('resume-exact-solids.json');surf=read('resume-surface-evidence.json')
rows=idx['rows'];assert len(rows)==len(scope['queue'])
assert idx['restoration']['verified']
assert all(r['qa_status']=='ACCEPTED_VISUAL_REVIEW' for r in rows),'Finish image review before authoring'
assert all(all(e['status']=='PROJECTION_CHECK_PASSED' for e in r['images'].values()) for r in rows)
outdir=ROOT/'output/pdf';outdir.mkdir(exist_ok=True)
pdf=outdir/'涡轮发动机明显曲面穿透与几何干涉检查报告_20261013.pdf'
pdfmetrics.registerFont(TTFont('YH','C:/Windows/Fonts/msyh.ttc',subfontIndex=0))
W,H=landscape(A4);cv=canvas.Canvas(str(pdf),pagesize=(W,H),pageCompression=1);cv.setTitle('涡轮发动机明显曲面穿透与几何干涉检查报告');page=0
stats=Counter(r['geometry_fact']['status'] for r in rows)
solids=stats['CONFIRMED_SOLID_OVERLAP'];surfaces=len(rows)-solids
def text(t,x,y,size=9,color=(.12,.17,.24)):
 cv.setFont('YH',size);cv.setFillColorRGB(*color);cv.drawString(x,y,str(t))
def wrap(t,x,y,width,size=9,leading=15):
 s=''
 for ch in str(t):
  if pdfmetrics.stringWidth(s+ch,'YH',size)>width:
   text(s,x,y,size);y-=leading;s=''
  s+=ch
 if s:text(s,x,y,size);y-=leading
 return y
def start(title):
 global page
 page+=1;text(title,32,H-34,17,(.04,.08,.14))
 text('原生 CATIA DMU / GSD / SPA   |   2026-10-13   |   NATIVE-STP-20261013',32,17,7)
 text(page,W-42,17,7)
def end():cv.showPage()
def image(p,x,y,w,h):
 cv.drawImage(ImageReader(str(p)),x,y,width=w,height=h,preserveAspectRatio=True,anchor='c')
start('涡轮发动机明显曲面穿透与几何干涉检查报告')
y=H-70
y=wrap(f'确认 {solids} 对实体几何重叠，{surfaces} 对曲面穿透。主报告仅展示既有 DMU 干涉指标不小于 1 mm 且已补齐几何证据的问题；接触和小间隙不逐项列入。',32,y,W-64,12,21)
y=wrap('按当前原位重建装配继续检查。源模型保留，未实施几何修复。报告中的对象编号可对应装配树，红框仅用于定位对象，不表示精确交集边界。',32,y-8,W-64,10,17)
example=rows[0]['images']['context']['annotated'];image(example,52,68,W-104,300)
text('完整重建装配示意及首项问题位置',32,49,8)
end()
start('检查范围与判定方法');y=H-67
methods=[
 f"当前装配包含 {len(prep['records'])} 个派生检查组件：1412 个实体、260 个有限面壳。源登记 1714 个对象，另有 {len(prep['errors'])} 个源面元素未能纳入；不能将本报告理解为源 STP 零遗漏证明。",
 f"延续同源模型已有的原生 DMU Between All 记录。理论无序对象对 {1672*1671//2:,}，原生返回 {native['raw_conflict_count']} 条冲突：干涉 507、接触 2185、间隙 361，结果未截断。初次 SPA 已测量返回的冲突对象对。本轮没有冒充重新执行全装配 DMU。",
 '接续的明显候选筛查门槛为原生 DMU 干涉指标至少 1 mm，共 168 对。这个数值用于本报告筛选，不是通用工程验收尺寸；DMU 指标也不等同于精确实体公共体积。',
 f"实体：对 {len(exact['rows'])} 对候选在一次性独立副本中求原生 Part Design 公共体，再由 SPA 测体积；单位由 m³ 换算为 mm³。公共体积超过本轮数值容差 1e-6 mm³ 时确认几何重叠。已核对原位单位矩阵及公共体积不超过输入实体最小体积。",
 '曲面：交线不能单独判材料重叠。对有 GSD 交线的明显面壳候选，分别建立正面和背面 0.02 mm、0.01 mm 的临时邻域，并与实体求公共部分；两侧均有公共部分、厚度减半后体积约减半，形成双侧穿透证据。探测厚度不是模型壁厚，探测体积不是原面壳的实际材料体积。',
 '用途、设计允许配合、制造公差、工程净距、运动及维护性未在本轮作工程裁决。已确认几何重叠不会因用途未知而降为无干涉。']
for t in methods:y=wrap(t,32,y,W-64,9,16)-14
end()
start('检查边界与可追溯记录');y=H-67
limits=[
 f"主报告 {len(rows)} 项。尚未确证的 {len(scope['pending_candidates'])} 对候选保留在审计记录，不计通过：其中包括 79 对其余面壳候选、1 对实体公共体计算失败、1 对面壳封闭或邻域构造失败。",
 '实体待复核 DMU-00097 已交换布尔运算顺序补算，仍未得到有效公共体。面壳待复核 DMU-00024 已取得交线，但封闭和临时邻域构造未成功。失败不是零重叠。',
 '截图使用完整重建装配作整体图；局部只显示 A/B 对象。两图等大，同一等轴侧方向，各自全部适应。A 为橙色、B 为青色，背景约 20% 不透明；遮挡时仅降低 A 的不透明度并在问题页标明。',
 '配图定位来自同相机下的真实单对象原生投影。原图、相机、对象显示属性、图像哈希及复核索引均保留。恢复后回读核对显示属性与相机，结果一致。',
 '检查装配的 Saved 标志因显示操作由已保存变为未保存；没有通过保存来掩盖该变化，也没有写入原始 STP 或覆盖检查装配。',
 '本报告延续当前检查装配的几何数据，新增精确实体及双侧曲面复核、原生截图。与历史局部范围不作新增或已解决问题的计数比较。',
 '源 STP SHA256：'+read('source-file-hash.json')['Hash'],
 '详细记录目录：全量原生DMU检查_20261012。确认问题清单见同目录的 明显问题确认清单_20261013.csv；未确证候选及覆盖缺口仍保留。']
for t in limits:y=wrap(t,32,y,W-64,9,16)-15
end()
for off in range(0,len(rows),18):
 start('确认问题总览');y=H-63
 headers=[('编号',32),('类型',114),('对象 A',185),('对象 B',315),('DMU 指标 mm',450),('公共体积 mm³ / 交线 mm',570)]
 for t,x in headers:text(t,x,y,8)
 y-=22
 for r in rows[off:off+18]:
  fact=r['geometry_fact'];kind='实体重叠' if fact['status']=='CONFIRMED_SOLID_OVERLAP' else '曲面穿透'
  value=fact.get('volume_mm3') if kind=='实体重叠' else fact['trials'][0]['intersection_length_mm']
  for t,x in [(r['issue_id'],32),(kind,114),(r['object_ids'][0],185),(r['object_ids'][1],315),(f"{r['native']['interference_depth_mm']:.3f}",450),(f'{value:.6g}',570)]:text(t,x,y,8)
  y-=23
 end()
csvrows=[]
for r in rows:
 fact=r['geometry_fact'];solid=fact['status']=='CONFIRMED_SOLID_OVERLAP'
 csvrows.append({'Issue ID':r['issue_id'],'类型':'实体重叠' if solid else '曲面穿透','对象A':r['object_ids'][0]+'.1','对象B':r['object_ids'][1]+'.1','源名称A':r['objects'][0]['name'],'源名称B':r['objects'][1]['name'],'源路径A':r['objects'][0]['source_path'],'源路径B':r['objects'][1]['source_path'],'DMU指标mm':r['native']['interference_depth_mm'],'实际公共体积mm3':fact.get('volume_mm3') if solid else '', 'GSD交线mm':fact['trials'][0]['intersection_length_mm'] if not solid else '', '配图复核':r['qa_status']})
 start(r['issue_id']+'  '+('实体几何干涉' if solid else '明显曲面穿透'))
 y=H-57
 for label,o,k in zip(('A 橙色','B 青色'),r['objects'],r['object_ids']):
  text(f"{label}  {k}.1  {o['name']}",32,y,8);y-=13
 measure=f"精确公共体积 {fact['volume_mm3']:.6g} mm³" if solid else f"GSD 交线 {fact['trials'][0]['intersection_length_mm']:.6g} mm；正反侧邻域均进入实体"
 text(measure+f"；原生 DMU 指标 {r['native']['interference_depth_mm']:.3f} mm；SPA 最小距离 0 mm",32,y,8);y-=13
 text('源路径：'+r['objects'][0]['source_path']+' / '+r['objects'][1]['source_path'],32,y,7)
 # Identical image rectangles; image aspect ratios are also identical.
 iw,ih=Image.open(r['images']['context']['annotated']).size
 assert Image.open(r['images']['detail']['annotated']).size==(iw,ih)
 frame_h=190;frame_w=W-64
 for role,yy,title in [('context',H/2-10,'整体定位图  完整重建装配'),('detail',49,'局部细节图  仅 A/B 全部适应')]:
  text(title,32,yy+frame_h+3,8)
  image(r['images'][role]['annotated'],32,yy,frame_w,frame_h)
 opacity=r['detail_opacity_a'];note='对象定位框；默认双方不透明。' if opacity==255 else f'对象定位框；局部 A 不透明度 {opacity}/255，原因是 A 遮挡 B。'
 text(note+'  检查位置与模型尺寸请以原生几何记录为准。',32,35,7)
 end()
with (F/'明显问题确认清单_20261013.csv').open('w',encoding='utf-8-sig',newline='') as fp:
 writer=csv.DictWriter(fp,fieldnames=csvrows[0].keys());writer.writeheader();writer.writerows(csvrows)
cv.save()
manifest={'pdf':str(pdf),'pages':page,'confirmed_solid_pairs':solids,'surface_penetration_pairs':surfaces,'issue_pages':len(rows),'pending_candidates':len(scope['pending_candidates']),'source_coverage_gaps':len(prep['errors']),'restoration':idx['restoration'],'created':datetime.now().isoformat(),'pdf_sha256':hashlib.sha256(pdf.read_bytes()).hexdigest()}
(F/'resume-report-generation.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(manifest,ensure_ascii=False))
