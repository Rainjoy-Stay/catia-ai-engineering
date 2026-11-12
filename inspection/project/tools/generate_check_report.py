"""Generate a unified CATIA inspection report in Word from result JSON.

The resulting DOCX is the formal human-readable report for this package.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any, Iterable

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
REPORT_TEMPLATE = ROOT.parent / "skills" / "catia-v5r18-checker" / "assets" / "CATIA检查报告模板.docx"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


COLORS = {
    "navy": "17365D", "blue": "2E5E8C", "light_blue": "E8EEF5",
    "ink": "263238", "muted": "607080", "line": "CBD5E1",
    "light": "F5F7FA", "pass": "18794E", "warn": "B54708",
    "fail": "B42318", "not_evaluated": "667085", "exempted": "175CD3",
    "error": "7A271A", "white": "FFFFFF",
}
STATUS_LABEL = {
    "PASS": "通过", "WARN": "警告", "FAIL": "失败",
    "NOT_EVALUATED": "未评价", "EXEMPTED": "已豁免", "ERROR": "错误",
}
STATUS_ORDER = ("FAIL", "ERROR", "WARN", "NOT_EVALUATED", "EXEMPTED", "PASS")

ENGINEERING_TYPE_LABEL = {
    "TUBULAR_COMPONENT_CANDIDATE": "管状组件候选",
    "PIPE_BEND_CANDIDATE": "管路弯头候选",
    "PLANAR_BOUNDARY_CANDIDATE": "平面边界候选",
    "UNRESOLVED": "未解析",
}

MODULES = (
    ("model_precheck", "模型几何预检"),
    ("large_single_part_analysis", "大型单 Part 精确检查"),
    ("logical_components", "逻辑组件恢复"),
    ("pipe_logical_components", "逻辑管路组装"),
    ("engineering_roles", "工程角色识别"),
    ("semantic_intersection_events", "表面交叉事件聚合"),
    ("solid_interaction_assessments", "实体交互语义判定"),
    ("opening_interface_analysis", "接管与开孔接口判定"),
    ("opening_interface_auto_discovery", "开孔接口自动发现"),
    ("pipe_candidate_review", "管路候选复核"),
)


def _set_cell_shading(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def _set_cell_width(cell, width_dxa: int) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_w = tc_pr.find(qn("w:tcW"))
    if tc_w is None:
        tc_w = OxmlElement("w:tcW")
        tc_pr.append(tc_w)
    tc_w.set(qn("w:w"), str(width_dxa))
    tc_w.set(qn("w:type"), "dxa")


def _set_table_geometry(table, widths_dxa: Iterable[int], indent_dxa: int = 120) -> None:
    widths = list(widths_dxa)
    table.autofit = False
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    tbl_pr = table._tbl.tblPr
    tbl_w = tbl_pr.find(qn("w:tblW"))
    if tbl_w is None:
        tbl_w = OxmlElement("w:tblW")
        tbl_pr.append(tbl_w)
    tbl_w.set(qn("w:w"), str(sum(widths)))
    tbl_w.set(qn("w:type"), "dxa")
    tbl_ind = tbl_pr.find(qn("w:tblInd"))
    if tbl_ind is None:
        tbl_ind = OxmlElement("w:tblInd")
        tbl_pr.append(tbl_ind)
    tbl_ind.set(qn("w:w"), str(indent_dxa))
    tbl_ind.set(qn("w:type"), "dxa")
    grid = table._tbl.tblGrid
    for child in list(grid):
        grid.remove(child)
    for width in widths:
        col = OxmlElement("w:gridCol")
        col.set(qn("w:w"), str(width))
        grid.append(col)
    for row in table.rows:
        for index, cell in enumerate(row.cells):
            _set_cell_width(cell, widths[index])
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER


def _repeat_header(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    repeat = OxmlElement("w:tblHeader")
    repeat.set(qn("w:val"), "true")
    tr_pr.append(repeat)


def _cant_split(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    tr_pr.append(OxmlElement("w:cantSplit"))


def _set_cell_text(cell, text: Any, *, bold: bool = False, color: str | None = None,
                   size: float = 8.5, align=None) -> None:
    cell.text = ""
    paragraph = cell.paragraphs[0]
    paragraph.paragraph_format.space_before = Pt(0)
    paragraph.paragraph_format.space_after = Pt(0)
    paragraph.paragraph_format.line_spacing = 1.05
    if align is not None:
        paragraph.alignment = align
    run = paragraph.add_run("-" if text is None or text == "" else str(text))
    _font(run, size=size, bold=bold, color=color or COLORS["ink"])


def _display(value: Any) -> str:
    if value is None or value == "":
        return "-"
    if isinstance(value, bool):
        return "是" if value else "否"
    return str(value)


def _font(run, *, size: float, bold: bool = False, color: str = COLORS["ink"],
          name: str = "Microsoft YaHei") -> None:
    run.font.name = name
    run._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), name)
    run.font.size = Pt(size)
    run.bold = bold
    run.font.color.rgb = RGBColor.from_string(color)


def _add_page_number(paragraph) -> None:
    paragraph.add_run("第 ")
    run = paragraph.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = " PAGE "
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    run._r.extend((begin, instr, end))
    paragraph.add_run(" 页")


def _configure_document(doc: Document, report_title: str) -> None:
    section = doc.sections[0]
    section.page_width, section.page_height = Cm(21.0), Cm(29.7)
    section.top_margin, section.bottom_margin = Cm(2.0), Cm(1.8)
    section.left_margin, section.right_margin = Cm(2.0), Cm(2.0)
    section.header_distance, section.footer_distance = Cm(0.8), Cm(0.8)

    styles = doc.styles
    normal = styles["Normal"]
    normal.font.name = "Microsoft YaHei"
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    normal.font.size = Pt(10)
    normal.font.color.rgb = RGBColor.from_string(COLORS["ink"])
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.15
    for name, size, color, before, after in (
        ("Title", 24, "000000", 0, 8),
        ("Heading 1", 16, "000000", 14, 7),
        ("Heading 2", 12.5, "000000", 10, 5),
        ("Heading 3", 11, "000000", 8, 4),
    ):
        style = styles[name]
        style.font.name = "Microsoft YaHei"
        style._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = RGBColor.from_string(color)
        style.paragraph_format.space_before = Pt(before)
        style.paragraph_format.space_after = Pt(after)
        style.paragraph_format.keep_with_next = True
        p_pr = style._element.get_or_add_pPr()
        p_bdr = p_pr.find(qn("w:pBdr"))
        if p_bdr is not None:
            p_pr.remove(p_bdr)

    header = section.header.paragraphs[0]
    header.text = "CATIA 模型几何质量检查系统"
    header.alignment = WD_ALIGN_PARAGRAPH.LEFT
    _font(header.runs[0], size=8, color=COLORS["muted"])
    footer = section.footer.paragraphs[0]
    footer.text = ""
    footer.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    _add_page_number(footer)
    for run in footer.runs:
        _font(run, size=8, color=COLORS["muted"])

    doc.core_properties.title = report_title
    doc.core_properties.subject = "CATIA V5 几何质量 工程语义与装配检查报告"
    doc.core_properties.author = "CATIA 管路与模型检查系统"
    doc.core_properties.keywords = "CATIA, DMU, BREP, STEP, Clash, Semantics, Inspection"


def _overall_status(data: dict[str, Any]) -> tuple[str, str]:
    counts = data.get("counts", {})
    source = data.get("source", {})
    budget = data.get("confidence_budget", {})
    rules = data.get("applied_rules") or {}
    if counts.get("ERROR", 0):
        return "检查异常", "ERROR"
    if source.get("cleanup_verified") is False:
        return "检查异常", "ERROR"
    semantic_fail = sum(int((data.get(key) or {}).get("disposition_counts", {}).get("FAIL", 0))
                        for key in ("semantic_intersection_events",
                                    "solid_interaction_assessments",
                                    "opening_interface_analysis"))
    if counts.get("FAIL", 0) or semantic_fail:
        return "不通过", "FAIL"
    precheck = data.get("model_precheck") or {}
    semantic_review = sum(int((data.get(key) or {}).get("disposition_counts", {}).get("REVIEW", 0))
                          for key in ("semantic_intersection_events",
                                      "solid_interaction_assessments",
                                      "opening_interface_analysis"))
    incomplete = (source.get("truncated") is True or bool(budget.get("not_checked"))
                  or bool(budget.get("degraded")) or not budget.get("checked")
                  or precheck.get("model_reliability") == "LOW"
                  or bool(precheck.get("issues")) or semantic_review > 0)
    approved = rules.get("routing", {}).get("threshold_status") == "APPROVED"
    if incomplete or not approved or counts.get("WARN", 0) or counts.get("NOT_EVALUATED", 0):
        return "检查不完整 / 需要复核", "WARN"
    return "通过", "PASS"


def _add_cover(doc: Document, data: dict[str, Any], report_id: str) -> None:
    for _ in range(3):
        doc.add_paragraph()
    kicker = doc.add_paragraph()
    kicker.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _font(kicker.add_run("CATIA V5 · DMU SPACE ANALYSIS"), size=10, bold=True, color=COLORS["blue"])
    title = doc.add_paragraph(style="Title")
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.add_run("CATIA V5 智能工程检查报告")
    subtitle = doc.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _font(subtitle.add_run(str(data.get("document", "UNKNOWN"))), size=14, bold=True,
          color=COLORS["muted"])

    counts = data.get("counts", {})
    overall, overall_key = _overall_status(data)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.space_after = Pt(18)
    _font(p.add_run(overall), size=17, bold=True, color=COLORS[overall_key.lower()])

    metadata = [
        ("报告编号", report_id),
        ("规则集", data.get("ruleset_id", "UNKNOWN")),
        ("检查方法", data.get("source", {}).get("method", "UNKNOWN")),
        ("计算范围", data.get("source", {}).get("computation_type", "UNKNOWN")),
        ("生成时间", datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")),
    ]
    table = doc.add_table(rows=len(metadata), cols=2)
    table.style = "Table Grid"
    for row, (label, value) in zip(table.rows, metadata):
        _set_cell_text(row.cells[0], label, bold=True, color=COLORS["navy"], size=9)
        _set_cell_text(row.cells[1], value, size=9)
        _set_cell_shading(row.cells[0], COLORS["light_blue"])
    _set_table_geometry(table, (2100, 7000))

    note = doc.add_paragraph()
    note.paragraph_format.space_before = Pt(18)
    note.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _font(note.add_run("组件级几何事实来自 CATIA 原生 DMU；Face/Surface 级事实来自 CATIA SPA/原生拓扑；截图和 AI 文字仅用于定位与解释。"),
          size=8.5, color=COLORS["muted"])
    doc.add_page_break()


def _add_rules(doc: Document, data: dict[str, Any]) -> None:
    doc.add_heading("1. 本次检查规则", level=1)
    rules = data.get("applied_rules") or {}
    routing, dmu, source = rules.get("routing", {}), rules.get("dmu_clash", {}), rules.get("source", {})
    opening = rules.get("opening_interface", {})
    mode = routing.get("bend_radius_mode", "ratio_r_over_d")
    if mode == "absolute_mm":
        bend_value = f"{routing.get('minimum_bend_radius_mm')} mm"
    elif mode == "standard_profile":
        from catia_checker.routing_rules import load_bend_radius_profile
        try:
            profile = load_bend_radius_profile(routing)
            override = (routing.get('bend_radius_overrides') or {}).get('minimum_ratio_r_over_d')
            ratio = override if override is not None else profile.get('minimum_bend_radius_ratio_r_over_d')
            bend_value = f"R/DN >= {ratio} ({profile.get('standard_id', '标准配置')})"
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            bend_value = "标准配置不可用"
    else:
        bend_value = f"{routing.get('minimum_bend_radius_ratio_r_over_d')} D"
    rows = (
        ("规则集", data.get("ruleset_id", "UNKNOWN")),
        ("审批状态", routing.get("threshold_status", "UNKNOWN")),
        ("来源文件", source.get("title") or routing.get("standard_reference") or "未提供"),
        ("文件编号/版本", f"{source.get('document_id') or '-'} / {source.get('revision') or '-'}"),
        ("普通最小间距", f"{routing.get('minimum_general_clearance_mm')} mm"),
        ("热区最小间距", f"{routing.get('minimum_hot_zone_clearance_mm')} mm"),
        ("最小弯曲半径", bend_value),
        ("本次实际DMU扫描间距", f"{data.get('source', {}).get('clearance_mm')} mm"),
        ("实体穿透判失败", "是" if dmu.get("clash_is_failure", True) else "否"),
        ("接触判失败", "是" if dmu.get("contact_is_failure", False) else "否"),
        ("接管/开孔轴线偏差容差", f"{opening.get('coaxial_tolerance_mm', '未配置')} mm"),
        ("接管/开孔夹角容差", f"{opening.get('angle_tolerance_deg', '未配置')} deg"),
        ("开孔径向间隙范围", f"{opening.get('radial_clearance_min_mm', '未配置')}–{opening.get('radial_clearance_max_mm', '未配置')} mm"),
        ("接管轴向贯穿容差", f"{opening.get('axial_tolerance_mm', '未配置')} mm"),
        ("允许接触对", json.dumps(rules.get("exemptions", {}).get("allowed_contact_pairs", []), ensure_ascii=False)),
        ("适用范围", str(rules.get("scope") or "未提供")),
    )
    table = doc.add_table(rows=len(rows), cols=2); table.style = "Table Grid"
    for row, (label, value) in zip(table.rows, rows):
        _set_cell_text(row.cells[0], label, bold=True, color=COLORS["navy"], size=8.5)
        _set_cell_shading(row.cells[0], COLORS["light_blue"])
        _set_cell_text(row.cells[1], value, size=8.5)
    _set_table_geometry(table, (2600, 6500))
    if not rules:
        doc.add_paragraph("结构化结果未包含规则快照，正式符合性结论不得仅依据本报告文字。")


def _add_summary(doc: Document, data: dict[str, Any]) -> None:
    doc.add_heading("2. 执行摘要", level=1)
    counts = data.get("counts", {})
    overall, overall_key = _overall_status(data)
    p = doc.add_paragraph()
    _font(p.add_run("总体结论："), size=10, bold=True, color=COLORS["navy"])
    _font(p.add_run(overall), size=10, bold=True, color=COLORS[overall_key.lower()])
    p.add_run("。本结论仅覆盖本次报告明确列出的检查范围。")

    table = doc.add_table(rows=2, cols=6)
    table.style = "Table Grid"
    for index, status in enumerate(("FAIL", "WARN", "PASS", "NOT_EVALUATED", "EXEMPTED", "ERROR")):
        _set_cell_text(table.rows[0].cells[index], STATUS_LABEL[status], bold=True,
                       color=COLORS["white"], size=8, align=WD_ALIGN_PARAGRAPH.CENTER)
        _set_cell_shading(table.rows[0].cells[index], COLORS[status.lower()])
        _set_cell_text(table.rows[1].cells[index], counts.get(status, 0), bold=True, size=13,
                       color=COLORS[status.lower()], align=WD_ALIGN_PARAGRAPH.CENTER)
    _set_table_geometry(table, (1517, 1517, 1517, 1517, 1516, 1516))

    source = data.get("source", {})
    doc.add_heading("3. 检查范围与方法", level=1)
    actual_release = str(source.get("catia_release") or data.get("catia_release") or "未知")
    environment_role = {
        "32": "外网开发验证环境 CATIA P3 V5-6R2022",
        "30": "内网目标环境 CATIA V5 R30",
    }.get(actual_release, "其他CATIA V5通用兼容环境")
    scope = [
        ("检查文档", data.get("document")),
        ("实际CATIA Release", actual_release),
        ("环境角色", environment_role),
        ("根产品", source.get("root_product")),
        ("顶层组件", source.get("top_level_component_count")),
        ("扫描组件", source.get("scope_component_count")),
        ("扫描间距", f"{source.get('clearance_mm')} mm"),
        ("原始冲突", source.get("raw_conflict_count")),
        ("返回冲突", source.get("returned_conflict_count")),
        ("结果截断", "是" if source.get("truncated") else "否"),
        ("临时产品", "是" if source.get("temporary_product_used") else "否"),
        ("清理确认", "是" if source.get("cleanup_verified") else "否"),
        ("工具保存源模型", "是" if source.get("source_saved_by_tool") else "否"),
    ]
    table = doc.add_table(rows=(len(scope) + 1) // 2, cols=4)
    table.style = "Table Grid"
    for index, (label, value) in enumerate(scope):
        row, side = divmod(index, 2)
        base = side * 2
        _set_cell_text(table.rows[row].cells[base], label, bold=True, color=COLORS["navy"], size=8)
        _set_cell_shading(table.rows[row].cells[base], COLORS["light_blue"])
        _set_cell_text(table.rows[row].cells[base + 1], value, size=8)
    _set_table_geometry(table, (1600, 2950, 1600, 2950))

    resume = data.get("resume_status") or {}
    if resume:
        doc.add_heading("3.1 大型单Part续检状态", level=2)
        large = data.get("large_single_part_analysis") or {}
        batch_plan = large.get("batch_plan") or {}
        broad_phase = batch_plan.get("broad_phase") or {}
        traceability = large.get("body_traceability") or {}
        shape_count = batch_plan.get("shape_count")
        total_possible_pairs = broad_phase.get("total_possible_pairs")
        candidate_pair_count = broad_phase.get("candidate_pair_count", resume.get("total_candidate_pairs"))
        if shape_count is not None:
            p = doc.add_paragraph()
            _font(p.add_run("筛选概况："), size=9, bold=True, color=COLORS["navy"])
            p.add_run(
                f"识别 {shape_count} 个 Body，理论组合 {total_possible_pairs} 对；"
                f"AABB Sweep and Prune 保留 {candidate_pair_count} 对候选后进行 OCCT 精确 B-Rep 计算。"
                f"本次未使用网格作几何裁决。Body 映射"
                f"{'完整' if traceability.get('is_complete') else '不完整'}"
                f"（{traceability.get('mapped_solid_count', 0)}/{shape_count}）。"
            )
        rows = (
            ("候选总数", resume.get("total_candidate_pairs"), "已完成", resume.get("completed_pairs")),
            ("本次新完成", resume.get("newly_completed_pairs"), "断点复用", resume.get("resumed_pairs")),
            ("超时", resume.get("timeout_pairs"), "预算顺延", resume.get("deferred_by_budget_pairs", 0)),
            ("其他失败", resume.get("failed_pairs"), "仍待处理", resume.get("pending_pairs")),
            ("完成率", f"{resume.get('completion_percent', 0):.2f}%", "是否需要续跑", "是" if resume.get("needs_resume") else "否"),
            ("完整性结论", "未完成，不得判整机通过" if resume.get("needs_resume") else "候选计算完整", "断点状态", "可继续" if resume.get("needs_resume") else "已完成"),
        )
        status_table=doc.add_table(rows=len(rows),cols=4); status_table.style="Table Grid"
        for row,values in zip(status_table.rows,rows):
            for index,value in enumerate(values):
                label=index%2==0; _set_cell_text(row.cells[index],value,bold=label,color=COLORS["navy"] if label else None,size=8)
                if label: _set_cell_shading(row.cells[index],COLORS["light_blue"])
            _cant_split(row)
        _set_table_geometry(status_table,(1600,2950,1600,2950))

    semantic_rows = []
    for label, key in (("Face/Surface语义事件", "semantic_intersection_events"),
                       ("实体交互语义判定", "solid_interaction_assessments"),
                       ("接管—开孔接口判定", "opening_interface_analysis")):
        block = data.get(key) or {}
        if block:
            counts_text = " / ".join(
                f"{status}={int((block.get('disposition_counts') or {}).get(status, 0))}"
                for status in ("FAIL", "REVIEW", "PASS"))
            total = block.get("event_count", block.get("assessment_count",
                              (block.get("network") or {}).get("result_count", 0)))
            semantic_rows.append((label, f"{total} 项；{counts_text}"))
            if key == "opening_interface_analysis" and block.get("rule_approval"):
                approval = block["rule_approval"]
                semantic_rows.append(("开孔接口规则审批",
                                      ("已批准，可正式裁决" if approval.get("formal_adjudication_allowed")
                                       else "待批准，仅输出几何预判和复核警告")))
    if semantic_rows:
        doc.add_heading("3.2 精确几何语义结论", level=2)
        table = doc.add_table(rows=len(semantic_rows), cols=2)
        table.style = "Table Grid"
        for row, (label, value) in zip(table.rows, semantic_rows):
            _set_cell_text(row.cells[0], label, bold=True, color=COLORS["navy"], size=8)
            _set_cell_shading(row.cells[0], COLORS["light_blue"])
            _set_cell_text(row.cells[1], value, size=8)
        _set_table_geometry(table, (2600, 6500))

    auto_opening = data.get("opening_interface_auto_discovery") or {}
    if auto_opening and not auto_opening.get("analysis_executed"):
        coverage = auto_opening.get("coverage") or {}
        reasons = "；".join(str(value) for value in coverage.get("reason_labels") or [])
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(5)
        _font(p.add_run("接管—开孔覆盖门禁："), size=9, bold=True,
              color=COLORS["not_evaluated"])
        p.add_run(f"未执行，原因：{reasons or '自动发现证据不足'}。该项不得计为通过。")


def _compact_counts(values: dict[str, Any] | None) -> str:
    values = values or {}
    ordered = ("FAIL", "ERROR", "REVIEW", "WARN", "NOT_EVALUATED", "PASS", "EXEMPTED")
    parts = [f"{key}={values[key]}" for key in ordered if key in values]
    return " / ".join(parts) if parts else "无状态统计"


def _module_detail(key: str, block: dict[str, Any]) -> tuple[str, str]:
    """Return execution state and compact human-readable coverage detail."""
    if not block:
        return "未提供", "本次结果没有该模块输出，不得视为已检查"
    if key == "model_precheck":
        issues = block.get("issues") or []
        state = "需复核" if issues or block.get("model_reliability") == "LOW" else "已执行"
        detail = (f"实体 {block.get('entity_count', 0)}；纳入 {block.get('included_entity_count', 0)}；"
                  f"健康分 {block.get('model_health_score', '-')}；可靠性 {block.get('model_reliability', '-')}；"
                  f"问题 {len(issues)}")
        return state, detail
    if key == "large_single_part_analysis":
        plan = block.get("batch_plan") or {}
        broad = plan.get("broad_phase") or {}
        trace = block.get("body_traceability") or {}
        return "已执行", (f"Body {plan.get('shape_count', '-')}；候选对 {broad.get('candidate_pair_count', '-')}；"
                           f"Solid 追溯 {trace.get('mapped_solid_count', '-')}/{plan.get('shape_count', '-')}")
    if key == "logical_components":
        return "已执行", (f"面 {block.get('face_count', 0)}；逻辑组件 {block.get('component_count', 0)}；"
                           f"已定型候选 {block.get('typed_candidate_count', 0)}；"
                           f"未解析接触 {block.get('unresolved_contact_count', 0)}")
    if key == "pipe_logical_components":
        return "已执行", (f"管路候选 {block.get('pipe_candidate_count', 0)}；"
                           f"接受连接 {block.get('joined_edge_count', 0)}；"
                           f"拒绝连接 {block.get('rejected_connection_count', 0)}")
    if key == "engineering_roles":
        return "已执行", (f"候选 {block.get('candidate_count', 0)}；角色统计 "
                           f"{json.dumps(block.get('role_counts') or {}, ensure_ascii=False)}")
    if key in {"semantic_intersection_events", "solid_interaction_assessments",
               "opening_interface_analysis"}:
        total = block.get("event_count", block.get("assessment_count",
                          (block.get("network") or {}).get("result_count", 0)))
        counts = block.get("disposition_counts") or {}
        state = "需复核" if counts.get("REVIEW") else "发现问题" if counts.get("FAIL") else "已执行"
        return state, f"记录 {total}；{_compact_counts(counts)}"
    if key == "opening_interface_auto_discovery":
        return ("已执行" if block.get("analysis_executed") else "未评价",
                "分析已执行" if block.get("analysis_executed") else
                "；".join(str(x) for x in (block.get("coverage") or {}).get("reason_labels") or [])
                or "自动发现证据不足")
    if key == "pipe_candidate_review":
        return "已执行", (f"候选 {len(block.get('candidates') or [])}；"
                           f"排除直圆柱 {block.get('excluded_straight_cylinder_count', 0)}")
    return "已提供", f"schema={block.get('schema_version', '未声明')}"


def _add_module_coverage(doc: Document, data: dict[str, Any]) -> None:
    doc.add_heading("4. 检查模块覆盖", level=1)
    p = doc.add_paragraph(
        "本节逐项披露检查模块是否产生结构化输出。未提供表示本次运行没有该模块证据，"
        "不能因为问题总数为零而判定该模块通过。"
    )
    _font(p.runs[0], size=9, color=COLORS["ink"])
    table = doc.add_table(rows=1, cols=3)
    table.style = "Table Grid"
    for cell, label in zip(table.rows[0].cells, ("检查模块", "执行状态", "覆盖与结果")):
        _set_cell_text(cell, label, bold=True, color=COLORS["white"], size=8,
                       align=WD_ALIGN_PARAGRAPH.CENTER)
        _set_cell_shading(cell, COLORS["navy"])
    _repeat_header(table.rows[0])
    for index, (key, label) in enumerate(MODULES):
        state, detail = _module_detail(key, data.get(key) or {})
        row = table.add_row()
        _set_cell_text(row.cells[0], label, bold=True, color=COLORS["navy"], size=8)
        _set_cell_text(row.cells[1], state, bold=True, size=8,
                       color=(COLORS["pass"] if state == "已执行" else
                              COLORS["fail"] if state == "发现问题" else
                              COLORS["warn"] if state == "需复核" else COLORS["not_evaluated"]))
        _set_cell_text(row.cells[2], detail, size=8)
        if index % 2:
            for cell in row.cells:
                _set_cell_shading(cell, COLORS["light"])
        _cant_split(row)
    _set_table_geometry(table, (2550, 1350, 5200))


def _add_model_quality(doc: Document, data: dict[str, Any]) -> None:
    doc.add_heading("5. 模型几何质量与转换可靠性", level=1)
    precheck = data.get("model_precheck") or {}
    if not precheck:
        doc.add_paragraph("本次结果未提供模型几何预检数据，壳体闭合性、零体积几何和转换可靠性均未评价。")
        return
    rows = (
        ("源格式", precheck.get("source_format"), "模型可靠性", precheck.get("model_reliability")),
        ("模型健康分", precheck.get("model_health_score"), "实体总数", precheck.get("entity_count")),
        ("纳入检查实体", precheck.get("included_entity_count"), "表面参与检查", "是" if precheck.get("surface_geometry_participates") else "否"),
        ("几何类型", json.dumps(precheck.get("geometry_type_counts") or {}, ensure_ascii=False),
         "转换信号", len(precheck.get("conversion_signals") or [])),
    )
    table = doc.add_table(rows=len(rows), cols=4); table.style = "Table Grid"
    for row, values in zip(table.rows, rows):
        for index, value in enumerate(values):
            label = index % 2 == 0
            _set_cell_text(row.cells[index], value, bold=label,
                           color=COLORS["navy"] if label else None, size=8)
            if label:
                _set_cell_shading(row.cells[index], COLORS["light_blue"])
        _cant_split(row)
    _set_table_geometry(table, (1700, 2850, 1700, 2850))

    issues = precheck.get("issues") or []
    doc.add_heading("5.1 几何健康问题", level=2)
    if not issues:
        doc.add_paragraph("未发现需要复核的几何健康问题。")
    else:
        issue_table = doc.add_table(rows=1, cols=3); issue_table.style = "Table Grid"
        for cell, label in zip(issue_table.rows[0].cells, ("对象", "问题代码", "等级")):
            _set_cell_text(cell, label, bold=True, color=COLORS["white"], size=8,
                           align=WD_ALIGN_PARAGRAPH.CENTER); _set_cell_shading(cell, COLORS["navy"])
        _repeat_header(issue_table.rows[0])
        for item in issues:
            row = issue_table.add_row()
            for cell, value in zip(row.cells, (item.get("object_id"), item.get("code"), item.get("severity"))):
                _set_cell_text(cell, value, size=8)
            _cant_split(row)
        _set_table_geometry(issue_table, (3200, 3900, 2000))

    signals = precheck.get("conversion_signals") or []
    doc.add_heading("5.2 转换可靠性信号", level=2)
    if not signals:
        doc.add_paragraph("未记录 STEP IGES 或 BREP 转换异常信号。")
    else:
        signal_table = doc.add_table(rows=1, cols=4); signal_table.style = "Table Grid"
        for cell, label in zip(signal_table.rows[0].cells, ("对象", "转换问题", "置信度", "依据")):
            _set_cell_text(cell, label, bold=True, color=COLORS["white"], size=8,
                           align=WD_ALIGN_PARAGRAPH.CENTER); _set_cell_shading(cell, COLORS["navy"])
        _repeat_header(signal_table.rows[0])
        for item in signals:
            row = signal_table.add_row()
            values = (item.get("source_id"), item.get("conversion_issue") or "无",
                      item.get("confidence"), "；".join(str(x) for x in item.get("reasons") or []))
            for cell, value in zip(row.cells, values):
                _set_cell_text(cell, value, size=7.5)
            _cant_split(row)
        _set_table_geometry(signal_table, (2100, 2200, 1300, 3500))


def _add_semantic_reconstruction(doc: Document, data: dict[str, Any]) -> None:
    doc.add_heading("6. 工程对象与连接关系识别", level=1)
    logical = data.get("logical_components") or {}
    pipes = data.get("pipe_logical_components") or {}
    roles = data.get("engineering_roles") or {}
    rows = (
        ("逻辑组件", logical.get("component_count"), "已定型候选", logical.get("typed_candidate_count")),
        ("未解析接触", logical.get("unresolved_contact_count"), "管路候选", pipes.get("pipe_candidate_count")),
        ("接受连接", pipes.get("joined_edge_count"), "拒绝连接", pipes.get("rejected_connection_count")),
        ("工程角色候选", roles.get("candidate_count"), "角色统计", json.dumps(roles.get("role_counts") or {}, ensure_ascii=False)),
    )
    table = doc.add_table(rows=len(rows), cols=4); table.style = "Table Grid"
    for row, values in zip(table.rows, rows):
        for index, value in enumerate(values):
            label = index % 2 == 0
            _set_cell_text(row.cells[index], value if value is not None else "未提供", bold=label,
                           color=COLORS["navy"] if label else None, size=8)
            if label:
                _set_cell_shading(row.cells[index], COLORS["light_blue"])
        _cant_split(row)
    _set_table_geometry(table, (1700, 2850, 1700, 2850))

    components = logical.get("components") or []
    if components:
        doc.add_heading("6.1 逻辑组件明细", level=2)
        detail = doc.add_table(rows=1, cols=5); detail.style = "Table Grid"
        for cell, label in zip(detail.rows[0].cells, ("组件 ID", "工程对象类型", "状态", "置信度", "面数量")):
            _set_cell_text(cell, label, bold=True, color=COLORS["white"], size=7.5,
                           align=WD_ALIGN_PARAGRAPH.CENTER); _set_cell_shading(cell, COLORS["navy"])
        _repeat_header(detail.rows[0])
        for item in components[:100]:
            hypothesis = item.get("engineering_hypothesis") or item
            object_type = hypothesis.get("engineering_object_type")
            values = (item.get("logical_component_id"), ENGINEERING_TYPE_LABEL.get(object_type, object_type),
                      item.get("semantic_status"), hypothesis.get("confidence"), item.get("face_count"))
            row = detail.add_row()
            for cell, value in zip(row.cells, values):
                _set_cell_text(cell, value, size=7.2)
            _cant_split(row)
        _set_table_geometry(detail, (2200, 2700, 1400, 1300, 1500))
        if len(components) > 100:
            doc.add_paragraph(f"逻辑组件共 {len(components)} 项；正文展示前 100 项，完整数据保留在结构化 JSON 中。")

    candidates = roles.get("candidates") or []
    if candidates:
        doc.add_heading("6.2 工程角色候选", level=2)
        role_table = doc.add_table(rows=1, cols=5); role_table.style = "Table Grid"
        for cell, label in zip(role_table.rows[0].cells, ("组件 ID", "工程角色", "状态", "置信度", "判定依据")):
            _set_cell_text(cell, label, bold=True, color=COLORS["white"], size=7.5,
                           align=WD_ALIGN_PARAGRAPH.CENTER); _set_cell_shading(cell, COLORS["navy"])
        _repeat_header(role_table.rows[0])
        for item in candidates[:100]:
            values = (item.get("logical_component_id"), item.get("engineering_role"), item.get("status"),
                      item.get("confidence"), "；".join(str(x) for x in item.get("basis") or []))
            row = role_table.add_row()
            for cell, value in zip(row.cells, values):
                _set_cell_text(cell, value, size=7.2)
            _cant_split(row)
        _set_table_geometry(role_table, (2100, 1900, 1200, 1200, 2700))


def _measurement(finding: dict[str, Any]) -> str:
    value = finding.get("measured_value")
    if value is None:
        return "-"
    return f"{value:g} {finding.get('unit') or ''}".strip()


def _opening_interface_report_rows(finding: dict[str, Any]) -> list[tuple[str, str]]:
    detail = (finding.get("metadata") or {}).get("opening_interface") or {}
    if not detail:
        return []
    values = detail.get("measurements") or {}
    evidence = detail.get("evidence") or {}

    def number(key: str, unit: str = "mm") -> str:
        value = values.get(key)
        return "未取得" if value is None else f"{float(value):.3f} {unit}".rstrip()

    def yes_no(key: str) -> str:
        value = values.get(key)
        return "是" if value is True else "否" if value is False else "未取得"

    evidence_text = "；".join((
        f"精确B-Rep={'是' if evidence.get('exact_brep') else '否'}",
        f"完整孔边界={'是' if evidence.get('boundary_complete') else '否'}",
        f"筒壁不连续已确认={'是' if evidence.get('host_discontinuity_confirmed') else '否'}",
        "网格参与最终判定=否",
    ))
    return [
        ("接口对象", f"开孔={detail.get('opening_id', '-')}；接管={detail.get('nozzle_id', '-')}") ,
        ("轴线关系", f"中心偏差={number('axis_offset_mm')}；夹角={number('axis_angle_deg', 'deg')}") ,
        ("孔径关系", f"开孔半径={number('opening_radius_mm')}；接管外半径={number('nozzle_outer_radius_mm')}；径向间隙={number('radial_clearance_mm')}") ,
        ("筒壁贯通", f"局部壁厚={number('host_wall_thickness_mm')}；穿过开孔平面={yes_no('crosses_opening_plane')}；跨越完整筒壁={yes_no('spans_host_wall')}") ,
        ("判定证据", evidence_text),
        ("原因", "；".join(str(item) for item in detail.get("reason_labels") or []) or "无异常"),
    ]


def _reportable_findings(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Hide confirmed normal connections from problem-oriented report sections."""
    return [item for item in data.get("findings", [])
            if ((item.get("metadata") or {}).get("relationship_assessment") or {}).get("decision")
            != "PASS_NORMAL_CONNECTION"]


