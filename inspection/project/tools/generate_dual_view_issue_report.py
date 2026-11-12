import json
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artifacts" / "spatial_box_complex"
INDEX = ART / "catia_dual_view_index.json"
ANALYSIS = ART / "spatial_box_analysis.json"
OUTPUT = ART / "涡轮发动机_复杂空间框22对象_问题定位双视图_CATIA原生截图报告.docx"

BLUE = "17365D"
MID_BLUE = "D9EAF7"
LIGHT_BLUE = "EAF3F8"
RED = "C00000"
GRAY = "666666"
LIGHT_GRAY = "F2F2F2"


def shade(cell, fill):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), fill)
    tc_pr.append(shd)


def margins(cell, top=70, start=90, bottom=70, end=90):
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for tag, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = tc_mar.find(qn(f"w:{tag}"))
        if node is None:
            node = OxmlElement(f"w:{tag}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def set_repeat_table_header(row):
    tr_pr = row._tr.get_or_add_trPr()
    tbl_header = OxmlElement("w:tblHeader")
    tbl_header.set(qn("w:val"), "true")
    tr_pr.append(tbl_header)


def keep_with_next(paragraph):
    p_pr = paragraph._p.get_or_add_pPr()
    keep = OxmlElement("w:keepNext")
    p_pr.append(keep)


def set_cell_text(cell, text, bold=False, color="000000", size=8.2, align=None):
    cell.text = ""
    p = cell.paragraphs[0]
    if align is not None:
        p.alignment = align
    p.paragraph_format.space_after = Pt(0)
    r = p.add_run(str(text))
    r.bold = bold
    r.font.name = "Microsoft YaHei"
    r._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    r.font.size = Pt(size)
    r.font.color.rgb = RGBColor.from_string(color)
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    margins(cell)


def add_caption(doc, text):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(1)
    p.paragraph_format.space_after = Pt(3)
    r = p.add_run(text)
    r.font.name = "Microsoft YaHei"
    r._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    r.font.size = Pt(8.3)
    r.font.color.rgb = RGBColor.from_string(GRAY)


def add_picture(doc, path, width=7.15):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(0)
    p.add_run().add_picture(str(path), width=Inches(width))


def label_category(category):
    return {
        "UNDETERMINED": "无法确定",
        "CONTACT_OR_COPLANAR": "接触或共面",
    }.get(category, category)


def main():
    issues = json.loads(INDEX.read_text(encoding="utf-8"))
    analysis = json.loads(ANALYSIS.read_text(encoding="utf-8"))

    doc = Document()
    sec = doc.sections[0]
    sec.page_width = Inches(8.5)
    sec.page_height = Inches(11)
    sec.top_margin = Inches(0.52)
    sec.bottom_margin = Inches(0.52)
    sec.left_margin = Inches(0.58)
    sec.right_margin = Inches(0.58)

    styles = doc.styles
    normal = styles["Normal"]
    normal.font.name = "Microsoft YaHei"
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    normal.font.size = Pt(9)
    normal.paragraph_format.space_after = Pt(4)
    for name, size, color in (("Title", 25, BLUE), ("Heading 1", 16, BLUE), ("Heading 2", 12, BLUE)):
        st = styles[name]
        st.font.name = "Microsoft YaHei"
        st._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
        st.font.size = Pt(size)
        st.font.color.rgb = RGBColor.from_string(color)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(40)
    p.paragraph_format.space_after = Pt(6)
    r = p.add_run("涡轮发动机局部空间框\n干涉问题定位报告")
    r.bold = True
    r.font.name = "Microsoft YaHei"
    r._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    r.font.size = Pt(25)
    r.font.color.rgb = RGBColor.from_string(BLUE)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("CATIA V5 原生截图 · 整体定位 + 局部细节")
    r.font.name = "Microsoft YaHei"
    r._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    r.font.size = Pt(12)
    r.font.color.rgb = RGBColor.from_string(GRAY)

    t = doc.add_table(rows=5, cols=2)
    t.style = "Table Grid"
    t.autofit = False
    t.columns[0].width = Inches(2.05)
    t.columns[1].width = Inches(5.15)
    cover_rows = [
        ("检查范围", "12 × 12 × 12 mm 空间框，共 22 个 Body"),
        ("空间范围", "X −53.70～−41.70；Y 142.00～154.00；Z −70.25～−58.25 mm"),
        ("组合检查", "231 对：明确无问题 146 对；NOT_EVALUATED 85 对"),
        ("本报告呈现", f"30 个具有接触/相交证据的问题对，逐项双视图定位"),
        ("裁决原则", "不把转换噪声或无法确定项直接判为 FAIL；全部保留为 NOT_EVALUATED"),
    ]
    for i, (a, b) in enumerate(cover_rows):
        set_cell_text(t.cell(i, 0), a, bold=True, color="FFFFFF", size=9)
        shade(t.cell(i, 0), BLUE)
        set_cell_text(t.cell(i, 1), b, size=9)

    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(14)
    r = p.add_run("读图说明")
    r.bold = True
    r.font.size = Pt(12)
    r.font.color.rgb = RGBColor.from_string(BLUE)
    for text in [
        "整体定位图：保留本次框选的 22 个对象；周围对象以约 20% 不透明度显示，问题双方分别用黄色和红色高亮。",
        "局部细节图：隐藏其余对象，只保留问题双方，以便判断接触、重叠和几何关系。",
        "两类图片中的红框均由高亮像素位置自动生成，用于快速找到问题区域。",
        "模型由 STP 导出且未确认存在空腔，因此不从外观推断内流道、壁厚或管路工程语义。",
    ]:
        p = doc.add_paragraph(style="List Bullet")
        p.paragraph_format.space_after = Pt(4)
        p.add_run(text)

    doc.add_page_break()
    h = doc.add_heading("问题项索引", level=1)
    keep_with_next(h)
    p = doc.add_paragraph("下表只列本轮需要关注的 30 个问题对；146 个明确无问题的组合不写入正文。")
    p.paragraph_format.space_after = Pt(6)

    rows_per_table = 10
    for start in range(0, len(issues), rows_per_table):
        chunk = issues[start:start + rows_per_table]
        table = doc.add_table(rows=1, cols=5)
        table.style = "Table Grid"
        widths = [0.43, 1.6, 1.6, 1.18, 1.0]
        for c, w in zip(table.columns, widths):
            c.width = Inches(w)
        headers = ["序号", "对象 A", "对象 B", "分类", "相交体积/mm³"]
        for i, header in enumerate(headers):
            set_cell_text(table.cell(0, i), header, bold=True, color="FFFFFF", size=7.8, align=WD_ALIGN_PARAGRAPH.CENTER)
            shade(table.cell(0, i), BLUE)
        set_repeat_table_header(table.rows[0])
        for item in chunk:
            cells = table.add_row().cells
            values = [
                f"{item['order']:02d}",
                f"Body {item['body_a']}\n{item['name_a']}",
                f"Body {item['body_b']}\n{item['name_b']}",
                label_category(item["category"]),
                f"{item['volume_mm3']:.6g}",
            ]
            for i, value in enumerate(values):
                set_cell_text(cells[i], value, size=7.2, align=WD_ALIGN_PARAGRAPH.CENTER if i in (0, 3, 4) else None)
                if item["category"] == "CONTACT_OR_COPLANAR":
                    shade(cells[i], LIGHT_BLUE)
        if start + rows_per_table < len(issues):
            doc.add_page_break()

    for item in issues:
        doc.add_page_break()
        h = doc.add_heading(f"问题 {item['order']:02d}　Body {item['body_a']} ↔ Body {item['body_b']}", level=1)
        h.paragraph_format.space_after = Pt(3)
        table = doc.add_table(rows=2, cols=4)
        table.style = "Table Grid"
        labels = [
            ("对象 A", f"Body {item['body_a']} · {item['name_a']}"),
            ("对象 B", f"Body {item['body_b']} · {item['name_b']}"),
            ("分类", label_category(item["category"])),
            ("精确相交体积", f"{item['volume_mm3']:.9g} mm³"),
        ]
        for i, (lab, val) in enumerate(labels):
            row, col = divmod(i, 2)
            cell = table.cell(row, col * 2)
            set_cell_text(cell, lab, bold=True, color="FFFFFF", size=8.2)
            shade(cell, BLUE)
            set_cell_text(table.cell(row, col * 2 + 1), val, size=8.1)

        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(3)
        p.paragraph_format.space_after = Pt(3)
        r = p.add_run("裁决：NOT_EVALUATED。当前证据只证明存在接触或相交，尚无装配许可、接口定义或同源转换证据，不能直接判 FAIL，也不能判 PASS。")
        r.bold = True
        r.font.size = Pt(8.6)
        r.font.color.rgb = RGBColor.from_string(RED)

        add_picture(doc, Path(item["context_image"]), 7.15)
        add_caption(doc, "整体定位图：周围对象低不透明度显示；黄/红为问题双方；红框为问题位置。")
        add_picture(doc, Path(item["detail_image"]), 7.15)
        add_caption(doc, "局部细节图：仅显示问题双方；红框为接触或相交区域。")

    doc.add_page_break()
    doc.add_heading("管路规范检查结果", level=1)
    p = doc.add_paragraph(
        "本次 22 个 Body 中共筛出 4 个弯曲管状候选。Body 840、841 已获得圆截面扫掠外形证据，但估算外径小于 HB 4-55-2002 分析配置的 4～80 mm 适用范围；Body 741、839 具有更明显的连续管路走向，但其复合外形尚未完成可靠的中心线与截面重建。四者均保留为 NOT_EVALUATED。直圆柱外观对象未仅凭外形认定为管路，以避免把螺栓等紧固件误判为导管。"
    )
    p.paragraph_format.space_after = Pt(8)
    table = doc.add_table(rows=1, cols=6)
    table.style = "Table Grid"
    headers = ["Body", "STP 名称", "估算 D/mm", "估算 R/mm", "R/D", "结论"]
    for i, header in enumerate(headers):
        set_cell_text(table.cell(0, i), header, bold=True, color="FFFFFF", size=8, align=WD_ALIGN_PARAGRAPH.CENTER)
        shade(table.cell(0, i), BLUE)
    pipe_rows = [
        (741, "MANIFOLD_SOLID_BREP #39261", None, None, None, "NOT_EVALUATED"),
        (839, "MANIFOLD_SOLID_BREP #39357", None, None, None, "NOT_EVALUATED"),
        (840, "MANIFOLD_SOLID_BREP #39358", 0.475054, 1.694027, 3.56597, "NOT_EVALUATED"),
        (841, "MANIFOLD_SOLID_BREP #39359", 0.500050, 1.175899, 2.35156, "NOT_EVALUATED"),
    ]
    for row in pipe_rows:
        cells = table.add_row().cells
        vals = [str(row[0]), row[1], "待重建" if row[2] is None else f"{row[2]:.6f}", "待重建" if row[3] is None else f"{row[3]:.6f}", "待重建" if row[4] is None else f"{row[4]:.5f}", row[5]]
        for i, val in enumerate(vals):
            set_cell_text(cells[i], val, size=7.8, align=WD_ALIGN_PARAGRAPH.CENTER if i != 1 else None)

    doc.add_heading("CATIA 管路候选截图", level=2)
    p = doc.add_paragraph(
        "下图中的两条细长弯曲实体分别为 Body 840 与 Body 841。该截图用于确认对象位置和外观；“管状外观”本身不等于已经确认的工程管路语义。"
    )
    p.paragraph_format.space_after = Pt(4)
    add_picture(doc, ART / "catia_pipe_screenshots" / "pipe_candidates_context.jpg", 7.15)
    add_caption(doc, "整体位置图：管路候选位于框选集合体右侧及下方，并与主体结构相邻。")
    add_picture(doc, ART / "catia_pipe_screenshots" / "pipe_candidates_detail.jpg", 7.15)
    add_caption(doc, "隔离放大图：Body 840 与 Body 841 两个弯曲管状候选实体。")

    doc.add_page_break()
    doc.add_heading("新增管路候选：Body 741 与 Body 839", level=2)
    p = doc.add_paragraph(
        "Body 741（绿色）和 Body 839（橙色）均呈连续弯曲、细长且近似恒定截面的路线外观，明显区别于短直圆柱紧固件。Body 839 的外形识别结果仍属于复合路线待复核，Body 741 也尚未建立可靠中心线，因此本页只确认其为优先管路候选，不签发弯曲半径合格结论。"
    )
    add_picture(doc, ART / "catia_pipe_screenshots" / "additional_pipe_candidates_context.jpg", 7.15)
    add_caption(doc, "整体定位图：周围集合体透明显示；绿色为 Body 741，橙色为 Body 839。")
    add_picture(doc, ART / "catia_pipe_screenshots" / "additional_pipe_candidates_detail.jpg", 7.15)
    add_caption(doc, "隔离放大图：两条新增管路候选的完整走向。")

    doc.add_heading("结论与下一步", level=2)
    for text in [
        "本轮空间框内未自动签发 FAIL：30 个可定位问题对均保留为 NOT_EVALUATED，等待装配关系或人工复核。",
        "优先在 CATIA 中复核相交体积较大、整体图中位置集中的问题对；确认属于允许连接后，可加入允许连接清单。",
        "STP 转换来源关系尚不足时，不把微小重叠直接升级为真实穿模。",
        "若要完成管路规范闭环，需要补充可确认的管路对象、真实外径/中心线或原生 CATIA 管路特征。",
    ]:
        doc.add_paragraph(text, style="List Bullet")

    for section in doc.sections:
        footer = section.footer.paragraphs[0]
        footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = footer.add_run("CATIA V5 空间框精确检查 · 仅问题项")
        run.font.name = "Microsoft YaHei"
        run._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
        run.font.size = Pt(7.5)
        run.font.color.rgb = RGBColor.from_string(GRAY)

    doc.save(OUTPUT)
    print(OUTPUT)


if __name__ == "__main__":
    main()
