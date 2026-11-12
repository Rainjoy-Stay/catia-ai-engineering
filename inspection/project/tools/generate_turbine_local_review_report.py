"""Create an evidence review document from current conservative classifications."""
import json
from pathlib import Path
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.shared import Inches, Pt
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / 'artifacts' / 'step_filter_local_evidence'


def run_font(run, size=10, bold=False):
    run.font.name = 'Microsoft YaHei'; run.font.size = Pt(size); run.bold = bold
    run._element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'), 'Microsoft YaHei')


def paragraph(doc, text):
    p = doc.add_paragraph(); p.paragraph_format.space_after = Pt(7)
    p.paragraph_format.line_spacing = 1.15; run_font(p.add_run(text))


def table(doc, headers, rows, widths):
    t = doc.add_table(rows=1, cols=len(headers)); t.autofit = False
    for col,width in zip(t.columns, widths):
        col.width = Inches(width)
    borders = OxmlElement('w:tblBorders')
    for edge in ('top','left','bottom','right','insideH','insideV'):
        node = OxmlElement('w:'+edge); node.set(qn('w:val'),'single')
        node.set(qn('w:sz'),'4'); node.set(qn('w:color'),'D9D9D9'); borders.append(node)
    t._tbl.tblPr.append(borders)
    for ri, values in enumerate([headers]+rows):
        cells = t.rows[0].cells if ri==0 else t.add_row().cells
        for ci,(cell,text) in enumerate(zip(cells,values)):
            cell.width=Inches(widths[ci]); cell.text=''
            cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
            p=cell.paragraphs[0]; p.paragraph_format.space_after=Pt(3)
            p.paragraph_format.space_before=Pt(3); p.paragraph_format.line_spacing=1.05
            p.alignment=WD_ALIGN_PARAGRAPH.CENTER
            run_font(p.add_run(str(text)),9,ri==0)
            if ri==0 or ri%2==0:
                sh=OxmlElement('w:shd'); sh.set(qn('w:fill'),'EAF1F8' if ri==0 else 'F5F7F9')
                cell._tc.get_or_add_tcPr().append(sh)
            margin=OxmlElement('w:tcMar')
            for side in ('top','left','bottom','right'):
                v=OxmlElement('w:'+side); v.set(qn('w:w'),'80'); v.set(qn('w:type'),'dxa'); margin.append(v)
            cell._tc.get_or_add_tcPr().append(margin)
        if ri==0:
            repeat=OxmlElement('w:tblHeader'); t.rows[0]._tr.get_or_add_trPr().append(repeat)
        else:
            no_split=OxmlElement('w:cantSplit'); t.rows[-1]._tr.get_or_add_trPr().append(no_split)
    doc.add_paragraph().paragraph_format.space_after=Pt(0)