def _add_findings_table(doc: Document, data: dict[str, Any]) -> None:
    doc.add_heading("7. 问题总览", level=1)
    findings = sorted(_reportable_findings(data),
                      key=lambda item: (STATUS_ORDER.index(item.get("status", "ERROR")),
                                        item.get("issue_id", "")))
    table = doc.add_table(rows=1, cols=7)
    table.style = "Table Grid"
    headers = ("Issue ID", "状态", "等级", "规则", "对象 A / B", "实测", "问题")
    for cell, label in zip(table.rows[0].cells, headers):
        _set_cell_text(cell, label, bold=True, color=COLORS["white"], size=7.5,
                       align=WD_ALIGN_PARAGRAPH.CENTER)
        _set_cell_shading(cell, COLORS["navy"])
    _repeat_header(table.rows[0])
    for item in findings:
        row = table.add_row()
        status = item.get("status", "ERROR")
        values = (
            item.get("issue_id"), STATUS_LABEL.get(status, status), item.get("severity"),
            item.get("rule_id"), f"{_display(item.get('object_a'))}\n{_display(item.get('object_b'))}",
            _measurement(item), item.get("title"),
        )
        for index, (cell, value) in enumerate(zip(row.cells, values)):
            _set_cell_text(cell, value, size=7.2,
                           bold=index == 1, color=COLORS.get(status.lower(), COLORS["ink"]) if index == 1 else None)
        _set_cell_shading(row.cells[1], "FFF4ED" if status == "WARN" else
                          "FEF3F2" if status in ("FAIL", "ERROR") else COLORS["light"])
        _cant_split(row)
    _set_table_geometry(table, (1500, 650, 550, 1150, 2350, 900, 2000))


