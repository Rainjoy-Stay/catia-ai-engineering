"""Exact OCCT B-Rep validation layer for mesh-planned CATIA routes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .occt_brep import OCCTBRepModel


@dataclass(frozen=True)
class ComponentRoutePolicy:
    mode: str = "CLEARANCE"
    minimum_clearance_mm: float = 0.0

    def __post_init__(self) -> None:
        if self.mode not in {"REQUIRED_CONTACT", "ALLOW_CONTACT", "CLEARANCE"}:
            raise ValueError(f"Unsupported component route policy: {self.mode}")
        if self.minimum_clearance_mm < 0:
            raise ValueError("minimum_clearance_mm cannot be negative")


@dataclass(frozen=True)
class BoundaryRoutePolicy:
    component: str
    mode: str = "WALL_ENCLOSURE"
    minimum_contained_fraction: float = 0.999999

    def __post_init__(self) -> None:
        if self.mode not in {"WALL_ENCLOSURE", "PERMITTED_VOLUME"}:
            raise ValueError(f"Unsupported boundary policy: {self.mode}")
        if not 0 < self.minimum_contained_fraction <= 1:
            raise ValueError("minimum_contained_fraction must be in (0, 1]")


@dataclass(frozen=True)
class BRepRouteValidationRequest:
    step_file: str | Path
    route_shape_id: str
    component_shapes: dict[str, tuple[str, ...]]
    allowed_zero_distance_contacts: frozenset[str] = frozenset()
    boundary_component: str | None = None
    tolerance_mm: float = 1e-6
    volume_tolerance_mm3: float = 1e-7


@dataclass(frozen=True)
class SeparateBRepRouteValidationRequest:
    route_step_file: str | Path
    environment_step_file: str | Path
    route_shape_id: str
    component_shapes: dict[str, tuple[str, ...]]
    allowed_zero_distance_contacts: frozenset[str] = frozenset()
    required_zero_distance_contacts: frozenset[str] = frozenset()
    component_policies: dict[str, ComponentRoutePolicy] | None = None
    boundary_component: str | None = None
    boundary_policy: BoundaryRoutePolicy | None = None
    permitted_volume_step_file: str | Path | None = None
    permitted_volume_shape_id: str = "STEP_SOLID_0001"
    tolerance_mm: float = 1e-6
    volume_tolerance_mm3: float = 1e-7


def validate_separate_route_brep(request: SeparateBRepRouteValidationRequest) -> dict[str, object]:
    """Validate a generated route STEP against a separate environment STEP."""
    route_model, environment = OCCTBRepModel(), OCCTBRepModel()
    route_manifest = route_model.load_step(request.route_step_file, lightweight=True)
    environment_manifest = environment.load_step(request.environment_step_file, lightweight=True)
    route_shapes = {item["shape_id"]: item for item in route_manifest["shapes"]}
    environment_shapes = {item["shape_id"]: item for item in environment_manifest["shapes"]}
    if request.route_shape_id not in route_shapes:
        raise ValueError(f"Unknown route shape: {request.route_shape_id}")
    route_bounds = route_shapes[request.route_shape_id]["bounds_mm"]
    route_volume = float(route_shapes[request.route_shape_id].get("volume_mm3") or 0.0)
    overall, results = "PASS", []
    for component, shape_ids in request.component_shapes.items():
        facts = []
        for shape_id in shape_ids:
            if shape_id not in environment_shapes:
                raise ValueError(f"Unknown environment shape: {shape_id}")
            distance = route_model.distance_to(request.route_shape_id, environment, shape_id)
            common = route_model.common_volume_to(request.route_shape_id, environment, shape_id)
            facts.append({
                "shape_id": shape_id,
                "minimum_distance_mm": distance["minimum_distance_mm"],
                "intersection_volume_mm3": common["intersection_volume_mm3"],
            })
        minimum = min(item["minimum_distance_mm"] for item in facts)
        volume = sum(item["intersection_volume_mm3"] for item in facts)
        boundary_policy = request.boundary_policy
        is_permitted_volume = bool(
            boundary_policy and boundary_policy.component == component
            and boundary_policy.mode == "PERMITTED_VOLUME"
            and request.permitted_volume_step_file is None)
        policy = ((request.component_policies or {}).get(component) or
                  ComponentRoutePolicy(
                      "REQUIRED_CONTACT" if component in request.required_zero_distance_contacts
                      else "ALLOW_CONTACT" if component in request.allowed_zero_distance_contacts
                      else "CLEARANCE"))
        if is_permitted_volume:
            state, failed = classify_route_containment(
                route_volume, volume, boundary_policy.minimum_contained_fraction)
        else:
            state, failed = classify_component_interaction(
                minimum, volume, policy, request.tolerance_mm, request.volume_tolerance_mm3)
        if failed: overall = "FAIL"
        record: dict[str, object] = {
            "component": component, "state": state,
            "minimum_distance_mm": minimum, "intersection_volume_mm3": volume,
            "shape_facts": facts,
            "policy": {"mode": policy.mode,
                       "minimum_clearance_mm": policy.minimum_clearance_mm},
        }
        if is_permitted_volume:
            record["route_volume_mm3"] = route_volume
            record["contained_volume_mm3"] = volume
            record["contained_fraction"] = (volume / route_volume if route_volume > 0 else 0.0)
            record["boundary_policy"] = asdict_boundary_policy(boundary_policy)
        elif component == request.boundary_component or (
            boundary_policy and boundary_policy.component == component
            and boundary_policy.mode == "WALL_ENCLOSURE"
        ):
            bounds = _combined_bounds(environment_shapes[sid]["bounds_mm"] for sid in shape_ids)
            inside = all(bounds["min"][i] - request.tolerance_mm <= route_bounds["min"][i]
                         and route_bounds["max"][i] <= bounds["max"][i] + request.tolerance_mm
                         for i in range(3))
            record["route_inside_boundary_brep_bounds"] = inside
            record["boundary_crossing"] = volume > request.volume_tolerance_mm3
            if not inside or record["boundary_crossing"]: overall = "FAIL"
        results.append(record)
    permitted_volume_source = None
    if request.permitted_volume_step_file is not None:
        if not request.boundary_policy or request.boundary_policy.mode != "PERMITTED_VOLUME":
            raise ValueError("A separate permitted volume requires PERMITTED_VOLUME policy")
        permitted = OCCTBRepModel()
        permitted_manifest = permitted.load_step(
            request.permitted_volume_step_file, lightweight=True)
        permitted_shapes = {item["shape_id"]: item for item in permitted_manifest["shapes"]}
        if request.permitted_volume_shape_id not in permitted_shapes:
            raise ValueError(
                f"Unknown permitted-volume shape: {request.permitted_volume_shape_id}")
        common = route_model.common_volume_to(
            request.route_shape_id, permitted, request.permitted_volume_shape_id)
        contained_volume = common["intersection_volume_mm3"]
        state, failed = classify_route_containment(
            route_volume, contained_volume,
            request.boundary_policy.minimum_contained_fraction)
        if failed:
            overall = "FAIL"
        results.append({
            "component": request.boundary_policy.component,
            "state": state,
            "minimum_distance_mm": None,
            "intersection_volume_mm3": contained_volume,
            "route_volume_mm3": route_volume,
            "contained_volume_mm3": contained_volume,
            "contained_fraction": contained_volume / route_volume if route_volume > 0 else 0.0,
            "boundary_policy": asdict_boundary_policy(request.boundary_policy),
            "shape_facts": [{
                "shape_id": request.permitted_volume_shape_id,
                "intersection_volume_mm3": contained_volume,
            }],
            "geometry_authority": "OCCT_EXACT_BREP_SEPARATE_PERMITTED_VOLUME",
            "policy": {"mode": "CLEARANCE", "minimum_clearance_mm": 0.0},
        })
        permitted_volume_source = str(Path(request.permitted_volume_step_file).resolve())
    return {
        "schema_version": "brep-route-validation.v2.0", "status": overall,
        "geometry_authority": "OCCT_EXACT_BREP", "mesh_used_for_validation": False,
        "route_step": str(Path(request.route_step_file).resolve()),
        "environment_step": str(Path(request.environment_step_file).resolve()),
        "route_shape_id": request.route_shape_id, "route_bounds_mm": route_bounds,
        "components": results,
        "required_zero_distance_contacts": sorted(request.required_zero_distance_contacts),
        "boundary_policy": (asdict_boundary_policy(request.boundary_policy)
                            if request.boundary_policy else None),
        "permitted_volume_step": permitted_volume_source,
    }


def classify_component_interaction(
    minimum_distance_mm: float, intersection_volume_mm3: float,
    policy: ComponentRoutePolicy, tolerance_mm: float = 1e-6,
    volume_tolerance_mm3: float = 1e-7,
) -> tuple[str, bool]:
    """Deterministic relationship gate independent of component names."""
    if intersection_volume_mm3 > volume_tolerance_mm3:
        return "INTERFERENCE", True
    contact = minimum_distance_mm <= tolerance_mm
    if policy.mode == "REQUIRED_CONTACT":
        return ("REQUIRED_CONTACT_OK", False) if contact else ("MISSING_REQUIRED_CONTACT", True)
    if policy.mode == "ALLOW_CONTACT" and contact:
        return "ACCEPTED_CONTACT", False
    if policy.mode == "CLEARANCE" and minimum_distance_mm + tolerance_mm < policy.minimum_clearance_mm:
        return "INSUFFICIENT_CLEARANCE", True
    return "CLEARANCE", False


def classify_route_containment(
    route_volume_mm3: float, contained_volume_mm3: float,
    minimum_contained_fraction: float = 0.999999,
) -> tuple[str, bool]:
    if route_volume_mm3 <= 0:
        return "INVALID_ROUTE_VOLUME", True
    fraction = max(0.0, min(1.0, contained_volume_mm3 / route_volume_mm3))
    if fraction + 1e-12 < minimum_contained_fraction:
        return "OUTSIDE_PERMITTED_VOLUME", True
    return "CONTAINED_IN_PERMITTED_VOLUME", False


def asdict_boundary_policy(policy: BoundaryRoutePolicy) -> dict[str, object]:
    return {
        "component": policy.component, "mode": policy.mode,
        "minimum_contained_fraction": policy.minimum_contained_fraction,
    }


def validate_route_brep(request: BRepRouteValidationRequest) -> dict[str, object]:
    """Validate one exported route solid against exact component B-Reps."""
    model = OCCTBRepModel()
    manifest = model.load_step(request.step_file, lightweight=True)
    descriptions = {item["shape_id"]: item for item in manifest["shapes"]}
    if request.route_shape_id not in descriptions:
        raise ValueError(f"Unknown route shape: {request.route_shape_id}")
    route_bounds = descriptions[request.route_shape_id]["bounds_mm"]
    results = []
    overall = "PASS"
    for component, shape_ids in request.component_shapes.items():
        facts = []
        for shape_id in shape_ids:
            distance = model.distance(request.route_shape_id, shape_id)
            common = model.common_volume(request.route_shape_id, shape_id)
            facts.append({
                "shape_id": shape_id,
                "minimum_distance_mm": distance["minimum_distance_mm"],
                "closest_route_point_mm": distance["closest_point_a_mm"],
                "closest_component_point_mm": distance["closest_point_b_mm"],
                "intersection_volume_mm3": common["intersection_volume_mm3"],
            })
        minimum = min(item["minimum_distance_mm"] for item in facts)
        volume = sum(item["intersection_volume_mm3"] for item in facts)
        if volume > request.volume_tolerance_mm3:
            state = "INTERFERENCE"
            overall = "FAIL"
        elif minimum <= request.tolerance_mm:
            state = ("ACCEPTED_CONTACT" if component in request.allowed_zero_distance_contacts
                     else "CONTACT")
            if state == "CONTACT" and overall == "PASS":
                overall = "REVIEW"
        else:
            state = "CLEARANCE"
        record: dict[str, object] = {
            "component": component, "state": state,
            "minimum_distance_mm": minimum,
            "intersection_volume_mm3": volume, "shape_facts": facts,
        }
        if component == request.boundary_component:
            component_bounds = _combined_bounds(descriptions[sid]["bounds_mm"] for sid in shape_ids)
            inside_bounds = all(
                component_bounds["min"][axis] - request.tolerance_mm <= route_bounds["min"][axis]
                and route_bounds["max"][axis] <= component_bounds["max"][axis] + request.tolerance_mm
                for axis in range(3)
            )
            record["route_inside_boundary_brep_bounds"] = inside_bounds
            record["boundary_crossing"] = volume > request.volume_tolerance_mm3
            if not inside_bounds or record["boundary_crossing"]:
                overall = "FAIL"
        results.append(record)
    return {
        "schema_version": "brep-route-validation.v1.0",
        "status": overall,
        "geometry_authority": "OCCT_EXACT_BREP",
        "mesh_used_for_validation": False,
        "source_step": str(Path(request.step_file).resolve()),
        "route_shape_id": request.route_shape_id,
        "route_bounds_mm": route_bounds,
        "components": results,
        "boundary_note": (
            "Exact B-Rep common/clearance plus bounds containment; connected cavity "
            "selection remains the mesh free-space planner's responsibility."
        ),
    }


def _combined_bounds(bounds: Iterable[dict[str, list[float]]]) -> dict[str, list[float]]:
    values = list(bounds)
    return {
        "min": [min(item["min"][axis] for item in values) for axis in range(3)],
        "max": [max(item["max"][axis] for item in values) for axis in range(3)],
    }
