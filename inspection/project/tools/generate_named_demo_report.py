"""Create the named 20-object STEP interference and tube-rule demonstration report."""
import json
from pathlib import Path
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT=Path(__file__).resolve().parents[1]
ART=ROOT/'artifacts'/'demo_batch_20'

def shade(cell,color):
    tcPr=cell._tc.get_or_add_tcPr();shd=OxmlElement('w:shd');shd.set(qn('w:fill'),color);tcPr.append(shd)
def text(cell,value,bold=False,color='000000'):
    cell.text='';p=cell.paragraphs[0];r=p.add_run(str(value));r.bold=bold;r.font.name='Microsoft YaHei';r.font.size=Pt(8.5);r.font.color.rgb=RGBColor.from_string(color);cell.vertical_alignment=WD_ALIGN_VERTICAL.CENTER
def table(doc,headers,rows,widths=None):
    t=doc.add_table(rows=1,cols=len(headers));t.style='Table Grid';t.autofit=True
    header_pr=t.rows[0]._tr.get_or_add_trPr();repeat=OxmlElement('w:tblHeader');repeat.set(qn('w:val'),'true');header_pr.append(repeat)
    for c,h in zip(t.rows[0].cells,headers):shade(c,'17365D');text(c,h,True,'FFFFFF')
    for ri,row in enumerate(rows):
        cells=t.add_row().cells
        for c,v in zip(cells,row):text(c,v);shade(c,'F3F6FA' if ri%2 else 'FFFFFF')
    for row in t.rows:
        pr=row._tr.get_or_add_trPr();pr.append(OxmlElement('w:cantSplit'))
    if widths:
        for row in t.rows:
            for c,w in zip(row.cells,widths):c.width=Cm(w)
    return t
def heading(doc,value,level=1):
    p=doc.add_heading(value,level=level)
    for r in p.runs:r.font.name='Microsoft YaHei';r.font.color.rgb=RGBColor(0,0,0)
def para(doc,value,bold_lead=None):
    p=doc.add_paragraph();p.paragraph_format.space_after=Pt(6);p.paragraph_format.line_spacing=1.15
    if bold_lead:
        r=p.add_run(bold_lead);r.bold=True;r.font.name='Microsoft YaHei'
    r=p.add_run(value);r.font.name='Microsoft YaHei';r.font.size=Pt(9.5);return p