def _add_baseline(doc: Document, comparison: dict[str, Any] | None) -> None:
    doc.add_heading("8. 基线变化", level=1)
    if not comparison:
        doc.add_paragraph("本次结果未提供基线比较。建议在模型评审批准后保存归一化基线。")
        return
    summary = comparison.get("summary", {})
    labels = (("新增", "added"), ("已解决", "resolved"), ("持续", "persistent"),
              ("变化", "changed"), ("回归", "regressions"), ("改善", "improvements"))
    table = doc.add_table(rows=2, cols=6)
    table.style = "Table Grid"
    for index, (label, key) in enumerate(labels):
        _set_cell_text(table.rows[0].cells[index], label, bold=True, color=COLORS["white"],
                       size=8, align=WD_ALIGN_PARAGRAPH.CENTER)
        _set_cell_shading(table.rows[0].cells[index], COLORS["navy"])
        _set_cell_text(table.rows[1].cells[index], summary.get(key, 0), bold=True, size=12,
                       align=WD_ALIGN_PARAGRAPH.CENTER)
    _set_table_geometry(table, (1517, 1517, 1517, 1517, 1516, 1516))


def _add_confidence(doc: Document, data: dict[str, Any]) -> None:
    doc.add_heading("9. 检查边界与可信度", level=1)
    budget = data.get("confidence_budget", {})
    groups = (("已检查", budget.get("checked", []), COLORS["pass"]),
              ("未检查", budget.get("not_checked", []), COLORS["not_evaluated"]),
              ("假设", budget.get("assumptions", []), COLORS["warn"]),
              ("降级项", budget.get("degraded", []), COLORS["error"]))
    for label, values, color in groups:
        paragraph = doc.add_paragraph()
        paragraph.paragraph_format.space_after = Pt(3)
        _font(paragraph.add_run(f"{label}："), size=9, bold=True, color=color)
        paragraph.add_run("；".join(str(value) for value in values) if values else "无")