def build():
    input_path=ART/'turbine_source_evidence_filtered.json'
    payload=json.loads(input_path.read_text(encoding='utf-8'))
    if payload['audit']['step_interference_filter']['schema_version'] != 'step-interference-filter.v1.1':
        raise ValueError('Report requires the accepted v1.1 result')
    records=json.loads((ART/'local_evidence_ledger.json').read_text(encoding='utf-8'))
    repair=json.loads((ART/'identity_repair.json').read_text(encoding='utf-8'))
    doc=Document(); sec=doc.sections[0]
    sec.page_width=Inches(8.5); sec.page_height=Inches(11)
    sec.top_margin=sec.bottom_margin=Inches(.7); sec.left_margin=sec.right_margin=Inches(.7)
    for name,size in [('Normal',10),('Title',22),('Heading 1',15),('Heading 2',12)]:
        s=doc.styles[name]; s.font.name='Microsoft YaHei'; s.font.size=Pt(size)
        s._element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'),'Microsoft YaHei')
        from docx.shared import RGBColor
        s.font.color.rgb=RGBColor(0,0,0)
        for node in list(s._element.get_or_add_pPr()):
            if node.tag==qn('w:pBdr'): s._element.pPr.remove(node)
    run_font(sec.header.paragraphs[0].add_run('CATIA 智能检查  涡轮模型局部复核'),8)
    foot=sec.footer.paragraphs[0]; foot.alignment=WD_ALIGN_PARAGRAPH.RIGHT
    run_font(foot.add_run('2026年9月17日  PARTIAL  '),8)
    field=OxmlElement('w:fldSimple'); field.set(qn('w:instr'),'PAGE'); foot._p.append(field)
    doc.add_paragraph('涡轮发动机重叠证据复核报告',style='Title')
    paragraph(doc,'本报告用于确认原 23 项失败记录中的几何事实及来源。36 个相关 Solid 已全部建立唯一空间对应，23 项公共体积全部复算成功。21 项有稳定的内部重叠点，2 项优先复核局部公差和转换差异。23 项均继续保留 NOT_EVALUATED，尚不能签发工程通过或失败结论。')
    doc.add_heading('重叠表示什么',level=1)
    paragraph(doc,'重叠表示两个实体占用了同一块三维空间，精确相交得到的公共体积大于零。接触只在边界相遇，公共体积为零。重叠可能是允许的连接关系、非设计穿模或转换差异；公共体积本身不说明原因。')
    doc.add_heading('修正来源错配',level=1)
    paragraph(doc,'旧标签加体积匹配误将三处几何映射到等体积但位置不同的 Body。本次使用体积、面积、重心及绝对包围盒共同确认唯一来源，未放宽容差；另补齐四个原来未解析的来源。')
    table(doc,['STEP Solid','原 Body','正确 Body'],[
        ('BATCH_0020  SOLID_0017','778','777'),('BATCH_0021  SOLID_0032','833','834'),
        ('BATCH_0021  SOLID_0034','835','836')],[3.9,1.6,1.6])
    doc.add_heading('优先复核的两项',level=1)
    thin=[r for r in records if not r['evidence']['robust_interior_witness_found']]
    table(doc,['问题 ID 后缀','Body 对','公共体积 mm³','局部分类容差 mm'],[
        (r['issue_id'].split('-')[-1],f"{r['body_a']} / {r['body_b']}",f"{r['evidence']['volume_mm3']:.6g}",
         f"{r['evidence']['classification_tolerance_mm']:.6g}") for r in thin],[1.7,1.3,2.1,2.0])
    paragraph(doc,'两项均在原始 STEP 经当前内核读取后复现，导出前后体积变化分别约 0.232% 和 0.376%，不能认定为 CATIA 导出新增伪影。828 / 841 的内部点分类受容差影响；未找到稳定内部点不证明无重叠。分类容差不是工程允许重叠值。')
    for page,chunk in enumerate((records[:8],records[8:16],records[16:]),1):
        doc.add_page_break(); doc.add_heading(f'逐项位置记录 第{page}组',level=1)
        paragraph(doc,'问题完整 ID 为 SINGLEPART 加下表后缀。坐标为公共体积重心，单位 mm，用于定位，不能当作重叠深度。完整精度、面信息及内部点证据保存在结构化记录中。')
        rows=[]
        for r in chunk:
            e=r['evidence']; xyz=e['centroid_mm']
            rows.append((r['issue_id'].split('-')[-1],f"{r['body_a']} / {r['body_b']}",
                         f"{e['volume_mm3']:.6g}", '\n'.join(f'{x:.4f}' for x in xyz),
                         '有稳定内部点' if e['robust_interior_witness_found'] else '优先公差复核'))
        table(doc,['问题 ID 后缀','Body 对','公共体积 mm³','重心 X Y Z','局部证据'],rows,[1.45,1.05,1.45,1.55,1.6])
        paragraph(doc,'本组所有项目均为 NOT_EVALUATED。稳定内部点仅证明材料区域的几何重叠，不证明它违反设计要求。')
    doc.add_page_break(); doc.add_heading('裁决所需的下一项证据',level=1)
    paragraph(doc,'全部 23 项仍需核对是否属于批准的接口或装配重叠范围，并确认全部公共体积是否局限在该范围内。两项薄重叠已完成原始 STEP 及分类容差复核，尚未获得工程意图依据。未获确认前，保留待评估。')
    paragraph(doc,'本次没有对整套涡轮模型进行管路语义重建，没有清理、合并或修改供应商几何。源模型前后 manifest 完全一致，Body 数仍为 1412；本轮局部检查使用上一轮保留的 BRep 缓存，没有再次保存或导出源模型。')
    doc.add_heading('统计口径',level=1)
    paragraph(doc,f"统一结果计数为 PASS {payload['counts']['PASS']}，FAIL {payload['counts']['FAIL']}，NOT_EVALUATED {payload['counts']['NOT_EVALUATED']}，ERROR {payload['counts']['ERROR']}。其中 PASS 来自原 23 项以外的精确无相交候选。计数保留了未计算和异常项，不能将这些数字简单相加当作互斥候选总数。")
    paragraph(doc,'尚有 6903 个候选未完成精确计算。局部复核结果及少量通过项不代表全模型通过，报告状态仍为 PARTIAL。旧阶段报告保留为历史记录，以本轮结构化结果及本报告的修正来源为准。')
    doc.add_heading('实现验证及证据文件',level=1)
    paragraph(doc,'过滤层 v1.1 相关回归 25 项通过，新增验证已确认的小体积穿模不会被伪影阈值过滤，缺少稳定内部点不会覆盖穿模证据。上一轮空间来源及局部几何回归 51 项通过。过滤层的独立验收不等于全模型验收通过。')
    paragraph(doc,'证据文件位于本报告同目录：identity_repair.json 保存来源修正；local_evidence_ledger.json 保存 23 项局部证据；thin_overlap_sensitivity.json 保存原始 STEP 和容差复核；turbine_source_evidence_filtered.json 为本报告使用的 v1.1 统一裁决。')
    path=ART/'涡轮发动机重叠证据复核报告.docx'; doc.save(path); print(path)


if __name__=='__main__': build()
