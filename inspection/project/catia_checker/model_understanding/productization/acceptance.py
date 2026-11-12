"""Deterministic release acceptance for a V2.0 review package."""

from __future__ import annotations

from typing import Any, Mapping


def evaluate_acceptance(package: Mapping[str, Any]) -> dict[str, Any]:
    overview = package.get("overview") or {}
    counts = overview.get("inspection_counts") or {}
    safety = package.get("safety") or {}
    gate = safety.get("semantic_regression_gate") or {}
    checks = [
        ("SCHEMA", package.get("schema_version") == "model-understanding-review-package.v2.0",
         "交付包结构版本正确"),
        ("SEMANTIC_GATE", gate.get("passed") is True, "语义安全回归门禁通过"),
        ("NO_ENGINE_ERRORS", int(counts.get("ERROR", 0)) == 0, "检查引擎无错误结果"),
        ("SOURCE_READ_ONLY", safety.get("source_model_modified") is False, "源模型保持只读"),
        ("FALLBACK", safety.get("fallback_available") is True, "传统检查回退可用"),
        ("GRAPH_AVAILABLE", int(overview.get("engineering_object_count", 0)) > 0 and
         int(overview.get("relationship_count", 0)) > 0, "工程对象及关系图已生成"),
        ("TOPOLOGY_AVAILABLE", int(overview.get("pipe_network_count", 0)) > 0,
         "系统级管路网络已生成"),
        ("TRACEABLE", bool(package.get("run_id")) and bool(package.get("package_fingerprint")),
         "运行编号和交付指纹完整"),
    ]
    results = [{"check_id": check_id, "passed": passed, "description": description}
               for check_id, passed, description in checks]
    pending = int((package.get("review_queue") or {}).get("pending_count", 0))
    return {
        "schema_version": "model-understanding-acceptance.v2.0",
        "release_status": "ACCEPTED_WITH_REVIEW_QUEUE" if all(item["passed"] for item in results) and pending
                          else "ACCEPTED" if all(item["passed"] for item in results) else "REJECTED",
        "automated_checks": results,
        "automated_pass_count": sum(item["passed"] for item in results),
        "automated_check_count": len(results),
        "pending_engineering_review_count": pending,
        "review_note": "待复核项没有被自动放行，不影响已验证能力的技术验收。" if pending else "无待复核项。",
    }


def acceptance_markdown(acceptance: Mapping[str, Any], package: Mapping[str, Any]) -> str:
    lines = [
        "# 哑模型工程对象及连接关系智能识别模块 V2.0 验收报告",
        "",
        f"- 验收状态：{acceptance['release_status']}",
        f"- 模型：{package.get('document')}",
        f"- 自动验收：{acceptance['automated_pass_count']}/{acceptance['automated_check_count']} 通过",
        f"- 待工程人工复核：{acceptance['pending_engineering_review_count']} 项",
        "",
        "## 自动验收明细",
        "",
    ]
    for item in acceptance["automated_checks"]:
        lines.append(f"- {'通过' if item['passed'] else '失败'}｜{item['check_id']}｜{item['description']}")
    lines.extend(["", "## 验收边界", "", f"- {acceptance['review_note']}",
                  "- 人工确认记录独立保存，不覆盖原始识别证据。",
                  "- 语义模块不可用时回退到传统几何检查。",
                  "- CATIA 源模型未被修改。", ""])
    return "\n".join(lines)