def _add_detail_pages(doc: Document, data: dict[str, Any], evidence_images: list[Path] | None = None) -> None:
    findings = sorted(_reportable_findings(data),
                      key=lambda item: (STATUS_ORDER.index(item.get("status", "ERROR")),
                                        item.get("issue_id", "")))
    if not findings:
        return
    doc.add_page_break()
    doc.add_heading("10. 问题明细", level=1)
    for index, item in enumerate(findings, 1):
        status = item.get("status", "ERROR")
        heading = doc.add_heading(f"10.{index}  {item.get('issue_id')} · {item.get('title')}", level=2)
        heading.runs[0].font.color.rgb = RGBColor.from_string(COLORS.get(status.lower(), COLORS["error"]))
        table = doc.add_table(rows=4, cols=4)
        table.style = "Table Grid"
        pairs = (
            ("状态", STATUS_LABEL.get(status, status), "严重度", item.get("severity")),
            ("规则", item.get("rule_id"), "实测/限值", f"{_measurement(item)} / {_display(item.get('limit_value'))} {item.get('unit') or ''}".strip()),
            ("对象 A", item.get("object_a"), "对象 B", item.get("object_b")),
            ("标准/依据", item.get("standard_reference") or "当前规则集", "证据数量", len(item.get("evidence", []))),
        )
        for row, values in zip(table.rows, pairs):
            for cell_index, value in enumerate(values):
                is_label = cell_index % 2 == 0
                _set_cell_text(row.cells[cell_index], value, bold=is_label,
                               color=COLORS["navy"] if is_label else None, size=8)
                if is_label:
                    _set_cell_shading(row.cells[cell_index], COLORS["light_blue"])
            _cant_split(row)
        _set_table_geometry(table, (1400, 3150, 1400, 3150))
        for label, value in (("判定说明", item.get("message")),
                             ("整改建议", item.get("recommendation"))):
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(4)
            p.paragraph_format.space_after = Pt(3)
            p.paragraph_format.keep_together = True
            _font(p.add_run(f"{label}："), size=9, bold=True, color=COLORS["navy"])
            p.add_run(str(value or "未提供"))
        relationship = (item.get("metadata") or {}).get("relationship_assessment") or {}
        if relationship:
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(4)
            p.paragraph_format.space_after = Pt(3)
            p.paragraph_format.keep_together = True
            _font(p.add_run("组件关系判断："), size=9, bold=True, color=COLORS["navy"])
            evidence = "；".join(str(value) for value in relationship.get("key_evidence", [])) or "未提供"
            p.add_run(
                f"{relationship.get('decision', 'UNKNOWN')}；"
                f"置信度={relationship.get('confidence', '未知')}；"
                f"理由={relationship.get('reason', '未提供')}；关键证据={evidence}"
            )
        opening_rows = _opening_interface_report_rows(item)
        if opening_rows:
            doc.add_heading("接口精确几何证据", level=3)
            detail_table = doc.add_table(rows=len(opening_rows), cols=2)
            detail_table.style = "Table Grid"
            for row, (label, value) in zip(detail_table.rows, opening_rows):
                _set_cell_text(row.cells[0], label, bold=True, color=COLORS["navy"], size=8)
                _set_cell_shading(row.cells[0], COLORS["light_blue"])
                _set_cell_text(row.cells[1], value, size=8)
                _cant_split(row)
            _set_table_geometry(detail_table, (1900, 7200))
        for evidence in item.get("evidence", []):
            path = evidence.get("path")
            if path and Path(path).exists():
                doc.add_picture(path, width=Cm(15.5))
                caption = doc.add_paragraph(f"证据：{evidence.get('description') or evidence.get('kind')}")
                caption.alignment = WD_ALIGN_PARAGRAPH.CENTER
                for run in caption.runs:
                    _font(run, size=8, color=COLORS["muted"])
        if index == 1:
            for image_path in evidence_images or []:
                if not image_path.exists():
                    continue
                picture = doc.add_paragraph()
                picture.alignment = WD_ALIGN_PARAGRAPH.CENTER
                picture.paragraph_format.space_before = Pt(6)
                picture.add_run().add_picture(str(image_path), width=Cm(13.5))
                caption = doc.add_paragraph("CATIA 定位证据：Body #4 与 Body #5 已在模型树和三维窗口中高亮")
                caption.alignment = WD_ALIGN_PARAGRAPH.CENTER
                caption.paragraph_format.keep_with_next = False
                for run in caption.runs:
                    _font(run, size=8, color=COLORS["muted"])
        if index != len(findings):
            divider = doc.add_paragraph()
            divider.paragraph_format.space_after = Pt(2)


