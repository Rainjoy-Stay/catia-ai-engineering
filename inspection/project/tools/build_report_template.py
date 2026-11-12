"""Build a complete, model-readable Word reference template for CATIA reports."""
from pathlib import Path
from docx import Document
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT.parent / "skills" / "catia-v5r18-checker" / "assets" / "CATIA检查报告模板.docx"
NAVY, INK, MUTED, LINE = "17365D", "263238", "607080", "D9D9D9"

def font(run, size=9.5, bold=False, color=INK):
    run.font.name = "Microsoft YaHei"
    run._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    run.font.size, run.bold = Pt(size), bold
    run.font.color.rgb = RGBColor.from_string(color)

def shade(cell, fill):
    node = OxmlElement("w:shd"); node.set(qn("w:fill"), fill)
    cell._tc.get_or_add_tcPr().append(node)

def borders(table):
    pr = table._tbl.tblPr
    root = pr.find(qn("w:tblBorders"))
    if root is None:
        root = OxmlElement("w:tblBorders"); pr.append(root)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        node = OxmlElement(f"w:{edge}"); node.set(qn("w:val"), "single")
        node.set(qn("w:sz"), "4"); node.set(qn("w:color"), LINE); root.append(node)

def cell_text(cell, value, *, bold=False, color=INK, center=False):
    cell.text = ""; cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
    p = cell.paragraphs[0]; p.alignment = WD_ALIGN_PARAGRAPH.CENTER if center else WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.space_before = p.paragraph_format.space_after = Pt(1.5)
    p.paragraph_format.line_spacing = 1.05; font(p.add_run(str(value)), 8.2, bold, color)

def add_table(doc, headers, rows, widths=None):
    table = doc.add_table(rows=1, cols=len(headers)); table.alignment = WD_TABLE_ALIGNMENT.LEFT
    trpr = table.rows[0]._tr.get_or_add_trPr(); tag = OxmlElement("w:tblHeader"); tag.set(qn("w:val"), "true"); trpr.append(tag)
    for cell, label in zip(table.rows[0].cells, headers):
        cell_text(cell, label, bold=True, color="FFFFFF", center=True); shade(cell, NAVY)
    for i, values in enumerate(rows):
        row = table.add_row(); row._tr.get_or_add_trPr().append(OxmlElement("w:cantSplit"))
        for j, (cell, value) in enumerate(zip(row.cells, values)): cell_text(cell, value, center=(j == 0 and len(headers) > 2))
        if i % 2:
            for cell in row.cells: shade(cell, "F7F9FB")
    if widths:
        for row in table.rows:
            for cell, width in zip(row.cells, widths): cell.width = Cm(width)
    borders(table); doc.add_paragraph().paragraph_format.space_after = Pt(1)

def note(doc, text):
    p = doc.add_paragraph(); p.paragraph_format.space_after = Pt(6); font(p.add_run(text), 8.5, color=MUTED)

def intro(doc, purpose, rule):
    p = doc.add_paragraph(); font(p.add_run("用途："), 9, True, NAVY); font(p.add_run(purpose), 9)
    p = doc.add_paragraph(); font(p.add_run("生成规则："), 9, True, NAVY); font(p.add_run(rule), 9)

def fields(doc, rows):
    add_table(doc, ("字段", "数据来源", "填写要求", "无数据时"), rows, (3.2, 4.0, 6.2, 3.0))

def module(doc, number, name, key, purpose, module_fields, output):
    doc.add_heading(f"4.{number} {name}", level=2)
    note(doc, f"结构化来源：{key}。{purpose}")
    add_table(doc, ("项目", "参考格式"), (
        ("执行状态", "已执行 / 部分执行 / 未执行 / 异常"),
        ("覆盖统计", "对象总数、已评价数、未评价数、失败数；覆盖率必须有分母"),
        ("核心结论", "一句可审计结论；缺失数据不得写成通过"),
        ("模块字段", module_fields),
        ("问题输出", output),
        ("未评价原因", "输入缺失、语义不足、许可受限、超时或算法不适用；无则填无"),
    ), (3.4, 13.0))
    add_table(doc, ("示例状态", "覆盖", "结论 / 原因"), (("部分执行", "已评价 128 / 总计 132", "4 个对象缺少可验证几何，保持 NOT_EVALUATED"),), (3.0, 4.0, 9.4))

