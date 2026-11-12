"""Normalized deterministic CATIA V5 inspection for a standard MCP client."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import uuid4

from catia_checker.dmu_results import convert_dmu_scan
from catia_checker.component_relationships import (
    build_pair_context, assess_pairs, conservative_assessment,
)
from catia_checker.llm_adapter import create_llm_adapter, load_runtime_config
from catia_checker.routing_rules import evaluate_bend_radius, general_clearance_mm, validate_rules
from catia_checker.step_geometry import inspect_step_pipe_geometry
from catia_checker.opening_interfaces import build_opening_interface_bundle


class CheckTool:
    def __init__(self, measurement, tubing):
        self.measurement = measurement
        self.tubing = tubing
        self._clearance_investigations = {}

    def get_tool_definitions(self):
        return [{"name": "catia_check_assembly", "description": (
            "Check the active CATIA V5 CATProduct using a validated packaged ruleset. "
            "Runs DMU and, when available, discovers native Arrangement Runs and evaluates bend radii. "
            "Returns an applied-rule snapshot and explicit coverage limits."), "inputSchema": {
                "type": "object", "properties": {
                    "rules_file": {"type": "string", "description":
                        "Optional JSON filename under project/config; defaults to rules-active.json"},
                    "include_tubing": {"type": "boolean", "default": True},
                    "max_routes": {"type": "integer", "minimum": 1, "maximum": 500, "default": 200},
                    "model_type": {"type": "string", "enum": ["AUTO", "CATIA_NATIVE", "STEP"],
                                   "default": "AUTO", "description":
                        "Use STEP for an imported neutral model so relationship judgment uses stricter confidence."},
                    "opening_interface_facts": {"type": "string", "description":
                        "Optional JSON file containing exact CATIA SPA/OCCT opening and cylinder facts."},
                }, "additionalProperties": False}},
            {"name": "catia_prepare_clearance_investigation", "description": (
                "Run one read-only CATIA DMU candidate scan for an AI-led component-clearance investigation. "
                "Returns fact-only component-pair contexts and an investigation_id; it does not decide design intent."),
             "inputSchema": {"type": "object", "properties": {
                 "rules_file": {"type": "string"},
                 "model_type": {"type": "string", "enum": ["AUTO", "CATIA_NATIVE", "STEP"], "default": "AUTO"},
                 "geometry_source": {"type": "string", "description":
                     "Optional original .stp/.step path for dumb-model pipe and bend-radius inference."},
             }, "additionalProperties": False}},
            {"name": "catia_finalize_clearance_investigation", "description": (
                "Validate and apply the AI agent's evidence-backed relationship judgments to a prepared scan. "
                "Does not rerun DMU or alter measured values. Writes a unified auditable JSON result."),
             "inputSchema": {"type": "object", "properties": {
                 "investigation_id": {"type": "string"},
                 "assessments": {"type": "array", "items": {"type": "object", "properties": {
                     "pair_id": {"type": "string"},
                     "decision": {"type": "string", "enum": ["PASS_NORMAL_CONNECTION", "CHECK_CLEARANCE", "REVIEW_REQUIRED"]},
                     "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                     "reason": {"type": "string"},
                     "key_evidence": {"type": "array", "items": {"type": "string"}},
                     "relation_type": {"type": "string"},
                     "evidence_trace": {"type": "array", "items": {"type": "object"}},
                     "unresolved_questions": {"type": "array", "items": {"type": "string"}},
                 }, "required": ["pair_id", "decision", "confidence", "reason", "key_evidence"],
                    "additionalProperties": False}},
             }, "required": ["investigation_id", "assessments"], "additionalProperties": False}}]

    @staticmethod
    def _parse(value):
        return json.loads(value) if isinstance(value, str) else value

    @staticmethod
    def _rules_path(root: Path, requested: str | None) -> Path:
        config = (root / "project" / "config").resolve()
        candidate = (config / (requested or "rules-active.json")).resolve()
        if candidate.parent != config or candidate.suffix.lower() != ".json":
            raise ValueError("rules_file must name a JSON file directly under project/config")
        if not candidate.is_file():
            raise FileNotFoundError(f"Rules file not found: {candidate.name}")
        return candidate

    def _inspect_routes(self, rules, max_routes: int):
        findings, errors, names = [], [], []
        try:
            runs = self.tubing._arrangement_product().ArrangementRuns
            names = [str(runs.Item(i).Name) for i in range(1, min(runs.Count, max_routes) + 1)]
            if runs.Count > max_routes:
                errors.append(f"原生管路数量{runs.Count}超过max_routes={max_routes}，结果不完整")
        except Exception as exc:
            return findings, names, [f"原生Arrangement Run不可用：{exc}"]
        for route_name in names:
            try:
                route = self._parse(self.tubing.execute(
                    "catia_tubing_inspect_route", {"route_name": route_name}))
                internal = route.get("nodes", [])[1:-1]
                findings.append(evaluate_bend_radius({
                    "name": route_name, "diameter_mm": route.get("SectionDiameter"),
                    "bend_radii_mm": [node.get("bend_radius") for node in internal],
                }, rules).to_dict())
            except Exception as exc:
                errors.append(f"{route_name}：{exc}")
        return findings, names, errors

    def execute(self, name, args):
        if name == "catia_prepare_clearance_investigation":
            return self._prepare_clearance_investigation(args or {})
        if name == "catia_finalize_clearance_investigation":
            return self._finalize_clearance_investigation(args or {})
        if name != "catia_check_assembly":
            raise ValueError(f"Unexpected tool: {name}")
        args = args or {}
        root = Path(__file__).resolve().parents[1]
        rules_path = self._rules_path(root, args.get("rules_file"))
        rules = json.loads(rules_path.read_text(encoding="utf-8"))
        validate_rules(rules)
        raw = self._parse(self.measurement.execute("catia_scan_product_clashes", {
            "clearance": general_clearance_mm(rules),
            "exclude_pairs": rules.get("exemptions", {}).get("allowed_contact_pairs", []),
            "max_conflicts": int(rules["dmu_clash"]["max_conflicts"]),
        }))
        if not isinstance(raw, dict) or "error" in raw or "conflicts" not in raw:
            raise RuntimeError("CATIA scan failed or returned no conflict data: " + str(raw))
        requested_type = str(args.get("model_type", "AUTO")).upper()
        model_type = ("STEP" if requested_type == "AUTO" and
                      raw.get("direct_transient_step_fallback") else
                      "CATIA_NATIVE" if requested_type == "AUTO" else requested_type)
        contexts = [build_pair_context(item, model_type=model_type)
                    for item in raw.get("conflicts", [])]
        adapter = create_llm_adapter(load_runtime_config(root / "project" / "config" / "runtime.json"))
        relationship_rules = rules.get("component_relationship", {})
        minimum_confidence = float(relationship_rules.get(
            "step_minimum_pass_confidence" if model_type == "STEP" else "minimum_pass_confidence",
            0.92 if model_type == "STEP" else 0.85))
        assessments = assess_pairs(contexts, adapter.judge_relationships,
                                   minimum_pass_confidence=minimum_confidence)
        for conflict, context, assessment in zip(raw.get("conflicts", []), contexts, assessments):
            conflict["relationship_context"] = context
            conflict["relationship_assessment"] = assessment.to_dict()
        payload = convert_dmu_scan(raw, rules).to_dict()
        payload.update({
            "applied_rules": rules, "rules_file": rules_path.name,
            "run_id": f"CATIA-{datetime.now():%Y%m%d-%H%M%S}-{uuid4().hex[:8]}",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "audit": {"geometry_authority": "CATIA V5 native calculation",
                      "llm_role": "structured_relationship_judgment_and_explanation",
                      "relationship_judge": type(adapter).__name__,
                      "relationship_model_type": model_type, "exceptions": []},
        })
        opening_facts = args.get("opening_interface_facts")
        if opening_facts:
            source_path = Path(str(opening_facts)).resolve()
            opening_payload = json.loads(source_path.read_text(encoding="utf-8"))
            if not isinstance(opening_payload, dict):
                raise ValueError("opening_interface_facts must contain a JSON object")
            opening_bundle = build_opening_interface_bundle(opening_payload, rules=rules)
            payload["opening_interface_analysis"] = opening_bundle
            for finding in opening_bundle["findings"]:
                payload["findings"].append(finding)
                payload["counts"][finding["status"]] += 1
            payload["confidence_budget"]["checked"].append(
                "接管—开孔精确解析几何匹配与贯通判定")
        if args.get("include_tubing", True):
            route_findings, route_names, route_errors = self._inspect_routes(
                rules, int(args.get("max_routes", 200)))
            for finding in route_findings:
                payload["findings"].append(finding)
                payload["counts"][finding["status"]] += 1
            payload["source"]["inspected_routes"] = route_names
            if route_names:
                payload["confidence_budget"]["checked"].append("原生Arrangement Run逐条弯曲半径")
            else:
                payload["confidence_budget"]["not_checked"].append(
                    "未发现或无法读取原生Arrangement Run；哑模型管路需专项测量")
            if route_errors:
                payload["confidence_budget"]["degraded"].extend(route_errors)
                payload["audit"]["exceptions"].extend(route_errors)
        else:
            payload["confidence_budget"]["not_checked"].append("调用参数关闭了管路专项检查")
        payload["confidence_budget"]["is_complete"] = not (
            payload["confidence_budget"]["not_checked"] or payload["confidence_budget"]["degraded"])
        run_dir = root / "project" / "output" / "runs" / payload["run_id"]
        run_dir.mkdir(parents=True, exist_ok=False)
        target = run_dir / "check.json"
        payload["result_file"] = str(target)
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return json.dumps(payload, ensure_ascii=False)

    def _prepare_clearance_investigation(self, args):
        root = Path(__file__).resolve().parents[1]
        rules_path = self._rules_path(root, args.get("rules_file"))
        rules = json.loads(rules_path.read_text(encoding="utf-8"))
        validate_rules(rules)
        raw = self._parse(self.measurement.execute("catia_scan_product_clashes", {
            "clearance": general_clearance_mm(rules),
            "exclude_pairs": [],
            "max_conflicts": int(rules["dmu_clash"]["max_conflicts"]),
        }))
        if not isinstance(raw, dict) or "conflicts" not in raw:
            raise RuntimeError("CATIA candidate scan returned no conflict data")
        requested = str(args.get("model_type", "AUTO")).upper()
        model_type = ("STEP" if requested == "AUTO" and raw.get("direct_transient_step_fallback")
                      else "CATIA_NATIVE" if requested == "AUTO" else requested)
        contexts = [build_pair_context(item, model_type=model_type)
                    for item in raw.get("conflicts", [])]
        investigation_id = f"CLR-{datetime.now():%Y%m%d-%H%M%S}-{uuid4().hex[:8]}"
        self._clearance_investigations[investigation_id] = {
            "raw": raw, "rules": rules, "rules_file": rules_path.name,
            "model_type": model_type, "contexts": contexts,
            "geometry_source": args.get("geometry_source"),
        }
        return json.dumps({
            "investigation_id": investigation_id,
            "document": raw.get("document"), "model_type": model_type,
            "clearance_mm": raw.get("clearance_mm"),
            "candidate_count": len(contexts), "truncated": raw.get("truncated", False),
            "pair_contexts": contexts,
            "next_action": "AI应按Skill选择补充取证工具，再逐对提交有证据引用的关系判断。",
        }, ensure_ascii=False)

    def _finalize_clearance_investigation(self, args):
        from catia_checker.component_relationships import validate_ai_assessment
        investigation_id = str(args["investigation_id"])
        state = self._clearance_investigations.get(investigation_id)
        if state is None:
            raise ValueError("Unknown or expired investigation_id")
        supplied = {str(item["pair_id"]): item for item in args.get("assessments", [])}
        if len(supplied) != len(args.get("assessments", [])):
            raise ValueError("Duplicate pair_id in assessments")
        rules = state["rules"]
        relationship_rules = rules.get("component_relationship", {})
        threshold = float(relationship_rules.get(
            "step_minimum_pass_confidence" if state["model_type"] == "STEP" else "minimum_pass_confidence",
            0.92 if state["model_type"] == "STEP" else 0.85))
        missing = []
        for conflict, context in zip(state["raw"]["conflicts"], state["contexts"]):
            pair_id = context["pair_id"]
            value = supplied.get(pair_id)
            if value is None:
                missing.append(pair_id)
                assessment = conservative_assessment(context)
            else:
                assessment = validate_ai_assessment(context, value,
                                                    minimum_pass_confidence=threshold)
            serialized = assessment.to_dict()
            if value:
                serialized["evidence_trace"] = value.get("evidence_trace", [])
                serialized["unresolved_questions"] = value.get("unresolved_questions", [])
            conflict["relationship_context"] = context
            conflict["relationship_assessment"] = serialized
        payload = convert_dmu_scan(state["raw"], rules).to_dict()
        payload.update({
            "applied_rules": rules, "rules_file": state["rules_file"],
            "run_id": investigation_id, "generated_at": datetime.now(timezone.utc).isoformat(),
            "audit": {"geometry_authority": "CATIA V5 native calculation",
                      "llm_role": "external_skill_agent_led_relationship_investigation",
                      "relationship_judge": "calling AI agent",
                      "relationship_model_type": state["model_type"],
                      "unsubmitted_pairs": missing, "exceptions": []},
        })
        geometry_source = state.get("geometry_source")
        if state["model_type"] == "STEP" and geometry_source:
            source_path = Path(geometry_source).resolve()
            inferred = inspect_step_pipe_geometry(source_path)
            payload["source"]["dumb_model_pipe_inference"] = inferred
            for bend in inferred["bends"]:
                finding = evaluate_bend_radius(bend, rules).to_dict()
                finding["evidence"][0]["source"] = inferred["method"]
                finding["evidence"][0]["description"] = (
                    "STEP解析圆环面反推：大半径=管中心线弯曲半径，2×小半径=外径候选")
                finding["evidence"][0]["data"].update({
                    "step_entity": bend["step_entity"],
                    "placement_entity": bend["placement_entity"],
                    "confidence": bend["confidence"], "basis": bend["basis"],
                })
                finding["metadata"].update({
                    "geometry_origin": "DUMB_STEP",
                    "recognition_confidence": bend["confidence"],
                })
                payload["findings"].append(finding)
                payload["counts"][finding["status"]] += 1
            payload["confidence_budget"]["checked"].extend([
                "STEP解析圆柱/圆环面识别管径与弯头候选",
                "STEP圆环面中心线弯曲半径与R/D",
            ])
            if not inferred["bends"]:
                payload["confidence_budget"]["not_checked"].append(
                    "STEP中未识别到可靠解析圆环面；弯曲半径需截面拟合复核")
        elif state["model_type"] == "STEP":
            payload["confidence_budget"]["not_checked"].append(
                "未提供STEP源文件路径，未执行哑模型弯曲半径解析")
        payload["confidence_budget"]["is_complete"] = not (
            payload["confidence_budget"]["not_checked"] or
            payload["confidence_budget"]["degraded"])
        run_dir = root = Path(__file__).resolve().parents[1] / "project" / "output" / "runs" / investigation_id
        run_dir.mkdir(parents=True, exist_ok=False)
        target = run_dir / "check.json"
        payload["result_file"] = str(target)
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        del self._clearance_investigations[investigation_id]
        return json.dumps(payload, ensure_ascii=False)