def _add_pipe_candidate_review(doc: Document, data: dict[str, Any]) -> None:
    review = data.get("pipe_candidate_review") or {}
    candidates = review.get("candidates") or []
    if not candidates and not review.get("excluded_straight_cylinder_count"):
        return
    doc.add_page_break()
    doc.add_heading("11. 管路候选复核", level=1)
    p = doc.add_paragraph(
        "候选由确定性几何特征筛选。弯曲、细长和近似恒定截面只构成管路候选证据；"
        "缺少原生管路语义、空腔或中心线证据时，弯曲半径结论保持 NOT_EVALUATED。"
    )
    _font(p.runs[0], size=9, color=COLORS["ink"])
    table = doc.add_table(rows=1, cols=7)
    table.style = "Table Grid"
    for cell, label in zip(table.rows[0].cells,
                           ("对象", "名称", "证据等级", "外径/mm", "弯曲半径/mm", "R/D", "结论")):
        _set_cell_text(cell, label, bold=True, color=COLORS["white"], size=7)
        _set_cell_shading(cell, COLORS["navy"])
    for candidate in candidates:
        values = (
            candidate.get("body_index") if candidate.get("body_index") is not None else "—",
            candidate.get("name") or "—", candidate.get("evidence_tier") or "—",
            candidate.get("outer_diameter_mm") if candidate.get("outer_diameter_mm") is not None else "待重建",
            candidate.get("centerline_bend_radius_mm") if candidate.get("centerline_bend_radius_mm") is not None else "待重建",
            candidate.get("radius_ratio_r_over_d") if candidate.get("radius_ratio_r_over_d") is not None else "待重建",
            candidate.get("status", "NOT_EVALUATED"),
        )
        for cell, value in zip(table.add_row().cells, values):
            _set_cell_text(cell, f"{value:.6g}" if isinstance(value, float) else value, size=6.8)
    _set_table_geometry(table, (700, 1900, 1500, 1000, 1150, 850, 1400), indent_dxa=0)
    excluded = int(review.get("excluded_straight_cylinder_count") or 0)
    if excluded:
        p = doc.add_paragraph(f"已排除 {excluded} 个仅有直圆柱外观的对象，避免把螺栓、销或轴误判为管路。")
        _font(p.runs[0], size=8, color=COLORS["muted"])
    seen: set[Path] = set()
    for candidate in candidates:
        for key, caption in (("context_image", "整体定位图：周围对象透明显示。"),
                             ("detail_image", "隔离放大图：仅显示管路候选。")):
            value = candidate.get(key)
            if not value:
                continue
            path = Path(value)
            if path in seen or not path.exists():
                continue
            seen.add(path)
            picture = doc.add_paragraph()
            picture.alignment = WD_ALIGN_PARAGRAPH.CENTER
            picture.add_run().add_picture(str(path), width=Cm(17.4))
            cp = doc.add_paragraph(caption)
            cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
            _font(cp.runs[0], size=7, color=COLORS["muted"])