def main():
    data=json.loads((ART/'named_local_analysis.json').read_text(encoding='utf-8'))
    mapping=json.loads((ART/'source_name_mapping.json').read_text(encoding='utf-8'))['mapping']
    selected=[x for x in mapping if x['selected_for_report'] and x['index']!=832]
    doc=Document();sec=doc.sections[0];sec.top_margin=Cm(1.7);sec.bottom_margin=Cm(1.6);sec.left_margin=Cm(1.8);sec.right_margin=Cm(1.8)
    styles=doc.styles
    styles['Normal'].font.name='Microsoft YaHei';styles['Normal'].font.size=Pt(9.5)
    title=doc.add_paragraph(style='Title');title.alignment=WD_ALIGN_PARAGRAPH.CENTER
    tr=title.add_run('涡轮发动机局部干涉与导管弯曲半径检查报告');tr.font.size=Pt(27);tr.font.name='Microsoft YaHei';tr.font.color.rgb=RGBColor(0,0,0)
    sub=doc.add_paragraph();sub.alignment=WD_ALIGN_PARAGRAPH.CENTER;sub.add_run('20个空间相邻对象演示批次').bold=True
    para(doc,'本报告验证从 CATIA 局部对象选择、唯一命名、STEP 导出、精确干涉计算、管路外形识别、HB 4-55-2002 规则调用到报告输出的完整链路。')
    overall='需要复核'
    table(doc,['项目','结果'],[
        ['总体状态',overall],['选中对象','20'],['可精确评价实体',data['exact_solid_count']],
        ['精确实体对',data['pair_count']],['计算异常',data['pair_errors']],
        ['明确分离 PASS',data['decision_counts'].get('PASS',0)],['NOT_EVALUATED',data['decision_counts'].get('NOT_EVALUATED',0)],
        ['正体积重叠候选',data['positive_volume_overlap_pairs']],['管路外形候选','2']],[4,12])
    heading(doc,'1 检查对象与唯一命名')
    para(doc,'系统先检查原始名称是否能够区分对象。本模型1412个Body的原名称均唯一，因此全部保留；只有发现完全重名时才会追加Body序号。重新导出的STEP、计算证据和本报告使用同一名称，原始STEP文件未被覆盖。')
    rows=[[x['index'],x['original_name'],x['final_stp_name'],('是' if x['renamed_because_duplicate'] else '否')] for x in selected]
    table(doc,['原Body序号','原名称','最终STEP名称','因重名改写'],rows,[2.2,4.5,7.5,2.2])
    doc.add_picture(str(ART/'CATIA_20Bodies.jpg'),width=Cm(16.5));doc.paragraphs[-1].alignment=WD_ALIGN_PARAGRAPH.CENTER
    cap=doc.add_paragraph('图1  CATIA中选取的20个空间相邻对象');cap.alignment=WD_ALIGN_PARAGRAPH.CENTER
    heading(doc,'2 精确干涉检查')
    para(doc,'18个有效闭合 Solid 完成全部153对精确B-Rep计算。PASS仅表示该对象对明确分离；接触、共面、正体积重叠和语义不明情况均保留复核，不直接视为真实穿模。')
    table(doc,['类别','数量'],[[k,v] for k,v in data['category_counts'].items()],[9,4])
    positive=[x for x in data['records'] if x.get('fact',{}).get('intersection_volume_mm3',0)>0]
    rows=[]
    for x in positive:
        rows.append([x['name_a'],x['name_b'],f"{x['fact']['intersection_volume_mm3']:.9g}",x['decision']['category'],x['decision']['status']])
    table(doc,['对象A','对象B','公共体积 mm³','分类','状态'],rows,[5.1,5.1,2.2,2.4,2])
    if data['non_solid_objects']:
        para(doc,'以下对象没有满足实体干涉计算要求的有效闭合 Solid，因此没有被静默算作通过：')
        table(doc,['STEP名称','状态','原因'],[[x['stp_name'],x['status'],x['reason']] for x in data['non_solid_objects']],[9,3,5])
    heading(doc,'3 管路候选与HB 4-55-2002检查')
    doc.add_picture(str(ART/'CATIA_管路候选.jpg'),width=Cm(16.5));doc.paragraphs[-1].alignment=WD_ALIGN_PARAGRAPH.CENTER
    cap=doc.add_paragraph('图2  两条B样条等圆截面管路外形候选');cap.alignment=WD_ALIGN_PARAGRAPH.CENTER
    rows=[]
    for item in data['geometry_candidates']:
        c=item['candidate'];f=item.get('bend_radius_rule_finding')
        if c['geometry_kind']!='BSPLINE_CIRCULAR_SWEEP_EXTERIOR_CANDIDATE':continue
        rows.append([item['stp_name'],f"{c['outer_diameter_mm']:.6f}",f"{c['centerline_bend_radius_mm']:.6f}",
                     f"{c['minimum_radius_ratio_r_over_d']:.4f}",f['status'] if f else 'NOT_EVALUATED'])
    table(doc,['STEP名称','DN候选 mm','最小R mm','R/DN','HB 4-55-2002'],rows,[7,2.3,2.3,2,3])
    para(doc,'两条构件的中心线和曲率均已从精确B-Rep恢复，但0.475 mm和0.500 mm不在当前HB 4-55-2002配置的4–80 mm公称外径系列内。系统保留实测值并输出NOT_EVALUATED，禁止自行假定比例后给出符合性结论。')
    heading(doc,'4 结论与演示价值')
    para(doc,'本批次已跑通唯一命名STEP、局部精确干涉和导管弯曲半径检查的完整技术链路。当前没有自动形成真实穿模FAIL；21个对象对因接触、共面或重叠语义不足保留NOT_EVALUATED。管路候选的几何测量成功，但标准口径适用性仍需确认。')
    para(doc,'STEP没有已确认空腔，因此本报告不评价流道贯通、内径和壁厚；材料、压力及成形工艺缺失时也不评价相应制造条款。')
    heading(doc,'5 可追溯文件')
    table(doc,['文件','用途'],[['涡轮发动机_原名一致_20对象.stp','保留可分辨原名；仅真正重名时追加编号'],['source_name_mapping.json','原Body序号、原名称与最终STEP名称映射'],['named_local_analysis.json','153对精确几何及管路规则结构化结果'],['CATIA_20Bodies.jpg / CATIA_管路候选.jpg','CATIA现场定位证据']],[8,9])
    out=ART/'涡轮发动机_20对象_干涉与管路规范检查报告.docx';doc.save(out);print(out)

if __name__=='__main__':main()
