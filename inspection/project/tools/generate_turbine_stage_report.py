from pathlib import Path
import json
from standalone.step_interference_filter import filter_result
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artifacts" / "live_acceptance_20260916"
OUT = ROOT / 'artifacts' / 'step_filter_acceptance' / "涡轮发动机_STEP过滤后阶段性报告.docx"
NAVY, BLUE, PALE, LINE = "17365D", "2E5E8C", "EAF1F8", "D9D9D9"


def font(run, size=10, bold=False, color="263238"):
    run.font.name = "Microsoft YaHei"
    run._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = RGBColor.from_string(color)


def shade(cell, fill):
    tcpr = cell._tc.get_or_add_tcPr()
    shd = tcpr.find(qn("w:shd")) or OxmlElement("w:shd")
    if shd.getparent() is None:
        tcpr.append(shd)
    shd.set(qn("w:fill"), fill)


def borders(table):
    pr = table._tbl.tblPr
    node = pr.find(qn("w:tblBorders")) or OxmlElement("w:tblBorders")
    if node.getparent() is None:
        pr.append(node)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "single"); el.set(qn("w:sz"), "4"); el.set(qn("w:color"), LINE)
        node.append(el)


def cell_text(cell, value, bold=False, color="263238", align=WD_ALIGN_PARAGRAPH.LEFT):
    cell.text = ""
    p = cell.paragraphs[0]; p.alignment = align
    p.paragraph_format.space_before = Pt(0); p.paragraph_format.space_after = Pt(0)
    font(p.add_run(str(value)), 9, bold, color)
    cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER


def add_table(doc, headers, rows, widths=None):
    table = doc.add_table(rows=1, cols=len(headers)); table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False; borders(table)
    for i, h in enumerate(headers):
        cell_text(table.rows[0].cells[i], h, True, "FFFFFF", WD_ALIGN_PARAGRAPH.CENTER); shade(table.rows[0].cells[i], NAVY)
    trpr = table.rows[0]._tr.get_or_add_trPr(); rep = OxmlElement("w:tblHeader"); rep.set(qn("w:val"), "true"); trpr.append(rep)
    for ri, row in enumerate(rows):
        cells = table.add_row().cells
        for i, val in enumerate(row):
            cell_text(cells[i], val, False, "263238", WD_ALIGN_PARAGRAPH.CENTER if i else WD_ALIGN_PARAGRAPH.LEFT)
            if ri % 2: shade(cells[i], "F6F8FA")
    if widths:
        for row in table.rows:
            for cell, width in zip(row.cells, widths): cell.width = Cm(width)
    doc.add_paragraph().paragraph_format.space_after = Pt(1)
    return table


def paragraph(doc, text, bold_prefix=None):
    p = doc.add_paragraph(); p.paragraph_format.space_after = Pt(6); p.paragraph_format.line_spacing = 1.18
    if bold_prefix and text.startswith(bold_prefix):
        font(p.add_run(bold_prefix), 10, True); font(p.add_run(text[len(bold_prefix):]), 10)
    else: font(p.add_run(text), 10)
    return p


def heading(doc, text, level=1):
    return doc.add_paragraph(text, style=f"Heading {level}")


