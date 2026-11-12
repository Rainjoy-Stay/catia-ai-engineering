import json, ast
from pathlib import Path
from docx import Document
from docx.shared import Mm, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.enum.text import WD_ALIGN_PARAGRAPH
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
F=ROOT/'output/全量原生DMU检查_20261012'
read=lambda p:json.loads((F/p).read_text(encoding='utf-8-sig'))
idx=read('resume-image-index.json'); rows=idx['rows']; scope=read('resume-scope.json'); prep=read('preparation-audit.json'); native=read('native-results.json'); exact=read('resume-exact-solids.json')
assert len(rows)==87 and all(r['qa_status']=='ACCEPTED_VISUAL_REVIEW' for r in rows)
doc=Document(); sec=doc.sections[0]
sec.page_width=Mm(210);sec.page_height=Mm(297)
sec.top_margin=Mm(12);sec.bottom_margin=Mm(12);sec.left_margin=Mm(14);sec.right_margin=Mm(14)
sec.footer_distance=Mm(5)
for name in ['Normal','Title','Heading 1','Caption']:
 s=doc.styles[name];s.font.name='Microsoft YaHei';s._element.rPr.rFonts.set(qn('w:eastAsia'),'Microsoft YaHei');s.font.color.rgb=RGBColor(0,0,0)
 s.font.size=Pt(9);s.paragraph_format.space_after=Pt(5)
doc.styles['Title'].font.size=Pt(20);doc.styles['Heading 1'].font.size=Pt(16)
for style in doc.styles:
 for border in list(style._element.iter(qn('w:pBdr'))):border.getparent().remove(border)
doc.styles['Normal'].paragraph_format.line_spacing=1.05
footer=sec.footer.paragraphs[0];footer.text='原生 CATIA DMU / GSD / SPA  |  2026-10-13  |  NATIVE-STP-20261013     '
fld=OxmlElement('w:fldSimple');fld.set(qn('w:instr'),'PAGE');footer._p.append(fld)
def p(t,size=9):
 x=doc.add_paragraph(t);x.paragraph_format.space_after=Pt(6)
 for r in x.runs:r.font.size=Pt(size)
 return x
def page(t,first=False):
 x=doc.add_paragraph(t,'Title' if first else 'Heading 1');x.paragraph_format.page_break_before=not first
 x.paragraph_format.keep_with_next=True
def pic(path,height):
 x=doc.add_paragraph();x.alignment=WD_ALIGN_PARAGRAPH.CENTER;x.paragraph_format.space_after=Pt(0);x.paragraph_format.line_spacing=1
 iw,ih=Image.open(path).size
 height=min(height,182*ih/iw)
 x.add_run().add_picture(str(path),height=Mm(height))
page('涡轮发动机明显曲面穿透与几何干涉检查报告',True)
p('确认 85 对实体几何重叠、2 对曲面穿透。主报告仅展示原生 DMU 干涉指标不小于 1 mm 且已补齐几何证据的问题。接触与小间隙不逐项列入。',12)
p('按当前原位重建装配继续检查。源模型保留，未实施几何修复。对象编号对应装配树；红框仅用于定位对象，不表示精确交集边界。')
pic(rows[0]['images']['context']['annotated'],112)
p('完整重建装配示意及首项问题位置',8)
tree=ast.parse((ROOT/'tools/build_native_resume_report.py').read_text(encoding='utf-8'))
env=globals()
for key,title in [('methods','检查范围与判定方法'),('limits','检查边界与可追溯记录')]:
 node=next(n.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id==key for t in n.targets))
 values=eval(compile(ast.Expression(node),'<report content>','eval'),env)
 page(title)
 for t in values:p(t)
for off in range(0,len(rows),18):
 page('确认问题总览')
 tab=doc.add_table(rows=1,cols=6);tab.style='Light Shading Accent 1'
 headers=['编号','类型','对象 A','对象 B','DMU 指标 mm','公共体积 mm³ / 交线 mm']
 for c,t in zip(tab.rows[0].cells,headers):c.text=t
 for r in rows[off:off+18]:
  f=r['geometry_fact'];solid=f['status']=='CONFIRMED_SOLID_OVERLAP';v=f['volume_mm3'] if solid else f['trials'][0]['intersection_length_mm']
  vals=[r['issue_id'],'实体重叠' if solid else '曲面穿透',*r['object_ids'],f"{r['native']['interference_depth_mm']:.3f}",f'{v:.6g}']
  for c,t in zip(tab.add_row().cells,vals):c.text=t
 for row in tab.rows:
  for c in row.cells:
   for x in c.paragraphs:
    x.paragraph_format.space_after=Pt(3);x.paragraph_format.space_before=Pt(3)
    for run in x.runs:run.font.size=Pt(8)
for r in rows:
 f=r['geometry_fact'];solid=f['status']=='CONFIRMED_SOLID_OVERLAP'
 page(r['issue_id']+'  '+('实体几何干涉' if solid else '明显曲面穿透'))
 for label,o,k in zip(('A 橙色','B 青色'),r['objects'],r['object_ids']):p(f"{label}  {k}.1  {o['name']}",8)
 measure=f"精确公共体积 {f['volume_mm3']:.6g} mm³" if solid else f"GSD 交线 {f['trials'][0]['intersection_length_mm']:.6g} mm；正反侧邻域均进入实体"
 p(measure+f"；原生 DMU 指标 {r['native']['interference_depth_mm']:.3f} mm；SPA 最小距离 0 mm",8)
 p('源路径：'+r['objects'][0]['source_path']+' / '+r['objects'][1]['source_path'],7)
 assert Image.open(r['images']['context']['annotated']).size==Image.open(r['images']['detail']['annotated']).size
 for role,title in [('context','整体定位图  完整重建装配'),('detail','局部细节图  仅 A/B 全部适应')]:
  x=p(title,8);x.paragraph_format.keep_with_next=True;x.paragraph_format.space_after=Pt(1)
  pic(r['images'][role]['annotated'],82)
 opacity=r['detail_opacity_a'];p('红框为对象定位框。'+('双方不透明。' if opacity==255 else f'局部 A 不透明度 {opacity}/255，用于显示被 A 遮挡的 B。'),7)
out=ROOT/'output/word/涡轮发动机明显曲面穿透与几何干涉检查报告_20261013_竖版A4.docx';out.parent.mkdir(parents=True,exist_ok=True)
doc.core_properties.title='涡轮发动机明显曲面穿透与几何干涉检查报告'
doc.save(out);print(out)
