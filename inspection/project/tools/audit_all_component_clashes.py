"""Run one read-only CATIA DMU Between-All scan and write unified JSON."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
from typing import Any
from uuid import uuid4


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from catia_checker.dmu_results import convert_dmu_scan
from catia_checker.component_relationships import build_pair_context, assess_pairs
from catia_checker.llm_adapter import create_llm_adapter, load_runtime_config
from catia_checker.routing_rules import evaluate_bend_radius, general_clearance_mm, validate_rules
from catia_checker.step_geometry import inspect_step_pipe_geometry
from catia_checker.model_understanding.pipeline import analyze_step_connections
from catia_checker.model_understanding.relationships import connection_relation_for_pair
from catia_checker.model_understanding.integration import derive_inspection_disposition
from catia_checker.model_understanding.integration.regression_gate import validate_semantic_report
from catia_checker.snapshots import compare_snapshots, create_snapshot, load_snapshot, write_snapshot
from catia_checker.geometry_integrity import GeometryTolerance
from catia_checker.surface_interactions import surface_fact_to_finding
from catia_checker.geometry_candidates import build_geometry_candidates
from catia_checker.geometry_executor import execute_precision_queue, precision_plan
from catia_checker.tessellated_provider import evaluate_tessellated_plan
from catia_checker.occt_brep import OCCTBRepModel, backend_status, sweep_and_prune_pairs
from catia_checker.intersection_events import aggregate_intersection_events
from catia_checker.logical_components import (
    assemble_pipe_logical_components, recover_logical_components,
)
from catia_checker.engineering_roles import classify_tubular_roles
from catia_checker.semantic_interactions import (
    assess_solid_interactions, enrich_intersection_events,
)
from catia_checker.opening_interfaces import (
    build_opening_interface_bundle, discover_opening_interface_bundle,
    record_auto_discovery_coverage,
)
from catia_checker.pipe_candidate_review import review_pipe_candidates


def _parse_result(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        parsed = json.loads(value)
        if isinstance(parsed, dict):
            return parsed
    raise ValueError("catia_scan_product_clashes returned an unsupported payload")


def _safe_stem(document: str) -> str:
    stem = Path(document).stem or "CATProduct"
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", stem)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--rules", type=Path,
        default=PROJECT_ROOT / "config" / "rules-active.json",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--baseline", type=Path, help="Compare against an existing snapshot")
    parser.add_argument("--write-baseline", type=Path, help="Write the current normalized snapshot")
    parser.add_argument("--fail-on-regression", action="store_true")
    parser.add_argument("--skip-tubing", action="store_true",
                        help="Do not auto-discover native Arrangement Runs")
    parser.add_argument("--max-routes", type=int, default=200)
    parser.add_argument(
        "--geometry-source", type=Path,
        help="Original STEP/STP or IGES/IGS file for exact dumb-model inspection",
    )
    parser.add_argument("--skip-occt-brep", action="store_true",
                        help="Disable exact OCCT B-Rep checks for the original STEP source")
    parser.add_argument("--occt-max-pairs", type=int, default=10000)
    parser.add_argument("--occt-candidate-margin-mm", type=float, default=1e-5,
                        help="Exact geometric AABB margin for OCCT sweep-and-prune")
    parser.add_argument("--intersection-event-merge-tolerance-mm", type=float, default=25.0,
                        help="Local section-region tolerance for Face intersection event aggregation")
    parser.add_argument(
        "--surface-facts", type=Path,
        help="JSON array of deterministic Solid/Shell/Surface interaction facts from CATIA or a geometry kernel",
    )
    parser.add_argument(
        "--opening-interface-facts", type=Path,
        help="CATIA SPA/OCCT analytic opening-boundary and cylindrical-surface facts JSON",
    )
    parser.add_argument(
        "--geometry-inventory", type=Path,
        help="CATIA geometry inventory JSON with WORLD bounds; creates the precise-intersection candidate queue",
    )
    parser.add_argument(
        "--pipe-candidate-review", type=Path,
        help="Optional pipe-candidate-review.v1 JSON, including CATIA context/detail screenshot paths",
    )
    parser.add_argument("--surface-candidate-margin-mm", type=float, default=5.0,
                        help="AABB broad-phase margin for Solid/Shell/Surface candidate pairing")
    parser.add_argument("--execute-tessellated-candidates", action="store_true",
                        help="Execute candidates with TESSELLATED capability and merge their deterministic facts")
    parser.add_argument(
        "--route", action="append", default=[], metavar="ROUTE_NAME",
        help="Inspect a native Arrangement Run and include its bend-radius R/D finding; repeatable",
    )
    args = parser.parse_args()

    with args.rules.open("r", encoding="utf-8") as stream:
        rules = json.load(stream)
    validate_rules(rules)

    # Keep live CATIA imports out of the reusable offline conversion layer.
    from r18_connection import R18Connection as CATIAConnection
    from catia_mcp.tools.measurement import MeasurementTools

    connection = CATIAConnection()
    connection.connect()
    actual_release = str(connection.app.SystemConfiguration.Release).strip()
    tool = MeasurementTools(connection)
    dmu_rules = rules.get("dmu_clash", {})
    scan_clearance_mm = general_clearance_mm(rules)
    raw_scan = _parse_result(tool.execute("catia_scan_product_clashes", {
        "clearance": scan_clearance_mm,
        "exclude_pairs": rules.get("exemptions", {}).get("allowed_contact_pairs", []),
        "max_conflicts": int(dmu_rules.get("max_conflicts", 10000)),
    }))
    source_suffix = args.geometry_source.suffix.lower() if args.geometry_source else ""
    is_step_source = source_suffix in {".stp", ".step"}
    is_iges_source = source_suffix in {".igs", ".iges"}
    model_type = "STEP" if is_step_source else "IGES" if is_iges_source else "CATIA_NATIVE"
    connection_graph = None
    if is_step_source and args.geometry_source.exists():
        connection_graph = analyze_step_connections(args.geometry_source)
        for conflict in raw_scan.get("conflicts", []):
            first_aliases = (conflict.get("first_product"), conflict.get("first_part_number"))
            second_aliases = (conflict.get("second_product"), conflict.get("second_part_number"))
            relation = next((resolved for first in first_aliases for second in second_aliases
                             if first and second and (resolved := connection_relation_for_pair(
                                 connection_graph, str(first), str(second)))), None)
            if relation:
                conflict["assembly_relation"] = relation
    pair_contexts = [build_pair_context(item, model_type=model_type)
                     for item in raw_scan.get("conflicts", [])]
    runtime = load_runtime_config(PROJECT_ROOT / "config" / "runtime.json")
    relationship_adapter = create_llm_adapter(runtime)
    relationship_rules = rules.get("component_relationship", {})
    pass_confidence = float(relationship_rules.get(
        "step_minimum_pass_confidence" if model_type == "STEP" else "minimum_pass_confidence",
        0.92 if model_type == "STEP" else 0.85))
    assessments = assess_pairs(
        pair_contexts, relationship_adapter.judge_relationships,
        minimum_pass_confidence=pass_confidence)
    for conflict, context, assessment in zip(raw_scan.get("conflicts", []), pair_contexts, assessments):
        conflict["relationship_context"] = context
        conflict["relationship_assessment"] = assessment.to_dict()
        conflict["inspection_disposition"] = derive_inspection_disposition(
            conflict, conflict["relationship_assessment"])
    bundle = convert_dmu_scan(raw_scan, rules)
    payload = bundle.to_dict()
    payload["applied_rules"] = rules
    payload["run_id"] = f"CATIA-{datetime.now():%Y%m%d-%H%M%S}-{uuid4().hex[:8]}"
    payload["generated_at"] = datetime.now(timezone.utc).isoformat()
    payload["audit"] = {
        "geometry_authority": f"CATIA V5 Release {actual_release} native DMU",
        "catia_release": actual_release,
        "llm_role": "structured_relationship_judgment_and_explanation",
        "relationship_judge": type(relationship_adapter).__name__,
        "source_model_modified": False,
        "source_model_saved_by_tool": bool(payload.get("source", {}).get("source_saved_by_tool")),
        "exceptions": [],
    }
    if args.pipe_candidate_review:
        pipe_review = json.loads(args.pipe_candidate_review.read_text(encoding="utf-8"))
        if pipe_review.get("schema_version") != "pipe-candidate-review.v1":
            raise ValueError("--pipe-candidate-review must use schema pipe-candidate-review.v1")
        payload["pipe_candidate_review"] = pipe_review
    elif connection_graph:
        pipe_review_records = []
        for body_id, score in connection_graph.get("pipe_candidate_scores", {}).items():
            pipe_review_records.append({
                "name": body_id,
                "candidate_type": score.get("candidate_type"),
                "candidate": {
                    "candidate_type": score.get("candidate_type"),
                    "geometry_kind": "MULTI_FEATURE_STEP_BODY",
                    "reason": score.get("classifier"),
                },
                "aspect_ratio": next((
                    float(item.split("=", 1)[1]) for item in score.get("evidence", [])
                    if item.startswith("aspect_ratio=")
                ), None),
            })
        payload["pipe_candidate_review"] = review_pipe_candidates(pipe_review_records)
    if args.surface_facts:
        facts = json.loads(args.surface_facts.read_text(encoding="utf-8"))
        if not isinstance(facts, list):
            raise ValueError("--surface-facts must contain a JSON array")
        tolerance = GeometryTolerance(source=str(args.rules))
        for fact in facts:
            if not isinstance(fact, dict):
                raise ValueError("each surface fact must be a JSON object")
            finding = surface_fact_to_finding(
                fact, tolerance=tolerance, required_clearance_mm=scan_clearance_mm).to_dict()
            payload["findings"].append(finding)
            payload["counts"][finding["status"]] += 1
        payload["confidence_budget"]["checked"].append(
            "Solid/Shell/Surface确定性相交与穿透事实")
        payload["source"]["surface_interaction_fact_count"] = len(facts)
    if args.opening_interface_facts:
        opening_payload = json.loads(args.opening_interface_facts.read_text(encoding="utf-8"))
        if not isinstance(opening_payload, dict):
            raise ValueError("--opening-interface-facts must contain a JSON object")
        opening_bundle = build_opening_interface_bundle(opening_payload, rules=rules)
        payload["opening_interface_analysis"] = opening_bundle
        for finding in opening_bundle["findings"]:
            payload["findings"].append(finding)
            payload["counts"][finding["status"]] += 1
        payload["confidence_budget"]["checked"].append(
            "接管—开孔精确解析几何匹配与贯通判定")
        rejected = opening_bundle["adapter"]["rejected_count"]
        if rejected:
            payload["confidence_budget"]["degraded"].append(
                f"{rejected}项开孔/圆柱记录因解析证据不完整未接纳")
    if args.geometry_inventory:
        inventory = json.loads(args.geometry_inventory.read_text(encoding="utf-8"))
        if not args.opening_interface_facts and isinstance(inventory, dict):
            auto_opening = discover_opening_interface_bundle(
                inventory, source="CATIA_SPA", rules=rules)
            payload["opening_interface_auto_discovery"] = auto_opening
            if auto_opening["analysis_executed"]:
                payload["opening_interface_analysis"] = auto_opening["analysis"]
                for finding in auto_opening["analysis"]["findings"]:
                    payload["findings"].append(finding)
                    payload["counts"][finding["status"]] += 1
            record_auto_discovery_coverage(
                payload, auto_opening, authority="CATIA精确几何清单")
        entities = inventory.get("entities") if isinstance(inventory, dict) else None
        if not isinstance(entities, list) and isinstance(inventory, dict) and isinstance(inventory.get("faces"), list):
            entities = [{
                **face,
                "source_id": face.get("face_id"),
                "source_path": face.get("face_id"),
                "entity_kind": "SURFACE",
                "geometry_kind": "SURFACE",
                "capabilities": ["EXACT_BREP"],
                "geometry_state": "AVAILABLE",
                "why_skipped": None,
            } for face in inventory["faces"]]
            payload["source"]["exact_face_inventory_admitted"] = len(entities)
        if not isinstance(entities, list):
            raise ValueError("--geometry-inventory must contain an entities array or exact faces array")
        queue = build_geometry_candidates(entities, search_margin_mm=args.surface_candidate_margin_mm)
        payload["surface_interaction_candidate_queue"] = queue
        entity_index = {str(item.get("object_id") or item.get("source_id") or item.get("source_path")): item
                        for item in entities}
        payload["surface_interaction_precision_plan"] = [
            precision_plan(candidate, entity_index) for candidate in queue["candidates"]]
        if args.execute_tessellated_candidates:
            execution = execute_precision_queue(
                queue["candidates"], entities,
                lambda plan: evaluate_tessellated_plan(plan) if plan["method"] == "TESSELLATED_SURFACE_INTERSECTION"
                else (_ for _ in ()).throw(RuntimeError("PRECISION_PROVIDER_NOT_CONFIGURED")))
            payload["surface_interaction_execution"] = execution
            for fact in execution["facts"]:
                finding = surface_fact_to_finding(
                    fact, tolerance=GeometryTolerance(source=str(args.rules)),
                    required_clearance_mm=scan_clearance_mm).to_dict()
                payload["findings"].append(finding)
                payload["counts"][finding["status"]] += 1
            if execution["review_count"] or execution["not_executable_count"]:
                payload["confidence_budget"]["degraded"].append(
                    "部分曲面候选未具备可执行的精确几何提供器，已进入人工复核队列")
        payload["source"]["surface_candidate_pair_count"] = queue["candidate_pair_count"]
        payload["confidence_budget"]["checked"].append(
            "Solid/Shell/Surface世界坐标AABB候选粗筛")
        if any(item["why_skipped"] == "NO_WORLD_BOUNDS" for item in queue["skip_log"]):
            payload["confidence_budget"]["degraded"].append(
                "部分Surface/Shell缺少世界坐标包围盒，未进入精确相交队列")
    if connection_graph:
        payload["model_understanding_connection_graph"] = connection_graph
        payload["model_precheck"] = connection_graph["model_precheck"]
        precheck = connection_graph["model_precheck"]
        payload["confidence_budget"]["checked"].append(
            "STEP几何准入与模型健康预检（含零体积Shell/Surface）")
        if precheck["model_reliability"] != "HIGH":
            payload["confidence_budget"]["degraded"].append(
                f"MODEL_RELIABILITY={precheck['model_reliability']}，结论需复核")
    if args.geometry_source and not args.skip_occt_brep:
        status = backend_status()
        payload["audit"]["occt_brep_backend"] = status
        if not status["available"]:
            payload["confidence_budget"]["degraded"].append(
                "OCCT精确B-Rep后端不可用；未回退到网格")
        else:
            occt_model = OCCTBRepModel()
            occt_manifest = (occt_model.load_iges(args.geometry_source) if is_iges_source
                             else occt_model.load_step(args.geometry_source))
            if not args.opening_interface_facts and "opening_interface_analysis" not in payload:
                auto_opening = discover_opening_interface_bundle(
                    occt_manifest, source="OCCT_BREP", rules=rules)
                payload["opening_interface_auto_discovery"] = auto_opening
                if auto_opening["analysis_executed"]:
                    payload["opening_interface_analysis"] = auto_opening["analysis"]
                    for finding in auto_opening["analysis"]["findings"]:
                        payload["findings"].append(finding)
                        payload["counts"][finding["status"]] += 1
                record_auto_discovery_coverage(
                    payload, auto_opening, authority="OCCT精确B-Rep")
            root_shape_id = occt_manifest["root_shape_id"]
            shape_descriptions = [item for item in occt_manifest["shapes"]
                                  if item["shape_id"] != root_shape_id]
            description_index = {item["shape_id"]: item for item in shape_descriptions}
            broad_phase = sweep_and_prune_pairs(
                shape_descriptions, margin_mm=args.occt_candidate_margin_mm)
            candidate_pairs = broad_phase.pop("pairs")
            exact_facts = []
            truncated = False
            primary_fact_count = 0
            suppressed_clearance_count = 0
            for first, second in candidate_pairs:
                if len(exact_facts) >= args.occt_max_pairs:
                    truncated = True
                    break
                first_desc, second_desc = description_index[first], description_index[second]
                entity_a = {"geometry_kind": "SOLID" if first_desc["solid_count"] else "SURFACE",
                            "capabilities": ["EXACT_BREP"]}
                entity_b = {"geometry_kind": "SOLID" if second_desc["solid_count"] else "SURFACE",
                            "capabilities": ["EXACT_BREP"]}
                solid_pair = (entity_a["geometry_kind"] == "SOLID"
                              and entity_b["geometry_kind"] == "SOLID")
                fact = occt_model.pair_fact(first, second, entity_a=entity_a, entity_b=entity_b)
                fact["object_a_name"] = first_desc.get("source_name")
                fact["object_b_name"] = second_desc.get("source_name")
                exact_facts.append(fact)
                # Clearance-only eliminations stay in the exact audit trail. The
                # primary engineering list contains actionable intersection/contact facts.
                if fact.get("intersection_type") == "SURFACE_CLEARANCE":
                    suppressed_clearance_count += 1
                    continue
                primary_fact_count += 1
                if solid_pair:
                    # Solid material interference is independent of the general
                    # routing-clearance rule.  Apply zero here; component-level
                    # spacing remains the responsibility of native DMU findings.
                    finding = surface_fact_to_finding(
                        fact, tolerance=GeometryTolerance(source="OCCT_BREP"),
                        required_clearance_mm=0.0).to_dict()
                    payload["findings"].append(finding)
                    payload["counts"][finding["status"]] += 1
                    continue
                finding = surface_fact_to_finding(
                    fact, tolerance=GeometryTolerance(source="OCCT_BREP"),
                    required_clearance_mm=scan_clearance_mm).to_dict()
                payload["findings"].append(finding)
                payload["counts"][finding["status"]] += 1
            intersection_events = aggregate_intersection_events(
                exact_facts, merge_tolerance_mm=args.intersection_event_merge_tolerance_mm)
            logical_components = recover_logical_components(shape_descriptions, exact_facts)
            pipe_components = assemble_pipe_logical_components(logical_components, exact_facts)
            engineering_roles = classify_tubular_roles(logical_components, exact_facts)
            semantic_events = enrich_intersection_events(
                intersection_events, logical_components, engineering_roles, exact_facts)
            solid_assessments = assess_solid_interactions(
                fact for fact in exact_facts
                if str((fact.get("entity_a") or {}).get("geometry_kind")).upper() == "SOLID"
                and str((fact.get("entity_b") or {}).get("geometry_kind")).upper() == "SOLID")
            payload["intersection_events"] = intersection_events
            payload["logical_components"] = logical_components
            payload["pipe_logical_components"] = pipe_components
            payload["engineering_roles"] = engineering_roles
            payload["semantic_intersection_events"] = semantic_events
            payload["solid_interaction_assessments"] = solid_assessments
            payload["occt_brep"] = {"manifest": occt_manifest, "pair_fact_count": len(exact_facts),
                                     "pair_facts": exact_facts, "truncated": truncated,
                                     "broad_phase": broad_phase,
                                     "intersection_event_count": intersection_events["event_count"],
                                     "logical_component_count": logical_components["component_count"],
                                     "pipe_logical_component_count": pipe_components["pipe_candidate_count"],
                                     "semantic_intersection_event_count": semantic_events["event_count"],
                                     "semantic_disposition_counts": semantic_events["disposition_counts"],
                                     "solid_disposition_counts": solid_assessments["disposition_counts"],
                                     "primary_fact_count": primary_fact_count,
                                     "suppressed_clearance_count": suppressed_clearance_count,
                                     "mesh_used": False}
            payload["confidence_budget"]["checked"].append(
                f"原始{'IGES' if is_iges_source else 'STEP'}的OCCT精确B-Rep距离、截交与公共体积")
            if truncated:
                payload["confidence_budget"]["degraded"].append(
                    f"OCCT精确配对达到occt_max_pairs={args.occt_max_pairs}上限")
    route_names = list(args.route)
    tubing_errors = []
    if not args.skip_tubing:
        from catia_mcp.tools.tubing import TubingTools
        tubing = TubingTools(connection)
        if not route_names:
            try:
                runs = tubing._arrangement_product().ArrangementRuns
                route_names = [str(runs.Item(index).Name)
                               for index in range(1, min(runs.Count, args.max_routes) + 1)]
                if runs.Count > args.max_routes:
                    tubing_errors.append(
                        f"原生管路数量{runs.Count}超过max_routes={args.max_routes}，检查范围已截断")
            except Exception as exc:
                tubing_errors.append(f"原生Arrangement Run不可用：{exc}")
        for route_name in route_names:
            try:
                route_data = _parse_result(tubing._inspect_route(route_name))
                internal_nodes = route_data.get("nodes", [])[1:-1]
                route_measurement = {
                    "name": route_name,
                    "diameter_mm": route_data.get("SectionDiameter"),
                    "bend_radii_mm": [node.get("bend_radius") for node in internal_nodes],
                }
                finding = evaluate_bend_radius(route_measurement, rules).to_dict()
                payload["findings"].append(finding)
                payload["counts"][finding["status"]] += 1
            except Exception as exc:
                tubing_errors.append(f"{route_name}：{exc}")
        payload["source"]["inspected_routes"] = route_names
        if route_names:
            payload["confidence_budget"]["checked"].append("原生管路逐条弯曲半径")
        else:
            geometry_source = args.geometry_source
            if geometry_source and geometry_source.exists() and is_step_source:
                inferred = inspect_step_pipe_geometry(geometry_source)
                payload["source"]["dumb_model_pipe_inference"] = inferred
                payload["audit"]["geometry_authority"] = (
                    f"CATIA V5 Release {actual_release} native DMU + "
                    "STEP analytic surface inference")
                for bend in inferred["bends"]:
                    finding = evaluate_bend_radius(bend, rules).to_dict()
                    finding["evidence"][0]["source"] = inferred["method"]
                    finding["evidence"][0]["description"] = (
                        "STEP解析圆环面反推：大半径=管中心线弯曲半径，2×小半径=外径候选")
                    finding["evidence"][0]["data"].update({
                        "step_entity": bend["step_entity"],
                        "placement_entity": bend["placement_entity"],
                        "confidence": bend["confidence"],
                        "basis": bend["basis"],
                    })
                    finding["metadata"].update({
                        "geometry_origin": "DUMB_STEP",
                        "recognition_confidence": bend["confidence"],
                    })
                    payload["findings"].append(finding)
                    payload["counts"][finding["status"]] += 1
                payload["confidence_budget"]["checked"].extend([
                    "STEP解析圆柱/圆环面识别管径与弯头候选",
                    "STEP哑模型管路间距（CATIA DMU几何扫描）",
                    "STEP圆环面中心线弯曲半径与R/D",
                ])
                if not inferred["bends"]:
                    payload["confidence_budget"]["not_checked"].append(
                        "STEP中未识别到可靠解析圆环面；需截面拟合中心线半径")
            else:
                payload["confidence_budget"]["not_checked"].append(
                    "未发现原生Arrangement Run，且未提供可用的STEP源文件；无法执行管路解析几何反推")
        if tubing_errors:
            payload["confidence_budget"]["degraded"].extend(tubing_errors)
            payload["audit"]["exceptions"].extend(tubing_errors)
    else:
        payload["confidence_budget"]["not_checked"].append("调用参数关闭了管路专项检查")
    payload["confidence_budget"]["is_complete"] = not (
        payload["confidence_budget"]["not_checked"] or payload["confidence_budget"]["degraded"])
    current_snapshot = create_snapshot(payload)
    comparison = None
    if args.baseline:
        comparison = compare_snapshots(current_snapshot, load_snapshot(args.baseline))
        payload["baseline_comparison"] = comparison
    if args.write_baseline:
        write_snapshot(current_snapshot, args.write_baseline)

    payload["audit"]["semantic_regression_gate"] = validate_semantic_report(payload)

    output = args.output or (PROJECT_ROOT / "output" / "runs" / payload["run_id"] / "check.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"output": str(output), **payload}, indent=2, ensure_ascii=False))
    if args.fail_on_regression and comparison and comparison["has_regressions"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