def _add_audit(doc: Document, data: dict[str, Any]) -> None:
    doc.add_heading("12. 审计与只读声明", level=1)
    source = data.get("source", {})
    audit = data.get("audit", {})
    rows = (
        ("运行 ID", data.get("run_id") or "未提供"),
        ("生成时间", data.get("generated_at") or "未提供"),
        ("几何事实来源", audit.get("geometry_authority") or "CATIA 原生计算"),
        ("AI 角色", audit.get("llm_role") or "仅解释结构化结果"),
        ("关系判断器", audit.get("relationship_judge") or "未启用"),
        ("源模型被工具修改", "是" if audit.get("source_model_modified") else "否"),
        ("源模型被工具保存", "是" if source.get("source_saved_by_tool") else "否"),
        ("扫描前 Saved 状态", _display(source.get("source_document_saved_before"))),
        ("扫描后 Saved 状态", _display(source.get("source_document_saved_after"))),
        ("临时对象清理确认", "是" if source.get("cleanup_verified") else "否"),
        ("结果截断", "是" if source.get("truncated") else "否"),
    )
    table = doc.add_table(rows=len(rows), cols=2)
    table.style = "Table Grid"
    for row, (label, value) in zip(table.rows, rows):
        _set_cell_text(row.cells[0], label, bold=True, color=COLORS["navy"], size=8)
        _set_cell_shading(row.cells[0], COLORS["light_blue"])
        _set_cell_text(row.cells[1], value, size=8)
    _set_table_geometry(table, (2500, 6600))
    exceptions = audit.get("exceptions") or []
    p = doc.add_paragraph()
    _font(p.add_run("异常与重试："), size=9, bold=True, color=COLORS["navy"])
    p.add_run("；".join(str(value) for value in exceptions) if exceptions else "无记录")


