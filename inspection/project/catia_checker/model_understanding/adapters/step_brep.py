"""Conservative STEP B-Rep topology and analytic-surface adapter.

This parser follows explicit entity references. It does not reconstruct CAD
features, calculate geometry, or infer engineering object types.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

from ..features.surfaces import summarize_surfaces


_ENTITY = re.compile(r"#(?P<id>\d+)\s*=\s*(?P<type>[A-Z0-9_]+)\s*\((?P<args>.*)\)\s*;", re.S)
_COMPLEX_ENTITY = re.compile(r"#(?P<id>\d+)\s*=\s*\((?P<args>.*)\)\s*;", re.S)
_COMPLEX_TYPE = re.compile(r"([A-Z][A-Z0-9_]+)\s*\(")
_REF = re.compile(r"#(\d+)")
_STRING = re.compile(r"^\s*'((?:''|[^'])*)'")
_SURFACE_MAP = {
    "PLANE": "PLANE", "CYLINDRICAL_SURFACE": "CYLINDER",
    "CONICAL_SURFACE": "CONE", "SPHERICAL_SURFACE": "SPHERE",
    "TOROIDAL_SURFACE": "TORUS", "B_SPLINE_SURFACE": "BSPLINE",
    "B_SPLINE_SURFACE_WITH_KNOTS": "BSPLINE", "BEZIER_SURFACE": "FREEFORM",
    "SURFACE_OF_REVOLUTION": "FREEFORM", "SURFACE_OF_LINEAR_EXTRUSION": "FREEFORM",
}
_NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][-+]?\d+)?"


def _decode_step_string(value: str) -> str:
    def decode(match):
        try:
            return bytes.fromhex(match.group(1)).decode("utf-16-be")
        except (ValueError, UnicodeDecodeError):
            return match.group(0)
    return re.sub(r"\\X2\\([0-9A-Fa-f]+)\\X0\\", decode, value).replace("''", "'")


def _surface_parameters(entity: "StepEntity") -> dict[str, float]:
    if entity.entity_type == "CYLINDRICAL_SURFACE":
        match = re.search(rf",\s*(?P<radius>{_NUMBER})\s*$", entity.arguments)
        return {"radius": float(match.group("radius"))} if match else {}
    if entity.entity_type == "TOROIDAL_SURFACE":
        match = re.search(rf",\s*(?P<major>{_NUMBER})\s*,\s*(?P<minor>{_NUMBER})\s*$",
                          entity.arguments)
        return ({"major_radius": float(match.group("major")),
                 "minor_radius": float(match.group("minor"))} if match else {})
    if entity.entity_type == "CONICAL_SURFACE":
        match = re.search(rf",\s*(?P<radius>{_NUMBER})\s*,\s*(?P<angle>{_NUMBER})\s*$",
                          entity.arguments)
        return ({"radius": float(match.group("radius")), "semi_angle_rad": float(match.group("angle"))}
                if match else {})
    if entity.entity_type == "SPHERICAL_SURFACE":
        match = re.search(rf",\s*(?P<radius>{_NUMBER})\s*$", entity.arguments)
        return {"radius": float(match.group("radius"))} if match else {}
    return {}


def _numeric_tuple(arguments: str) -> list[float]:
    groups = re.findall(r"\(([^()]*)\)", arguments)
    if not groups:
        return []
    return [float(value) for value in re.findall(_NUMBER, groups[-1])]


def _placement(entity: "StepEntity", entities: dict[str, "StepEntity"],
               scale_to_mm: float) -> dict[str, Any]:
    placement_ref = next((ref for ref in entity.references if entities.get(ref) and
                          entities[ref].entity_type == "AXIS2_PLACEMENT_3D"), None)
    if not placement_ref:
        return {}
    placement = entities[placement_ref]
    origin = None
    directions = []
    for ref in placement.references:
        target = entities.get(ref)
        if not target:
            continue
        if target.entity_type == "CARTESIAN_POINT":
            values = _numeric_tuple(target.arguments)
            if len(values) == 3:
                origin = [value * scale_to_mm for value in values]
        elif target.entity_type == "DIRECTION":
            values = _numeric_tuple(target.arguments)
            if len(values) == 3:
                magnitude = sum(value * value for value in values) ** 0.5
                if magnitude:
                    directions.append([value / magnitude for value in values])
    return {"placement_id": placement_ref, "origin_mm": origin,
            "axis_direction": directions[0] if directions else None,
            "reference_direction": directions[1] if len(directions) > 1 else None}


def _axis_consistency(directions: list[list[float]]) -> float | None:
    if not directions:
        return None
    reference = directions[0]
    return sum(abs(sum(a * b for a, b in zip(reference, direction)))
               for direction in directions) / len(directions)


def _descendants(start: StepEntity, entities: dict[str, StepEntity], target_type: str,
                 max_depth: int = 8) -> list[StepEntity]:
    found, visited = [], set()
    queue = [(ref, 1) for ref in start.references]
    while queue:
        ref, depth = queue.pop(0)
        if ref in visited or depth > max_depth:
            continue
        visited.add(ref)
        entity = entities.get(ref)
        if not entity:
            continue
        if entity.entity_type == target_type:
            found.append(entity)
        else:
            queue.extend((child, depth + 1) for child in entity.references)
    return found


def _radius_clusters(values: list[float], relative_tolerance: float = 0.01) -> list[dict[str, Any]]:
    clusters: list[list[float]] = []
    for value in sorted(values):
        target = next((cluster for cluster in clusters
                       if abs(value - sum(cluster) / len(cluster)) <=
                       relative_tolerance * max(value, sum(cluster) / len(cluster))), None)
        if target is None:
            clusters.append([value])
        else:
            target.append(value)
    result = []
    for cluster in clusters:
        center = sum(cluster) / len(cluster)
        result.append({
            "radius": center, "sample_count": len(cluster),
            "relative_variation": ((max(cluster) - min(cluster)) / center if center else None),
            "samples": cluster,
        })
    # Equal-support concentric clusters normally represent inner and outer walls;
    # the outer radius is the relevant nominal envelope for spacing and supports.
    return sorted(result, key=lambda item: (-item["sample_count"], -item["radius"]))


@dataclass(frozen=True)
class StepEntity:
    entity_id: str
    entity_type: str
    arguments: str
    references: tuple[str, ...]
    complex_types: tuple[str, ...] = ()


def _statements(text: str):
    """Yield semicolon-terminated statements while respecting quoted strings."""
    buffer, quoted, index = [], False, 0
    while index < len(text):
        char = text[index]
        buffer.append(char)
        if char == "'":
            if quoted and index + 1 < len(text) and text[index + 1] == "'":
                buffer.append(text[index + 1]); index += 1
            else:
                quoted = not quoted
        if char == ";" and not quoted:
            yield "".join(buffer).strip()
            buffer = []
        index += 1


def _entities(text: str) -> dict[str, StepEntity]:
    result = {}
    for statement in _statements(text):
        match = _ENTITY.search(statement)
        if match:
            entity_id = f"#{match.group('id')}"
            arguments = match.group("args")
            entity_type = match.group("type")
            complex_types = ()
        else:
            complex_match = _COMPLEX_ENTITY.search(statement)
            if not complex_match:
                continue
            entity_id = f"#{complex_match.group('id')}"
            arguments = complex_match.group("args")
            entity_type = "COMPLEX_ENTITY"
            complex_types = tuple(_COMPLEX_TYPE.findall(arguments))
        result[entity_id] = StepEntity(
            entity_id, entity_type, arguments,
            tuple(f"#{value}" for value in _REF.findall(arguments)),
            complex_types,
        )
    return result


def _frame(placement: StepEntity, entities: dict[str, StepEntity], scale: float) -> list[list[float]] | None:
    data = _placement(StepEntity("#frame", "FRAME", f"({placement.entity_id})", (placement.entity_id,)),
                      entities, scale)
    origin, z_axis, x_axis = (data.get("origin_mm"), data.get("axis_direction"),
                              data.get("reference_direction"))
    if not origin or not z_axis or not x_axis:
        return None
    y_axis = [z_axis[1] * x_axis[2] - z_axis[2] * x_axis[1],
              z_axis[2] * x_axis[0] - z_axis[0] * x_axis[2],
              z_axis[0] * x_axis[1] - z_axis[1] * x_axis[0]]
    return [[x_axis[0], y_axis[0], z_axis[0], origin[0]],
            [x_axis[1], y_axis[1], z_axis[1], origin[1]],
            [x_axis[2], y_axis[2], z_axis[2], origin[2]],
            [0.0, 0.0, 0.0, 1.0]]


def _rigid_inverse(matrix: list[list[float]]) -> list[list[float]]:
    rotation = [[matrix[row][column] for row in range(3)] for column in range(3)]
    translation = [matrix[row][3] for row in range(3)]
    inverse_translation = [-sum(rotation[row][column] * translation[column] for column in range(3))
                           for row in range(3)]
    return [rotation[row] + [inverse_translation[row]] for row in range(3)] + [[0., 0., 0., 1.]]


def _multiply(left: list[list[float]], right: list[list[float]]) -> list[list[float]]:
    return [[sum(left[row][k] * right[k][column] for k in range(4))
             for column in range(4)] for row in range(4)]


def _transform_point(matrix: list[list[float]], point: list[float]) -> list[float]:
    vector = point + [1.0]
    return [sum(matrix[row][column] * vector[column] for column in range(4)) for row in range(3)]


def _representation_transforms(entities: dict[str, StepEntity], scale: float
                               ) -> dict[str, list[tuple[str, list[list[float]], str, bool]]]:
    """Return directed child-representation to parent-representation transforms."""
    identity = [[1., 0., 0., 0.], [0., 1., 0., 0.], [0., 0., 1., 0.], [0., 0., 0., 1.]]
    result: dict[str, list[tuple[str, list[list[float]], str, bool]]] = {}
    for entity in entities.values():
        types = set(entity.complex_types) if entity.entity_type == "COMPLEX_ENTITY" else {entity.entity_type}
        if "SHAPE_REPRESENTATION_RELATIONSHIP" not in types:
            continue
        representations = [ref for ref in entity.references if entities.get(ref) and
                           entities[ref].entity_type in {"SHAPE_REPRESENTATION",
                                                        "ADVANCED_BREP_SHAPE_REPRESENTATION"}]
        if len(representations) < 2:
            continue
        matrix = identity
        transformed = False
        transform_ids = [ref for ref in entity.references if entities.get(ref) and
                         entities[ref].entity_type == "ITEM_DEFINED_TRANSFORMATION"]
        if transform_ids:
            transformed = True
            transform = entities[transform_ids[0]]
            placements = [entities[ref] for ref in transform.references if entities.get(ref) and
                          entities[ref].entity_type == "AXIS2_PLACEMENT_3D"]
            if len(placements) != 2:
                continue
            item_1, item_2 = _frame(placements[0], entities, scale), _frame(placements[1], entities, scale)
            if item_1 is None or item_2 is None:
                continue
            matrix = _multiply(item_2, _rigid_inverse(item_1))
        result.setdefault(representations[0], []).append(
            (representations[1], matrix, entity.entity_id, transformed))
        if not transformed:
            result.setdefault(representations[1], []).append(
                (representations[0], identity, entity.entity_id, False))
    return result


def _body_world_transform(body_id: str, entities: dict[str, StepEntity], scale: float
                          ) -> tuple[list[list[float]] | None, list[str]]:
    representations = [entity.entity_id for entity in entities.values()
                       if entity.entity_type in {"SHAPE_REPRESENTATION", "ADVANCED_BREP_SHAPE_REPRESENTATION"}
                       and body_id in entity.references]
    if not representations:
        return None, []
    edges = _representation_transforms(entities, scale)
    identity = [[1., 0., 0., 0.], [0., 1., 0., 0.], [0., 0., 1., 0.], [0., 0., 0., 1.]]
    queue = [(representations[0], identity, [], False, frozenset())]
    candidates = []
    while queue:
        current, matrix, path, has_transform, visited = queue.pop(0)
        if current in visited:
            continue
        next_visited = visited | {current}
        outgoing = [edge for edge in edges.get(current, []) if edge[0] not in next_visited]
        if not outgoing:
            if has_transform:
                candidates.append((matrix, path))
            continue
        for parent, step, relationship_id, transformed in outgoing:
            queue.append((parent, _multiply(step, matrix), path + [relationship_id],
                          has_transform or transformed, next_visited))
    return min(candidates, key=lambda candidate: len(candidate[1])) if candidates else (None, [])


def _body_product(body_id: str, entities: dict[str, StepEntity]) -> dict[str, Any] | None:
    body_representations = [entity.entity_id for entity in entities.values()
                            if entity.entity_type == "ADVANCED_BREP_SHAPE_REPRESENTATION" and
                            body_id in entity.references]
    related = set(body_representations)
    for relationship in entities.values():
        if relationship.entity_type == "SHAPE_REPRESENTATION_RELATIONSHIP" and any(
                ref in related for ref in relationship.references):
            related.update(ref for ref in relationship.references if entities.get(ref) and
                           entities[ref].entity_type in {"SHAPE_REPRESENTATION",
                                                        "ADVANCED_BREP_SHAPE_REPRESENTATION"})
    for definition in entities.values():
        if definition.entity_type != "SHAPE_DEFINITION_REPRESENTATION" or not any(
                ref in related for ref in definition.references):
            continue
        products = _descendants(definition, entities, "PRODUCT", max_depth=6)
        if products:
            product = products[0]
            name_match = _STRING.search(product.arguments)
            product_definitions = _descendants(definition, entities, "PRODUCT_DEFINITION", max_depth=4)
            occurrence_names = []
            for product_definition in product_definitions:
                for candidate in entities.values():
                    if (candidate.entity_type == "NEXT_ASSEMBLY_USAGE_OCCURRENCE" and
                            product_definition.entity_id in candidate.references):
                        occurrence_match = _STRING.search(candidate.arguments)
                        if occurrence_match:
                            occurrence_names.append(_decode_step_string(occurrence_match.group(1)))
            return {"product_id": product.entity_id,
                    "product_name": _decode_step_string(name_match.group(1)) if name_match else product.entity_id,
                    "occurrence_names": sorted(set(occurrence_names))}
    return None


def inspect_step_brep(path: str | Path) -> dict[str, Any]:
    source = Path(path).resolve()
    if source.suffix.lower() not in {".stp", ".step"}:
        raise ValueError("STEP B-Rep inspection requires a .stp or .step file")
    text = source.read_text(encoding="latin-1")
    entities = _entities(text)
    scale_to_mm = 1.0
    if ".MILLI.,.METRE." not in text and "SI_UNIT($,.METRE.)" in text:
        scale_to_mm = 1000.0
    bodies = []
    for entity in entities.values():
        if entity.entity_type not in {"MANIFOLD_SOLID_BREP", "BREP_WITH_VOIDS",
                                    "SHELL_BASED_SURFACE_MODEL"}:
            continue
        name_match = _STRING.search(entity.arguments)
        name = (_decode_step_string(name_match.group(1)) if name_match else "") or entity.entity_id
        product = _body_product(entity.entity_id, entities)
        shell_refs = [ref for ref in entity.references if entities.get(ref) and
                      entities[ref].entity_type in {"CLOSED_SHELL", "OPEN_SHELL"}]
        face_refs = []
        for shell_ref in shell_refs:
            face_refs.extend(ref for ref in entities[shell_ref].references
                             if entities.get(ref) and entities[ref].entity_type == "ADVANCED_FACE")
        faces = []
        unresolved = []
        for face_ref in face_refs:
            face = entities[face_ref]
            surface_refs = [ref for ref in face.references if entities.get(ref) and
                            (entities[ref].entity_type in _SURFACE_MAP or
                             entities[ref].entity_type.endswith("_SURFACE"))]
            if not surface_refs:
                unresolved.append(face_ref)
                faces.append({"face_id": face_ref, "surface_type": "OTHER"})
                continue
            surface = entities[surface_refs[-1]]
            parameters = _surface_parameters(surface)
            for key in ("radius", "major_radius", "minor_radius"):
                if key in parameters:
                    parameters[key] *= scale_to_mm
            boundary_curves = []
            for circle in _descendants(face, entities, "CIRCLE"):
                circle_parameters = _surface_parameters(StepEntity(
                    circle.entity_id, "CYLINDRICAL_SURFACE", circle.arguments, circle.references))
                radius = circle_parameters.get("radius")
                boundary_curves.append({
                    "curve_id": circle.entity_id, "curve_type": "CIRCLE",
                    "radius_mm": radius * scale_to_mm if radius is not None else None,
                    "placement": _placement(circle, entities, scale_to_mm),
                })
            faces.append({"face_id": face_ref, "surface_id": surface.entity_id,
                          "step_surface_type": surface.entity_type,
                          "surface_type": _SURFACE_MAP.get(surface.entity_type, "OTHER"),
                          "parameters": parameters,
                          "placement": _placement(surface, entities, scale_to_mm),
                          "boundary_curves": boundary_curves})
        closure = ("CLOSED" if shell_refs and all(entities[ref].entity_type == "CLOSED_SHELL"
                                                  for ref in shell_refs) else
                   "OPEN" if shell_refs else "UNKNOWN")
        topology_points = []
        for point in _descendants(entity, entities, "CARTESIAN_POINT", max_depth=12):
            values = _numeric_tuple(point.arguments)
            if len(values) == 3:
                scaled = [value * scale_to_mm for value in values]
                if scaled not in topology_points:
                    topology_points.append(scaled)
        bounds_points = list(topology_points)
        for face in faces:
            placement, parameters = face.get("placement", {}), face.get("parameters", {})
            axis = placement.get("axis_direction")
            if face.get("surface_type") == "CYLINDER" and axis and parameters.get("radius"):
                centers = [curve.get("placement", {}).get("origin_mm")
                           for curve in face.get("boundary_curves", ())]
                centers = [center for center in centers if center]
                if centers:
                    radius = float(parameters["radius"])
                    minimum = [min(center[i] for center in centers) -
                               radius * max(0.0, 1.0 - axis[i] ** 2) ** 0.5 for i in range(3)]
                    maximum = [max(center[i] for center in centers) +
                               radius * max(0.0, 1.0 - axis[i] ** 2) ** 0.5 for i in range(3)]
                    bounds_points.extend([[x, y, z] for x in (minimum[0], maximum[0])
                                          for y in (minimum[1], maximum[1])
                                          for z in (minimum[2], maximum[2])])
            elif face.get("surface_type") == "TORUS" and axis and placement.get("origin_mm"):
                major, minor = parameters.get("major_radius"), parameters.get("minor_radius", 0.0)
                if major:
                    center = placement["origin_mm"]
                    extent = [float(minor) + float(major) * max(0.0, 1.0 - axis[i] ** 2) ** 0.5
                              for i in range(3)]
                    minimum, maximum = ([center[i] - extent[i] for i in range(3)],
                                        [center[i] + extent[i] for i in range(3)])
                    bounds_points.extend([[x, y, z] for x in (minimum[0], maximum[0])
                                          for y in (minimum[1], maximum[1])
                                          for z in (minimum[2], maximum[2])])
        reference_bounds = None
        if bounds_points:
            reference_bounds = [min(point[axis] for point in bounds_points) for axis in range(3)] + [
                max(point[axis] for point in bounds_points) for axis in range(3)]
        world_transform, transform_path = _body_world_transform(entity.entity_id, entities, scale_to_mm)
        world_points = ([_transform_point(world_transform, point) for point in bounds_points]
                        if world_transform else [])
        world_bounds = None
        if world_points:
            world_bounds = [min(point[axis] for point in world_points) for axis in range(3)] + [
                max(point[axis] for point in world_points) for axis in range(3)]
        tube_radii = []
        for face in faces:
            parameters = face.get("parameters", {})
            if face["surface_type"] == "CYLINDER" and parameters.get("radius", 0) > 0:
                tube_radii.append(float(parameters["radius"]))
            elif face["surface_type"] == "TORUS" and parameters.get("minor_radius", 0) > 0:
                tube_radii.append(float(parameters["minor_radius"]))
        radius_clusters = _radius_clusters(tube_radii)
        dominant_cluster = radius_clusters[0] if radius_clusters else None
        dominant_radius = dominant_cluster["radius"] if dominant_cluster else None
        diameter_variation = dominant_cluster["relative_variation"] if dominant_cluster else None
        statistics_result = summarize_surfaces(faces)
        tubular_face_ratio = ((statistics_result["surface_type_counts"]["CYLINDER"] +
                               statistics_result["surface_type_counts"]["TORUS"]) /
                              statistics_result["face_count"] if statistics_result["face_count"] else None)
        tube_axes = [face["placement"]["axis_direction"] for face in faces
                     if face["surface_type"] in {"CYLINDER", "TORUS"} and
                     face.get("placement", {}).get("axis_direction")]
        bodies.append({
            "source_id": entity.entity_id, "source_name": name,
            "product_id": product.get("product_id") if product else None,
            "product_name": product.get("product_name") if product else None,
            "occurrence_names": product.get("occurrence_names", []) if product else [],
            "step_entity_type": entity.entity_type, "geometry_kind": "SOLID" if closure == "CLOSED" else "SHELL",
            "closure_state": closure, "geometry_state": "AVAILABLE" if face_refs else "UNAVAILABLE",
            "shell_ids": shell_refs, "face_ids": face_refs, "faces": faces,
            "surface_statistics": statistics_result,
            "topology_reference_points_mm": topology_points,
            "reference_bounds_mm": world_bounds or reference_bounds,
            "reference_bounds_quality": "TOPOLOGY_POINTS_PLUS_ANALYTIC_SURFACE_EXTREMA",
            "reference_bounds_coordinate_space": ("WORLD" if world_bounds else
                                                  "LOCAL_STEP_REPRESENTATION"),
            "assembly_transform": ({"matrix": world_transform, "relationship_path": transform_path}
                                   if world_transform else None),
            "tubular_features": {
                "radius_samples": tube_radii,
                "radius_clusters": radius_clusters,
                "dominant_radius": dominant_radius,
                "dominant_diameter": dominant_radius * 2.0 if dominant_radius else None,
                "diameter_variation": diameter_variation,
                "tubular_surface_ratio": tubular_face_ratio,
                "ratio_basis": "FACE_COUNT_PROXY",
                "dominant_radius_support": (dominant_cluster["sample_count"] / len(tube_radii)
                                            if dominant_cluster and tube_radii else None),
                "axis_directions": tube_axes,
                "axis_consistency": _axis_consistency(tube_axes),
            },
            "limitations": (["STEP face areas are not calculated by the text topology adapter"] +
                            (["Reference bounds are local STEP representation coordinates and cannot be used "
                              "for assembly spatial filtering until transforms are resolved",
                              "Reference bounds may omit curved extrema and are for spatial filtering only"]
                             if reference_bounds and not world_bounds else
                             (["World reference bounds may omit curved extrema and are for spatial filtering only"]
                              if world_bounds else [])) +
                            ([f"{len(unresolved)} faces have no resolved surface reference"] if unresolved else [])),
        })
    return {
        "schema_version": "step-brep.v0.1", "source_file": str(source),
        "unit_scale_to_mm": scale_to_mm,
        "entity_count": len(entities), "body_count": len(bodies), "bodies": bodies,
        "limitations": [
            "The adapter follows STEP topology references but does not reconstruct native CAD features",
            "Surface counts are deterministic; areas and geometric tolerances require a CAD kernel",
        ],
    }
