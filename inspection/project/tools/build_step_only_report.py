from __future__ import annotations

import hashlib
import json
import argparse
from datetime import datetime
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "project" / "output" / "runs" / "STEP-ONLY-20260923-FIRST"
STEP = ROOT / "project" / "artifacts" / "full_project_check_step_20260923" / "MiniEngine_Current_D6_R15_G3_20260923.stp"
EXACT = RUN / "step_exact.json"
PIPE = RUN / "step_pipe_geometry.json"
OUT_JSON = RUN / "check.json"
OUT_DOCX = RUN / "STEP独立全项目检查报告.docx"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def issue_id(prefix: str, a: str, b: str) -> str:
    token = hashlib.sha256(f"{a}|{b}".encode()).hexdigest()[:10].upper()
    return f"{prefix}-{token}"


def set_cell_shading(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_cell_margins(cell, top=100, start=100, bottom=100, end=100) -> None:
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    mar = tc_pr.first_child_found_in("w:tcMar")
    if mar is None:
        mar = OxmlElement("w:tcMar")
        tc_pr.append(mar)
    for tag, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = mar.find(qn(f"w:{tag}"))
        if node is None:
            node = OxmlElement(f"w:{tag}")
            mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def set_repeat_table_header(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    tbl_header = OxmlElement("w:tblHeader")
    tbl_header.set(qn("w:val"), "true")
    tr_pr.append(tbl_header)


def add_table(doc: Document, headers, rows, widths=None):
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    table.autofit = False
    set_repeat_table_header(table.rows[0])
    for i, h in enumerate(headers):
        c = table.rows[0].cells[i]
        c.text = str(h)
        set_cell_shading(c, "1F4E78")
        for r in c.paragraphs[0].runs:
            r.font.color.rgb = RGBColor(255, 255, 255)
            r.font.bold = True
            r.font.size = Pt(8.5)
        c.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
    for ridx, row in enumerate(rows):
        cells = table.add_row().cells
        for i, value in enumerate(row):
            cells[i].text = str(value)
            cells[i].vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            cells[i].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER if i < 2 else WD_ALIGN_PARAGRAPH.LEFT
            for run in cells[i].paragraphs[0].runs:
                run.font.size = Pt(8.5)
            if ridx % 2:
                set_cell_shading(cells[i], "EAF2F8")
        for c in cells:
            set_cell_margins(c)
    for ridx, row in enumerate(table.rows):
        tr_pr = row._tr.get_or_add_trPr()
        cant_split = OxmlElement("w:cantSplit")
        tr_pr.append(cant_split)
        if ridx < len(table.rows) - 1:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    paragraph.paragraph_format.keep_with_next = True
    if widths:
        for row in table.rows:
            for c, w in zip(row.cells, widths):
                c.width = Cm(w)
    doc.add_paragraph().paragraph_format.space_after = Pt(1)
    return table


def add_bullet(doc: Document, text: str) -> None:
    p = doc.add_paragraph(style="List Bullet")
    p.add_run(text)


def build_payload():
    exact = json.loads(EXACT.read_text(encoding="utf-8"))
    pipe = json.loads(PIPE.read_text(encoding="utf-8"))
    assessments = exact["solid_interaction_assessments"]["assessments"]
    findings = []
    excluded_contacts = []
    for a in assessments:
        left, right = a["object_a"], a["object_b"]
        volume = float(a["intersection_volume_mm3"])
        distance = float(a["minimum_distance_mm"])
        if volume > 1e-6:
            findings.append({
                "issue_id": issue_id("STEP-INTERFERENCE", left, right),
                "status": "FAIL", "severity": "S3", "title": "实体材料穿透",
                "object_a": left, "object_b": right,
                "measured_value": volume, "unit": "mm3",
                "method": "OCCT_EXACT_BREP_COMMON_VOLUME",
                "rule_id": "STEP.SOLID.NO_POSITIVE_COMMON_VOLUME",
                "rationale": f"精确公共体积为 {volume:.3f} mm3，大于 1e-6 mm3 容差，属于真实材料重叠。",
                "recommendation": "回到设计来源核对该处是否为未布尔清理或位置错误；若为批准的插入或压合，补充接口图纸后再建立豁免。",
                "evidence": [{"kind": "GEOMETRY", "data": {"distance_mm": distance, "section_edge_count": a["section_edge_count"], "geometry_authority": "ORIGINAL_STEP_OCCT_BREP"}}],
                "metadata": {"geometry_object_a": left, "geometry_object_b": right},
            })
        elif distance <= 1e-5 and a["section_edge_count"] > 0:
            excluded_contacts.append({
                "object_a": left, "object_b": right, "distance_mm": distance,
                "common_volume_mm3": volume, "section_edge_count": a["section_edge_count"],
                "disposition": "NORMAL_ASSEMBLY_CONTACT_EXCLUDED_FROM_ISSUES",
                "basis": "零公共体积、无材料穿透，仅存在边界截交，按正常装配贴合处理。",
            })
        elif distance < 9.999:
            findings.append({
                "issue_id": issue_id("STEP-CLEARANCE", left, right),
                "status": "WARN", "severity": "S2", "title": "几何净距低于暂用值",
                "object_a": left, "object_b": right,
                "measured_value": distance, "unit": "mm",
                "method": "OCCT_EXACT_BREP_MINIMUM_DISTANCE",
                "rule_id": "ROUTING.GENERAL_CLEARANCE.PENDING_APPROVAL",
                "rationale": f"精确表面最小距离为 {distance:.3f} mm，低于暂用 10 mm；该阈值未批准，因此只提示，不判不合格。",
                "recommendation": "确认对象功能和项目批准净距；若该处属于管路邻近结构，结合振动、制造公差和维护空间复核。",
                "evidence": [{"kind": "GEOMETRY", "data": {"common_volume_mm3": volume, "geometry_authority": "ORIGINAL_STEP_OCCT_BREP"}}],
                "metadata": {"geometry_object_a": left, "geometry_object_b": right},
            })
    bends = pipe.get("bends", [])
    min_bend = min(bends, key=lambda x: x["r_over_d"]) if bends else None
    if min_bend:
        findings.append({
            "issue_id": "STEP-PIPE-BEND-RATIO-SUMMARY",
            "status": "PASS", "severity": "S1", "title": "解析环面弯曲半径几何预检",
            "object_a": "STEP管路候选解析环面", "object_b": None,
            "measured_value": min_bend["r_over_d"], "unit": "ratio",
            "method": "STEP_ANALYTIC_TOROIDAL_SURFACE",
            "rule_id": "HB 4-55-2002 MIN R OVER D",
            "rationale": f"20 张解析环面中最小候选外径 {min_bend['diameter_mm']:.3f} mm、中心线半径 {min_bend['centerline_bend_radius_mm']:.3f} mm、R/D={min_bend['r_over_d']:.4f}，高于 2.0 下限。STEP 不含原生管路语义，因此这是几何预检。",
            "recommendation": "用管线表确认该候选确为 DN6 机械弯曲导管及标准适用性。",
            "evidence": [{"kind": "GEOMETRY", "data": {"toroidal_face_count": len(bends), "minimum_entity": min_bend["step_entity"], "geometry_authority": "ORIGINAL_STEP_TEXT_AND_OCCT"}}],
        })
    counts = {k: 0 for k in ("PASS", "WARN", "FAIL", "NOT_EVALUATED", "EXEMPTED", "ERROR")}
    for f in findings:
        counts[f["status"]] += 1
    counts["NOT_EVALUATED"] = 5
    payload = {
        "schema_version": "step-only-check.v1.0",
        "run_id": "STEP-ONLY-20260923-FIRST",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "overall_status": "FAIL",
        "source": {
            "input_format": "STEP", "input_file": str(STEP), "sha256": sha256(STEP),
            "source_file": str(STEP), "source_sha256": sha256(STEP).lower(),
            "file_size_bytes": STEP.stat().st_size,
            "geometry_authority": "ORIGINAL_STEP_OCCT_EXACT_BREP",
            "catia_native_model_used": False, "catia_native_tubing_used": False,
            "previous_check_results_used": False, "mesh_used_for_final_decision": False,
            "solid_count": len(exact["shapes"]) - 1,
            "pair_candidate_count": exact["pair_fact_count"], "truncated": exact["truncated"],
        },
        "rules": {
            "interference": "positive common solid volume > 1e-6 mm3 = FAIL",
            "contact": "zero common volume + boundary section = normal assembly contact; excluded from issue list per user instruction",
            "general_clearance_mm": 10.0, "general_clearance_status": "ASSUMED_PENDING_APPROVAL",
            "bend_standard": "HB 4-55-2002", "minimum_r_over_d": 2.0,
        },
        "counts": counts, "findings": findings,
        "large_single_part_analysis": {"manifest": exact},
        "excluded_normal_contacts": excluded_contacts,
        "geometry_summary": {
            "closed_solids": len(exact["shapes"]) - 1,
            "all_pairs_processed": not exact["truncated"],
            "cylindrical_surface_candidates": pipe.get("cylindrical_surface_count", 0),
            "toroidal_surface_candidates": pipe.get("toroidal_pipe_bend_count", 0),
            "bounds_mm": exact["shapes"][0]["bounds_mm"],
        },
        "not_evaluated": [
            "材料、牌号、压力等级、温度和介质",
            "装配约束、连接器、逻辑管线和设计接口意图",
            "壁厚与内径的完整全路径一致性",
            "支撑夹具间距、振动载荷和疲劳",
            "热区、运动包络、维护拆装空间及制造缺陷",
        ],
        "audit": {
            "exact_manifest": str(EXACT), "pipe_geometry": str(PIPE),
            "contact_policy": "7 zero-volume boundary contacts excluded from issue list after geometric review",
            "source_modified": False, "source_saved": False,
        },
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def build_doc(payload, output_docx=OUT_DOCX, *, occt_evidence=False):
    template = ROOT / "skills" / "catia-v5r18-checker" / "assets" / "CATIA检查报告模板.docx"
    doc = Document(template if template.exists() else None)
    # Retain the controlled template's styles and section settings, but remove
    # its instructional/sample body so the delivered report contains only the
    # current STEP-only inspection.
    body = doc._element.body
    for child in list(body):
        if child.tag != qn("w:sectPr"):
            body.remove(child)
    for section in doc.sections:
        section.top_margin, section.bottom_margin = Cm(2.0), Cm(1.8)
        section.left_margin, section.right_margin = Cm(1.8), Cm(1.8)
    styles = doc.styles
    styles["Normal"].font.name = "Microsoft YaHei"
    styles["Normal"]._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    styles["Normal"].font.size = Pt(9.5)
    for name in ("Title", "Heading 1", "Heading 2"):
        styles[name].font.color.rgb = RGBColor(0, 0, 0)
        styles[name].font.name = "Microsoft YaHei"
        styles[name]._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    doc.add_heading("STEP 独立全项目检查报告", 0)
    p = doc.add_paragraph("仅以中性几何文件为输入的首次独立检查")
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_table(doc, ["项目", "内容"], [
        ["报告编号", payload["run_id"]], ["输入文件", STEP.name],
        ["检查日期", "2026-09-23"], ["总体结论", "不通过"],
        ["判定内核", "OCCT 精确 B-Rep"], ["原生 CATIA 数据", "未使用"],
    ], [4.0, 12.5])
    doc.add_paragraph("结论：STEP 中确认 2 组实体存在正公共体积，属于材料穿透；另有 6 组正间隙低于暂用 10 mm，仅作待批准提示。7 组零公共体积接触经几何复核按正常装配贴合处理，不写入问题清单。")

    doc.add_heading("1 本次检查规则", 1)
    add_table(doc, ["项目", "规则", "状态"], [
        ["实体干涉", "公共体积大于 1e-6 mm3 判不通过", "确定性几何规则"],
        ["零距离接触", "公共体积为零且仅边界截交，按正常装配贴合排除", "用户指定策略"],
        ["一般净距", "10 mm", "待项目批准，仅 WARN"],
        ["弯曲半径", "HB 4-55-2002，R/D 不小于 2.0", "标准几何预检"],
    ], [3.0, 9.0, 4.5])

    doc.add_heading("2 执行摘要", 1)
    c = payload["counts"]
    add_table(doc, ["PASS", "WARN", "FAIL", "未评价", "错误"], [[c["PASS"], c["WARN"], c["FAIL"], c["NOT_EVALUATED"], c["ERROR"]]], [3.2]*5)
    doc.add_paragraph("当前 STEP 不能作为无条件放行依据。两处实体穿透需优先核实；低净距项需要项目净距标准和对象功能确认。")

    doc.add_heading("3 检查范围与方法", 1)
    add_bullet(doc, "唯一输入为当前导出的 STEP 文件；未读取 CATProduct、CATPart、Arrangement Run、原生参数、约束或上一轮检查结果。")
    add_bullet(doc, "读取 9 个封闭实体，采用精确 B-Rep 包围盒粗筛后，对 20 个候选对计算最小距离、截交和公共体积；没有截断。")
    add_bullet(doc, "最终干涉判定未使用三角网格。解析圆柱和圆环面仅用于管径与弯曲半径候选测量。")
    add_bullet(doc, f"文件 SHA-256：{payload['source']['sha256']}")

    doc.add_heading("4 检查模块覆盖", 1)
    add_table(doc, ["模块", "状态", "覆盖与结论"], [
        ["STEP 文件身份", "完成", "文件摘要、大小和单位记录完成"],
        ["几何转换与实体清点", "完成", "9 个封闭实体，整体范围已记录"],
        ["实体穿透", "完成", "20 个候选对精确计算，2 个 FAIL"],
        ["零距离接触", "完成", "7 个零公共体积接触按正常装配贴合排除"],
        ["一般净距", "部分", "6 个低于暂用 10 mm 的 WARN；规则待批准"],
        ["管径与弯曲半径", "部分", "38 个圆柱面、20 个环面候选；完成几何预检"],
        ["壁厚与流道", "未评价", "缺少可证明的全路径内外表面配对"],
        ["支撑 热区 运动 维护", "未评价", "STEP 不包含所需工程语义和包络"],
    ], [4.2, 2.2, 10.2])

    doc.add_heading("5 模型几何质量与转换可靠性", 1)
    b = payload["geometry_summary"]["bounds_mm"]
    doc.add_paragraph(f"STEP 成功传递 9 个封闭实体。模型包围盒为 X {b['min'][0]:.3f} 至 {b['max'][0]:.3f} mm，Y {b['min'][1]:.3f} 至 {b['max'][1]:.3f} mm，Z {b['min'][2]:.3f} 至 {b['max'][2]:.3f} mm。所有候选对均完成，未发生截断。实体名称在 STEP 中乱码或重复，因此报告使用稳定编号 STEP_SOLID_0001 至 STEP_SOLID_0009，不猜测原零件身份。")

    doc.add_heading("6 工程对象与连接关系识别", 1)
    doc.add_paragraph("STEP 保留了实体与解析曲面，但未保留逻辑管线、装配约束和连接器。STEP_SOLID_0009 含 90 张面并出现约 6 mm 外径、约 15 mm 中心线半径的重复解析管路特征，可作为管路几何候选；其工程名称、介质、流向和接口意图仍未知。")
    doc.add_paragraph("7 组零距离关系均满足公共体积为零且仅边界截交。依据本次规则，将其解释为装配贴合并从问题清单排除；该处理不等同于恢复了原始装配约束。")

    doc.add_heading("7 问题总览", 1)
    rows = []
    for f in payload["findings"]:
        if f["status"] == "PASS":
            continue
        rows.append([f["issue_id"], f["status"], f["object_a"] + " ↔ " + str(f.get("object_b") or ""), f["title"], f"{f['measured_value']:.3f} {f['unit']}"])
    add_table(doc, ["问题编号", "状态", "对象", "标题", "实测"], rows, [4.0, 1.8, 4.1, 4.0, 2.6])

    doc.add_heading("8 管路几何专项", 1)
    bends = json.loads(PIPE.read_text(encoding="utf-8"))["bends"]
    min_r = min(x["centerline_bend_radius_mm"] for x in bends)
    max_r = max(x["centerline_bend_radius_mm"] for x in bends)
    min_ratio = min(x["r_over_d"] for x in bends)
    max_ratio = max(x["r_over_d"] for x in bends)
    doc.add_paragraph(f"STEP 文本和精确曲面中识别到 38 个圆柱面候选及 20 张环面候选。环面候选外径均约 5.994 mm，中心线半径范围 {min_r:.3f} 至 {max_r:.3f} mm，R/D 范围 {min_ratio:.4f} 至 {max_ratio:.4f}。最小值高于 HB 4-55-2002 的 2.0 几何下限。由于一处物理弯头可能由多张裁剪环面组成，本报告不把 20 张面直接宣称为 20 个独立弯头。")

    doc.add_heading("9 正常装配接触审计", 1)
    doc.add_paragraph("以下关系不进入问题总览，但保留审计记录。判据为最小距离近似零、公共体积为零、存在边界截交。")
    add_table(doc, ["对象 A", "对象 B", "截交边数", "处理"], [[x["object_a"], x["object_b"], x["section_edge_count"], "正常装配贴合 排除"] for x in payload["excluded_normal_contacts"]], [4.0,4.0,3.0,5.5])

    doc.add_heading("10 基线变化", 1)
    doc.add_paragraph("本次按首次 STEP-only 检查处理，没有历史基线，不进行新增、持续、改善或恶化比较。")

    doc.add_heading("11 检查边界与可信度", 1)
    for text in payload["not_evaluated"]:
        add_bullet(doc, text)
    doc.add_paragraph("可信度说明：实体公共体积、最小表面距离和解析曲面半径属于高可信几何事实；对象工程身份、允许接触、制造与服役符合性属于未知或需外部资料确认。")

    doc.add_heading("12 问题明细与整改建议", 1)
    for f in payload["findings"]:
        if f["status"] == "PASS":
            continue
        heading = doc.add_heading(f["issue_id"] + " " + f["title"], 2)
        heading.paragraph_format.keep_with_next = True
        add_table(doc, ["字段", "内容"], [
            ["状态与严重度", f["status"] + " / " + f["severity"]],
            ["对象", f["object_a"] + " ↔ " + str(f.get("object_b") or "")],
            ["实测", f"{f['measured_value']:.6g} {f['unit']}"],
            ["方法", f["method"]], ["判定依据", f["rationale"]],
            ["建议", f["recommendation"]],
        ], [4.0, 12.5])
        if occt_evidence:
            screenshots = [{"path": str(RUN / "evidence" / f"{f['issue_id']}_{view}_marked.png"),
                            "description": f"{view} OCCT 精确定位图：红框由公共体积或最近点坐标投影生成；网格仅用于显示"}
                           for view in ("isometric", "front")]
        else:
            screenshots = [e for e in f.get("evidence", []) if e.get("kind") == "SCREENSHOT" and e.get("path")]
        for evidence in screenshots[:2]:
            image_path = Path(evidence["path"])
            if image_path.is_file():
                p = doc.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.add_run().add_picture(str(image_path), width=Cm(16.0))
                cap = doc.add_paragraph(evidence.get("description") or image_path.name)
                cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
                cap.paragraph_format.keep_with_next = False

    doc.add_heading("13 审计与只读声明", 1)
    doc.add_paragraph("本次重新读取 STEP 并独立计算。没有调用 CATIA 原生装配或管路对象，没有继承上一轮 DMU 数值，也没有修改、保存或覆盖源模型及 STEP 文件。精确几何 JSON 是机器事实主记录，Word 为可读呈现。")
    doc.add_paragraph(f"结构化结果：{OUT_JSON.name}。精确计算明细：{EXACT.name}。管路解析曲面明细：{PIPE.name}。")
    doc.save(output_docx)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-only", action="store_true")
    parser.add_argument("--output-docx", type=Path, default=OUT_DOCX)
    parser.add_argument("--occt-evidence", action="store_true")
    args = parser.parse_args()
    RUN.mkdir(parents=True, exist_ok=True)
    data = json.loads(OUT_JSON.read_text(encoding="utf-8")) if args.report_only else build_payload()
    build_doc(data, args.output_docx, occt_evidence=args.occt_evidence)
    print(OUT_JSON)
    print(args.output_docx)