def build_report(input_json: Path, output_docx: Path, evidence_images: list[Path] | None = None) -> Path:
    data = json.loads(input_json.read_text(encoding="utf-8"))
    if data.get("schema_version") != "1.1.0":
        raise ValueError(f"Unsupported result schema_version: {data.get('schema_version')}")
    report_id = f"CATIA-{Path(str(data.get('document', 'UNKNOWN'))).stem}-{datetime.now():%Y%m%d}"
    doc = Document(REPORT_TEMPLATE) if REPORT_TEMPLATE.exists() else Document()
    if REPORT_TEMPLATE.exists():
        body = doc._element.body
        for child in list(body):
            if child.tag != qn("w:sectPr"):
                body.remove(child)
    _configure_document(doc, "CATIA V5 智能工程检查报告")
    _add_cover(doc, data, report_id)
    _add_rules(doc, data)
    _add_summary(doc, data)
    _add_module_coverage(doc, data)
    _add_model_quality(doc, data)
    _add_semantic_reconstruction(doc, data)
    _add_findings_table(doc, data)
    _add_baseline(doc, data.get("baseline_comparison"))
    _add_confidence(doc, data)
    _add_detail_pages(doc, data, evidence_images)
    _add_pipe_candidate_review(doc, data)
    _add_audit(doc, data)
    output_docx.parent.mkdir(parents=True, exist_ok=True)
    doc.save(output_docx)
    return output_docx


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_json", type=Path)
    parser.add_argument("--docx", type=Path, required=True)
    parser.add_argument("--evidence-image", type=Path, action="append", default=[])
    args = parser.parse_args()
    print(build_report(args.input_json, args.docx, args.evidence_image))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