def build():
    doc = Document(); sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21), Cm(29.7)
    sec.top_margin, sec.bottom_margin = Cm(1.8), Cm(1.7); sec.left_margin = sec.right_margin = Cm(1.8)
    sec.header_distance = sec.footer_distance = Cm(0.7)
    normal = doc.styles["Normal"]; normal.font.name = "Microsoft YaHei"; normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    normal.font.size = Pt(9.5); normal.font.color.rgb = RGBColor.from_string(INK); normal.paragraph_format.space_after = Pt(5); normal.paragraph_format.line_spacing = 1.12
    for name, size in (("Title", 23), ("Heading 1", 16), ("Heading 2", 12.5), ("Heading 3", 10.5)):
        s = doc.styles[name]; s.font.name = "Microsoft YaHei"; s._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
        s.font.size = Pt(size); s.font.bold = True; s.font.color.rgb = RGBColor.from_string("000000")
        s.paragraph_format.keep_with_next = True; s.paragraph_format.space_before = Pt(9); s.paragraph_format.space_after = Pt(5)
    h = sec.header.paragraphs[0]; h.text = "CATIA 模型几何质量检查系统"; font(h.runs[0], 8, color=MUTED)
    f = sec.footer.paragraphs[0]; f.alignment = WD_ALIGN_PARAGRAPH.RIGHT; font(f.add_run("完整报告参考模板"), 8, color=MUTED)

    for _ in range(4): doc.add_paragraph()
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER; font(p.add_run("CATIA V5 ENGINEERING INSPECTION"), 10, True, NAVY)
    p = doc.add_paragraph(style="Title"); p.alignment = WD_ALIGN_PARAGRAPH.CENTER; p.add_run("CATIA V5 智能工程检查报告模板")
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER; font(p.add_run("章节格式 字段契约 模块示例与缺失值规则"), 11, color=MUTED)
    doc.add_paragraph()
    add_table(doc, ("模板属性", "内容"), (
        ("适用对象", "CATProduct、单一 CATPart、STEP、IGES、BREP"),
        ("权威数据", "结构化检查 JSON；Word 只负责可读呈现"),
        ("使用者", "内网大模型 Agent、工程复核人员、审计人员"),
        ("强制原则", "模块缺失必须显示未提供或未评价，不得推断为通过"),
    ), (4.0, 12.5))

    doc.add_page_break(); doc.add_heading("模板使用说明", level=1)
    intro(doc, "让大模型按固定结构生成完整报告，而不是把本文件当作空白封面。", "保留章节顺序和字段语义；允许根据数据量自动扩页；没有结果的字段按缺失值规则输出。")
    add_table(doc, ("标记", "含义", "处理方式"), (
        ("必填", "每次报告都必须出现", "缺失时显示未提供并解释原因"),
        ("条件必填", "相关模块执行或存在问题时必须出现", "不适用时显示不适用"),
        ("可重复", "按对象、问题或事件逐条生成", "不得合并导致对象身份丢失"),
        ("审计字段", "用于追溯运行与证据", "保留原始 ID、方法、路径和版本"),
    ), (2.5, 5.0, 9.0))
    doc.add_heading("统一状态与缺失值", level=2)
    add_table(doc, ("状态", "使用条件"), (
        ("PASS", "批准规则覆盖声明范围，必需模块完成且无阻断项"), ("WARN", "风险提示、人工确认项或低置信度结论"),
        ("FAIL", "违反规则或确认存在不可接受问题"), ("NOT_EVALUATED", "缺少输入、语义、许可、计算结果或能力不适用"),
        ("ERROR", "检查链异常或结果不可用"), ("EXEMPTED", "依据明确豁免规则排除；不得并入 PASS"),
    ), (3.5, 13.0))
    note(doc, "空数组表示集合没有记录；字段不存在表示数据未提供。二者不能互换。数值必须带单位，对象必须保留稳定 ID 或完整实例路径。")

    doc.add_page_break(); doc.add_heading("1 本次检查规则", level=1)
    intro(doc, "冻结本次结论采用的标准、阈值和豁免。", "规则快照写入报告；审批状态不是已批准时，总体结论不得写正式通过。")
    fields(doc, (("ruleset_id 必填", "rules/source", "完整规则集 ID 和版本", "未提供"), ("approval_status 必填", "rules", "已批准/草案/待确认", "待确认"),
        ("standard_reference", "rules", "标准号、版本、条款", "未提供"), ("scope", "rules", "适用文档、对象和排除范围", "未声明"),
        ("units", "rules", "长度、角度和体积单位", "不得猜测"), ("thresholds", "rules", "净距、干涉、弯曲半径和接口阈值", "NOT_EVALUATED"),
        ("exemptions", "rules", "豁免对象、理由和批准依据", "无")))
    add_table(doc, ("规则项", "比较方式", "阈值", "单位", "来源 / 审批"), (("[规则名称]", "[小于/大于/区间/枚举]", "[数值]", "[mm/deg/mm³]", "[标准条款/状态]"),), (4,3.5,2.4,2.4,4.2))

    doc.add_heading("2 执行摘要", level=1); intro(doc, "一页内说明结果、风险和下一阶段门禁。", "先给总体结论，再给状态计数和最高优先级问题；未评价与异常必须影响结论。")
    add_table(doc, ("总体状态", "PASS", "WARN", "FAIL", "未评价", "异常"), (("[状态]", "[n]", "[n]", "[n]", "[n]", "[n]"),), (3,2.5,2.5,2.5,3,3))
    fields(doc, (("overall_status 必填", "counts + modules", "按门禁规则计算", "ERROR"), ("executive_conclusion 必填", "综合结果", "事实结论和行动建议", "说明无法形成结论"),
        ("top_risks", "findings", "最多五项，含 issue_id 和对象", "无已识别高风险"), ("next_gate", "综合结果", "可进入/有条件进入/不可进入", "待确认")))

    doc.add_page_break(); doc.add_heading("3 检查范围与方法", level=1); intro(doc, "说明检查了什么、怎样检查以及是否完成。", "输入事实与算法分开描述；续检、截断和引用缺失必须出现。")
    fields(doc, (("document", "source", "名称、类型、路径、保存状态", "未提供"), ("catia_release", "source", "实际Release；32=外网V5-6R2022开发环境，30=内网R30目标环境", "未知"),
        ("environment_role", "由catia_release映射", "外网开发验证 / 内网目标验收 / 其他通用兼容", "未确认"),
        ("component_scope", "manifest", "组件/Body/Solid/Route 数量", "未统计"), ("methods", "source/modules", "DMU、OCCT、BRep、语义推断", "未提供"),
        ("completion", "source", "完整/部分/截断/续检点", "未确认"), ("read_only", "audit", "修改、保存和临时对象清理", "未确认")))

    doc.add_page_break(); doc.add_heading("4 检查模块覆盖", level=1)
    intro(doc, "逐模块证明哪些能力实际执行并给出可审计摘要。", "以下十个模块必须逐项出现；没有输出时保留标题，写未执行或未评价及原因。")
    module(doc,1,"模型几何预检","model_precheck","判断模型是否具备后续可靠检查的几何基础。","文档可读性、Body/Solid/Shell 数量、零体积、开放壳体、无效拓扑、转换状态","几何健康问题，含对象、类型、严重度、证据和后续影响")
    module(doc,2,"大型单 Part 精确检查","large_single_part_analysis","对多 Body 或导入单 Part 候选对进行精确距离和公共体积判断。","总候选、已评估、未评估、批次、检查点、最小距离、公共体积","穿模、接触复核、超时或未解析 Solid；保留 Body/Solid 映射")
    module(doc,3,"逻辑组件恢复","logical_components","从碎片化 Solid 或 Body 恢复工程组件分组。","logical_component_id、成员、分组依据、置信度、边界框、体积","低置信度分组、未归属对象和冲突归属")
    module(doc,4,"逻辑管路组装","pipe_logical_components","把直管、弯头、接头和分支组织为连续管路对象。","pipe_id、成员、连通性、轴线、外径、壁厚、端点、分支关系","断链、尺寸不一致、无法识别管件或不完整路径")
    module(doc,5,"工程角色识别","engineering_roles","给逻辑对象赋予管路、壳体、接管、法兰、支架等角色。","object_id、role、候选角色、置信度、几何和邻接证据","低置信度角色、角色冲突和未分类对象")
    module(doc,6,"表面交叉事件聚合","semantic_intersection_events","把底层面面交叉记录聚合为工程事件。","event_id、对象对、参与面、交线/交点数量、位置、聚合依据","重复事件、边界接触、疑似转换碎裂和待复核交叉")
    module(doc,7,"实体交互语义判定","solid_interaction_assessments","区分穿模、允许连接、接触、转换伪影和不确定交互。","assessment_id、对象对、disposition、公共体积、最小距离、语义证据、置信度","FAIL/WARN/REVIEW 条目；不得用网格替代最终 BRep 判定")
    module(doc,8,"接管与开孔接口判定","opening_interface_analysis","验证接管是否通过正确开孔并跨越完整筒壁。","开孔/接管 ID、中心偏差、轴线夹角、半径、径向间隙、壁厚、平面与筒壁跨越状态","完整孔边界、精确 BRep、筒壁不连续证据及原因码")
    module(doc,9,"开孔接口自动发现","opening_interface_auto_discovery","自动产生候选开孔和接管配对。","candidate_id、开孔、接管、距离、方向、尺寸匹配、候选分数、来源","接受、拒绝和待确认候选；保留排除原因")
    module(doc,10,"管路候选复核","pipe_candidate_review","呈现管路识别候选及弯曲半径、连续性和排除结论。","candidate_id、对象、证据、外径、弯曲半径、R/D、连续性、review_status","确认、排除、待复核对象和缺失尺寸")

    doc.add_page_break(); doc.add_heading("5 模型几何质量与转换可靠性", level=1)
    intro(doc, "说明几何健康和格式转换是否削弱结论。", "把几何事实、转换信号与影响分栏；低可靠性必须进入总体状态。")
    add_table(doc,("对象","几何信号","状态","对结论的影响","建议"),(("[对象 ID/路径]","[开放壳体/零体积/重复面/碎裂]","[状态]","[受影响模块]","[修复或复核]"),),(3.5,3.6,2.3,4.2,3))
    add_table(doc,("转换阶段","可靠性信号","证据","结论"),(("[STEP/IGES/BREP 导入]","[实体数/面数/容差异常]","[计数、日志或哈希]","[可靠/降级/不可用]"),),(3.5,4.5,4.8,3.8))

    doc.add_heading("6 工程对象与连接关系识别", level=1)
    intro(doc, "展示系统识别出的工程对象、角色和连接依据。", "使用稳定 ID；推断必须带置信度和证据，不得写成原生 CATIA 事实。")
    add_table(doc,("逻辑对象 ID","工程角色","成员对象","连接对象","置信度 / 依据"),(("[LC-001]","[管路/壳体/接管]","[Body/Solid 列表]","[对象 ID]","[0–1；几何、拓扑、命名]"),),(3,3.2,4,3,3.8))
    add_table(doc,("关系 ID","对象 A","对象 B","关系类型","证据与状态"),(("[REL-001]","[对象 ID]","[对象 ID]","[连接/穿透/接触/相邻]","[BRep/距离/语义；状态]"),),(2.6,3,3,3.8,4.6))

    doc.add_heading("7 问题总览", level=1); intro(doc, "提供可排序、可追踪的问题索引。", "一行一个 finding；总览与明细的 ID、状态、对象和数值必须一致。")
    add_table(doc,("问题 ID","状态 / 严重度","对象","问题","实测 / 阈值","建议"),(("[ISSUE-001]","[FAIL/HIGH]","[对象 A ↔ B]","[简短标题]","[值/阈值/单位]","[可执行动作]"),),(2.6,2.8,3.2,3.6,2.7,2.6))
    doc.add_heading("8 基线变化", level=1); intro(doc, "说明相对批准基线的变化。", "无批准基线时写未比较，不得自动建立基线。")
    add_table(doc,("变化类型","问题 ID","前值","本次值","说明"),(("[新增/持续/已解决/恶化/改善]","[ID]","[值/状态]","[值/状态]","[原因或影响]"),),(4,2.8,2.8,2.8,4))

    doc.add_page_break(); doc.add_heading("9 检查边界与可信度", level=1)
    intro(doc, "防止局部结果被误解为完整模型结论。", "列出已检查、未检查、假设、限制和降级；覆盖率必须有分母。")
    add_table(doc,("类别","范围 / 对象","数量或比例","原因","对结论的影响"),(("已检查","[范围]","[n/N 或 %]","[方法]","[可支持结论]"),("未检查","[范围]","[n/N 或 %]","[原因]","[不能支持结论]"),("假设","[内容]","—","[依据]","[不成立的影响]"),("降级","[模块]","[范围]","[许可/格式/能力]","[状态门禁]")),(2.5,3.8,2.7,3.8,3.8))

    doc.add_heading("10 问题明细", level=1); intro(doc, "逐问题给出事实、规则、解释、证据和建议。", "以下块按 finding 重复；截图只负责定位，几何结论以结构化测量为准。")
    add_table(doc,("字段","参考内容"),(("问题身份","issue_id、标题、状态、严重度、所属模块"),("对象","object_a/object_b、实例路径、Body/Solid/Face ID"),("测量","实测值、阈值、单位、方法、容差"),("规则依据","rule_id、标准条款、规则快照值"),("事实与解释","先写几何事实，再写工程语义；明确置信度"),("整改建议","动作、责任对象、复核条件"),("证据链","记录、对象路径、视图、原图和标注图")),(4,12.5))
    doc.add_heading("10.1 接管开孔专项字段", level=2)
    add_table(doc,("开孔 ID","接管 ID","中心偏差","轴线夹角","开孔半径","接管外半径","径向间隙"),(("[ID]","[ID]","[mm]","[deg]","[mm]","[mm]","[mm]"),),(2.4,2.4,2.4,2.4,2.4,2.4,2.4))
    add_table(doc,("局部壁厚","穿过开孔平面","跨越完整筒壁","精确 BRep","完整孔边界","筒壁不连续","原始原因码"),(("[mm]","[是/否/未评价]","[是/否/未评价]","[状态]","[状态]","[状态]","[code]"),),(2.4,2.8,2.8,2.3,2.3,2.3,2.5)); note(doc,"专项结论必须明确：网格参与最终判定＝否。原因码同时给出可读中文解释。")

    doc.add_heading("11 管路候选复核", level=1); intro(doc, "记录候选为何被确认、排除或待复核。", "候选并非最终工程事实；缺少直径或半径时写 NOT_EVALUATED。")
    add_table(doc,("候选 ID","对象 / 成员","外径","最小弯曲半径","R/D","状态","依据 / 排除原因"),(("[PIPE-CAND-001]","[对象 ID 列表]","[mm]","[mm]","[比值]","[确认/排除/待复核]","[几何与连通证据]"),),(2.7,3.5,2,2.7,1.8,2.8,3.3))

    doc.add_heading("12 审计与只读声明", level=1); intro(doc, "证明报告来自哪次运行并说明源模型是否保持不变。", "保留工具版本、时间、重试、错误和临时对象清理；记录前后状态。")
    fields(doc,(("run_id 必填","audit","唯一运行 ID 与时间","未提供"),("tool_versions","audit","检查器、MCP、CATIA、OCCT 版本","未知"),("source_state_before","audit","文档、保存状态、哈希或清单","未记录"),("source_state_after","audit","检查后状态及差异","未记录"),("temporary_objects","audit","创建数量、清理结果、残留项","未确认"),("errors_retries","audit","异常、重试次数、最终状态","无"),("llm_trace","audit","模型或模板模式、语义判断轨迹","模板模式")))
    add_table(doc,("只读核对项","结果","证据"),(("源模型未保存","[是/否/未确认]","[前后保存状态]"),("源模型未修改","[是/否/未确认]","[manifest/hash/变更记录]"),("临时对象已清理","[是/否/不适用]","[清理计数与异常]")),(5,3.5,8))

    doc.add_page_break(); doc.add_heading("机器生成前自检清单", level=1)
    add_table(doc,("检查项","通过条件"),(("十个模块完整出现","每个模块都有状态、覆盖、结论和未评价原因"),("十二章完整出现","章节顺序和字段含义一致"),("状态一致","摘要、总览、明细和模块统计一致"),("对象可追踪","稳定 ID、完整路径或可验证映射"),("数值可解释","实测、阈值、单位、方法和容差齐全"),("缺失不伪造","显示未提供/未评价并说明原因"),("证据不越权","截图只定位；精确测量承担结论"),("只读可验证","前后状态、保存行为和清理有记录")),(5,11.5))
    note(doc,"最终报告删除方括号占位内容并用结构化结果替换；不得删除因无数据而必须保留的模块或章节。")
    doc.core_properties.title = "CATIA V5 智能工程检查报告模板"; doc.core_properties.subject = "完整章节格式 字段契约 模块示例与缺失值规则"; doc.core_properties.author = "CATIA 管路与模型检查系统"
    OUTPUT.parent.mkdir(parents=True, exist_ok=True); doc.save(OUTPUT); print(OUTPUT)

if __name__ == "__main__": build()