def build():
    latest = ROOT / 'artifacts' / 'step_filter_local_evidence' / 'turbine_source_evidence_filtered.json'
    rechecked = latest if latest.is_file() else ROOT / 'artifacts' / 'step_filter_body_recheck' / 'turbine_rechecked_filtered.json'
    input_path = rechecked if rechecked.is_file() else ART / 'turbine_traceability_merged.json'
    payload = filter_result(json.loads(input_path.read_text(encoding='utf-8')))
    filtered = payload['audit']['step_interference_filter']
    evaluated = sum(filtered['categories'].values())
    pair_status = {s: sum(f['status'] == s for f in payload['findings'])
                   for s in ('FAIL', 'NOT_EVALUATED', 'PASS')}
    status_text = f"{pair_status['FAIL']} FAIL / {pair_status['NOT_EVALUATED']} NOT_EVALUATED / {pair_status['PASS']} PASS"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = Document(); sec = doc.sections[0]
    sec.top_margin, sec.bottom_margin = Cm(1.8), Cm(1.7); sec.left_margin = sec.right_margin = Cm(2.0)
    for name, size in (("Normal", 10), ("Title", 24), ("Heading 1", 16), ("Heading 2", 12.5)):
        st = doc.styles[name]; st.font.name = "Microsoft YaHei"; st._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
        st.font.size = Pt(size); st.font.color.rgb = RGBColor(0, 0, 0)
        if name != "Normal": st.font.bold = True; st.paragraph_format.keep_with_next = True
        ppr = st._element.get_or_add_pPr()
        pbdr = ppr.find(qn("w:pBdr"))
        if pbdr is not None:
            ppr.remove(pbdr)
    header = sec.header.paragraphs[0]; header.text = "CATIA 模型智能检查系统  实机验收记录"; font(header.runs[0], 8, False, "607080")
    footer = sec.footer.paragraphs[0]; footer.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    font(footer.add_run("阶段性结果  PARTIAL  |  2026-09-16"), 8, False, "607080")

    for _ in range(3): doc.add_paragraph()
    title = doc.add_paragraph(style="Title"); title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    font(title.add_run("涡轮发动机 CATIA 智能检查阶段性报告"), 24, True, "000000")
    sub = doc.add_paragraph(); sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    font(sub.add_run("大型单 CATPart 精确相交与几何追溯实机验收"), 13, True, "607080")
    stat = doc.add_paragraph(); stat.alignment = WD_ALIGN_PARAGRAPH.CENTER; stat.paragraph_format.space_before = Pt(18)
    font(stat.add_run("PARTIAL  阶段性结果"), 18, True, "B54708")
    add_table(doc, ["项目", "内容"], [
        ("检查模型", "涡轮发动机.CATPart"), ("检查日期", "2026-09-16"),
        ("方法", "CATIA Body 分批导出 + OCCT 精确 BRep + CATIA SPA/拓扑复核"),
        ("数据安全", "只读检查；源模型未修改、未由工具保存；临时文件已清理"),
    ], [4.0, 12.5])
    paragraph(doc, f"本报告记录已有精确证据经 STEP 转换过滤层重新裁决后的结果：{status_text}。原 23 项 FAIL 保留待复核，不能视为转换伪影已排除或模型已通过。全部候选尚未计算完成，不构成最终验收结论。")
    doc.add_page_break()

    heading(doc, "1 执行摘要")
    paragraph(doc, "结论：当前状态为 PARTIAL。系统已验证大型单 CATPart 的分批导出、全局候选筛选、精确 BRep 相交、Body/Solid 追溯以及 CATIA 截图定位链。当前已完成 426 对候选的精确计算，占跨批候选的 5.81%。")
    add_table(doc, ["指标", "结果", "说明"], [
        ("CATIA Body", "1412", "源模型实体容器"), ("OCCT Solid", "1410", "分批 STEP 导出后的精确实体"),
        ("理论两两组合", "993345", "未执行穷举精确计算"), ("AABB 候选", "7329", "宽相位筛选后"),
        ("跨批候选", "6083", "需通过检查点继续处理"), ("已精确计算", str(evaluated), status_text),
        ("待处理", "6903", "7329 - 426"), ("已计算比例", "5.81%", "相对 AABB 候选"),
    ], [4.4, 3.0, 9.1])

    heading(doc, "2 结果口径与风险")
    focused = payload['audit'].get('focused_body_recheck') or {}
    paragraph(doc, f"已计算候选的过滤结果为 {status_text}。本次定向复核确认 {focused.get('verified_solid_count', 0)} 个 Solid，重新计算 {focused.get('recomputed_pair_count', 0)} 项原重叠。来源、有效性或设计意图不足时保持 NOT_EVALUATED；公共体积证据保留。没有重新执行全部候选计算。")
    paragraph(doc, "预计从现有检查点继续运行全量精确检查需约 2至2.5 小时；如存在更多复杂或损坏实体，可能超过 3 小时。完成前不建议签发最终“通过”结论。")

    heading(doc, "3 Body Solid 追溯结果")
    add_table(doc, ["项目", "结果", "判定"], [
        ("已安全映射 Solid", "1386 / 1410", "覆盖率 98.30%"), ("未解析 Solid", "24", "不使用顺序回退"),
        ("Body 45", "1 Body 对应 2 Solid", "已记录一对多组"), ("顺序映射", "未使用", "sequence fallback = false"),
        ("第 21 批", "40 Body 转换为 38 Solid", "转换数量差异，必须保持 PARTIAL"),
    ], [5.0, 4.0, 7.5])
    paragraph(doc, "追溯链综合 CATIA SPA 体积、面积、重心与 OCCT 体积、面积、重心、包围盒和拓扑数量。稳定标签只用于生成候选，必须通过几何特征复核；对重复几何、多解或特征不足的情况拒绝猜测。")

    heading(doc, "4 CATIA 定位证据")
    paragraph(doc, "以下为几何重叠待复核项 SINGLEPART-049525CEB294 的历史实机定位证据。截图可辅助定位，不证明该项为真实穿模或转换伪影。截图保留模型树，红框仅标记视图区几何差异。")
    for name, caption in (("SINGLEPART-049525CEB294_isometric_marked.jpg", "图 1  等轴测视图"), ("SINGLEPART-049525CEB294_right_marked.jpg", "图 2  右视图")):
        p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.add_run().add_picture(str(ART / "evidence" / name), width=Cm(16.2))
        c = doc.add_paragraph(); c.alignment = WD_ALIGN_PARAGRAPH.CENTER; font(c.add_run(caption), 9, False, "607080")

    heading(doc, "5 会话与数据安全")
    paragraph(doc, "检查完成后已恢复原活动文档“涡轮发动机.CATPart”，临时 CATIA 文档数量为 0。检查工具未修改源模型，未触发源模型保存，单 Body 救援过程的临时文件已全部删除。")

    heading(doc, "6 验收判定与后续动作")
    paragraph(doc, "当前判定：PARTIAL。该版本已证明检查架构可在真实大型 CATPart 上运行，且能在不使用网格作为最终裁决的前提下输出精确 BRep 结果与 CATIA 定位证据。但尚有 6903 个候选对待处理，24 个 Solid 未安全映射，并存在第 21 批的 Body/Solid 数量差异。")
    steps = [
        "对旧 23 项重叠补充逐 Solid 有效性、来源及非设计重叠或接口范围证据，再执行过滤裁决。",
        "从 turbine_full.checkpoint.json 继续运行，完成剩余 6903 个候选对。",
        "对 24 个未解析 Solid 执行更严格的 SPA/拓扑定位，仍不允许顺序猜测。",
        "全量完成后重新生成统计、截图和最终 Word 验收报告。",
    ]
    for s in steps:
        p = doc.add_paragraph(style="List Number"); font(p.add_run(s), 10)
    paragraph(doc, "注：本报告仅对已完成的候选对和已验证的定位链负责，不代表对整个涡轮发动机模型完成了最终全量验收。", "注：")

    doc.core_properties.title = "涡轮发动机 CATIA 智能检查阶段性报告"
    doc.core_properties.subject = "大型单 CATPart 实机验收"
    doc.core_properties.author = "CATIA 模型智能检查系统"
    doc.save(OUT); print(OUT)


if __name__ == "__main__": build()
