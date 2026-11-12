"""Read-only geometry helpers for native CATIA Arrangement Runs."""

from __future__ import annotations

import math
import os
import struct
import tempfile
from typing import Any

import pythoncom

Point = tuple[float, float, float]


def arrangement_product(root: Any) -> Any:
    for token in ("CATIAArrangementProduct", "ArrangementProduct"):
        try:
            value = root.GetTechnologicalObject(token)
            if value is not None:
                return value
        except Exception:
            continue
    raise RuntimeError("Active CATProduct does not expose an Arrangement Product")


def resolve_run(arrangement: Any, exact_name: str) -> Any:
    matches = []
    runs = arrangement.ArrangementRuns
    for index in range(1, runs.Count + 1):
        run = runs.Item(index)
        try:
            if run.Name == exact_name:
                matches.append(run)
        except Exception:
            continue
    if not matches:
        raise ValueError(f"No Arrangement Run named '{exact_name}'")
    if len(matches) > 1:
        raise ValueError(f"Arrangement Run name '{exact_name}' is ambiguous")
    return matches[0]


def node_point(node: Any, root: Any) -> Point:
    """Read GetPoint with its exact [in,out] SAFEARRAY(VARIANT) signature."""
    value = node._oleobj_.InvokeTypes(
        1610940419,
        0,
        pythoncom.DISPATCH_METHOD,
        (pythoncom.VT_EMPTY, 0),
        (
            (pythoncom.VT_DISPATCH, 1),
            (pythoncom.VT_BYREF | pythoncom.VT_ARRAY | pythoncom.VT_VARIANT, 3),
        ),
        root._oleobj_,
        (0.0, 0.0, 0.0),
    )
    if not isinstance(value, (tuple, list)) or len(value) != 3:
        raise RuntimeError("CATIA GetPoint returned an invalid coordinate array")
    point = tuple(float(component) for component in value)
    if not all(math.isfinite(component) for component in point):
        raise RuntimeError("CATIA GetPoint returned non-finite coordinates")
    return point  # type: ignore[return-value]


def add(a: Point, b: Point) -> Point:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def sub(a: Point, b: Point) -> Point:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def scale(a: Point, factor: float) -> Point:
    return (a[0] * factor, a[1] * factor, a[2] * factor)


def dot(a: Point, b: Point) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def norm(a: Point) -> float:
    return math.sqrt(dot(a, a))


def unit(a: Point) -> Point:
    length = norm(a)
    if length <= 1e-12:
        raise ValueError("Arrangement Run contains coincident route nodes")
    return scale(a, 1.0 / length)


def run_polyline(run: Any, root: Any, chord_tolerance: float) -> tuple[list[Point], float, int]:
    """Return a centerline polyline whose bend sagitta is bounded by tolerance."""
    if not math.isfinite(chord_tolerance) or chord_tolerance <= 0:
        raise ValueError("chord_tolerance must be positive")
    diameter = float(run.SectionDiameter)
    if not math.isfinite(diameter) or diameter <= 0:
        raise ValueError(f"Arrangement Run '{run.Name}' has no positive round section diameter")
    nodes = run.ArrangementNodes
    points = [node_point(nodes.Item(i), root) for i in range(1, nodes.Count + 1)]
    if len(points) < 2:
        raise ValueError(f"Arrangement Run '{run.Name}' has fewer than two nodes")

    output = [points[0]]
    arc_segment_count = 0
    for index in range(1, len(points) - 1):
        previous, vertex, following = points[index - 1], points[index], points[index + 1]
        radius = float(nodes.Item(index + 1).BendRadius)
        if radius <= 1e-9:
            output.append(vertex)
            continue
        toward_previous = unit(sub(previous, vertex))
        toward_following = unit(sub(following, vertex))
        angle = math.acos(max(-1.0, min(1.0, dot(toward_previous, toward_following))))
        if angle <= 1e-8 or abs(math.pi - angle) <= 1e-8:
            output.append(vertex)
            continue
        tangent_distance = radius / math.tan(angle / 2.0)
        if tangent_distance > min(norm(sub(previous, vertex)), norm(sub(following, vertex))) + 1e-6:
            raise ValueError(f"Arrangement Run '{run.Name}' bend radius does not fit adjacent segments")
        tangent1 = add(vertex, scale(toward_previous, tangent_distance))
        tangent2 = add(vertex, scale(toward_following, tangent_distance))
        bisector = unit(add(toward_previous, toward_following))
        center = add(vertex, scale(bisector, radius / math.sin(angle / 2.0)))
        radial1, radial2 = sub(tangent1, center), sub(tangent2, center)
        arc_angle = math.acos(max(-1.0, min(1.0, dot(radial1, radial2) / (radius * radius))))
        max_step = 2.0 * math.acos(max(-1.0, 1.0 - chord_tolerance / radius))
        subdivisions = max(1, math.ceil(arc_angle / max_step))
        output.append(tangent1)
        sine = math.sin(arc_angle)
        for step in range(1, subdivisions):
            fraction = step / subdivisions
            radial = add(
                scale(radial1, math.sin((1.0 - fraction) * arc_angle) / sine),
                scale(radial2, math.sin(fraction * arc_angle) / sine),
            )
            output.append(add(center, radial))
        output.append(tangent2)
        arc_segment_count += subdivisions
    output.append(points[-1])
    return output, diameter, arc_segment_count


def segment_distance(p1: Point, q1: Point, p2: Point, q2: Point) -> tuple[float, Point, Point]:
    epsilon = 1e-12
    d1, d2, r = sub(q1, p1), sub(q2, p2), sub(p1, p2)
    a, e, f = dot(d1, d1), dot(d2, d2), dot(d2, r)
    if a <= epsilon and e <= epsilon:
        return norm(r), p1, p2
    if a <= epsilon:
        s, t = 0.0, max(0.0, min(1.0, f / e))
    else:
        c = dot(d1, r)
        if e <= epsilon:
            t, s = 0.0, max(0.0, min(1.0, -c / a))
        else:
            b = dot(d1, d2)
            denominator = a * e - b * b
            s = max(0.0, min(1.0, (b * f - c * e) / denominator)) if denominator else 0.0
            t = (b * s + f) / e
            if t < 0.0:
                t, s = 0.0, max(0.0, min(1.0, -c / a))
            elif t > 1.0:
                t, s = 1.0, max(0.0, min(1.0, (b - c) / a))
    closest1, closest2 = add(p1, scale(d1, s)), add(p2, scale(d2, t))
    return norm(sub(closest1, closest2)), closest1, closest2


def polyline_distance(first: list[Point], second: list[Point]) -> tuple[float, Point, Point]:
    best = (math.inf, first[0], second[0])
    for start1, end1 in zip(first, first[1:]):
        for start2, end2 in zip(second, second[1:]):
            candidate = segment_distance(start1, end1, start2, end2)
            if candidate[0] < best[0]:
                best = candidate
    return best


def _parse_stl(path: str) -> tuple[list[Point], list[tuple[int, int, int]]]:
    with open(path, "rb") as stream:
        data = stream.read()
    raw: list[list[Point]] = []
    binary = False
    count = 0
    if len(data) >= 84:
        count = struct.unpack_from("<I", data, 80)[0]
        binary = len(data) == 84 + count * 50
    if binary:
        offset = 84
        for _ in range(count):
            offset += 12
            triangle = []
            for _ in range(3):
                triangle.append(tuple(float(v) for v in struct.unpack_from("<fff", data, offset)))
                offset += 12
            raw.append(triangle)  # type: ignore[arg-type]
            offset += 2
    else:
        current: list[Point] = []
        for line in data.decode("ascii", errors="ignore").splitlines():
            fields = line.strip().split()
            if len(fields) == 4 and fields[0].lower() == "vertex":
                current.append((float(fields[1]), float(fields[2]), float(fields[3])))
                if len(current) == 3:
                    raw.append(current)
                    current = []
    vertices: list[Point] = []
    lookup: dict[Point, int] = {}
    triangles = []
    for triangle in raw:
        indices = []
        for point in triangle:
            key = tuple(round(value, 6) for value in point)
            if key not in lookup:
                lookup[key] = len(vertices)
                vertices.append(key)  # type: ignore[arg-type]
            indices.append(lookup[key])
        triangles.append(tuple(indices))
    if not triangles:
        raise RuntimeError("Temporary CATPart STL export contains no triangles")
    return vertices, triangles


def component_mesh(app: Any, product_doc: Any, root: Any, exact_name: str) -> tuple[list[Point], list[tuple[int, int, int]], list[float]]:
    """Tessellate one exact top-level CATPart component without changing source data."""
    matches = []
    for index in range(1, root.Products.Count + 1):
        component = root.Products.Item(index)
        if component.Name == exact_name:
            matches.append(component)
    if not matches:
        raise ValueError(f"No top-level component named '{exact_name}'")
    if len(matches) > 1:
        raise ValueError(f"Component name '{exact_name}' is ambiguous")
    component = matches[0]
    try:
        source_doc = component.ReferenceProduct.Parent
        source_part = source_doc.Part
    except Exception as exc:
        raise ValueError(f"Component '{exact_name}' does not reference a CATPart") from exc

    values = list(component.Position._oleobj_.InvokeTypes(
        1611005953,  # CATIAMove.GetComponents
        0,
        pythoncom.DISPATCH_METHOD,
        (pythoncom.VT_EMPTY, 0),
        ((pythoncom.VT_BYREF | pythoncom.VT_ARRAY | pythoncom.VT_VARIANT, 3),),
        tuple(0.0 for _ in range(12)),
    ))
    if len(values) != 12:
        raise RuntimeError(f"Component '{exact_name}' returned an invalid position matrix")

    # CATIA rejects Selection.Copy for embedded/never-saved component documents
    # and opens a modal "Copy data error" dialog.  Refuse that code path before
    # touching the clipboard so headless checks remain non-blocking.
    source_path = str(getattr(source_doc, "FullName", "") or "")
    if not os.path.isabs(source_path) or not os.path.exists(source_path):
        raise RuntimeError(
            f"Component '{exact_name}' references an unsaved CATPart; "
            "clipboard tessellation is disabled to prevent CATIA modal dialogs"
        )

    temporary_doc = None
    fd, path = tempfile.mkstemp(suffix=".stl", prefix="catia_component_")
    os.close(fd)
    os.unlink(path)
    try:
        product_doc.Activate()
        source_selection = product_doc.Selection
        source_selection.Clear()
        for index in range(1, source_part.Bodies.Count + 1):
            source_selection.Add(source_part.Bodies.Item(index))
        if source_selection.Count == 0:
            raise ValueError(f"Component '{exact_name}' contains no solid Body")
        source_selection.Copy()
        source_selection.Clear()

        temporary_doc = app.Documents.Add("Part")
        target_part = temporary_doc.Part
        target_selection = temporary_doc.Selection
        target_selection.Clear()
        target_selection.Add(target_part.MainBody)
        target_selection.PasteSpecial("CATPrtResultWithOutLink")
        target_selection.Clear()
        target_part.Update()
        temporary_doc.ExportData(path, "stl")
        vertices, triangles = _parse_stl(path)
    finally:
        if os.path.exists(path):
            os.unlink(path)
        if temporary_doc is not None:
            temporary_doc.Close()
        product_doc.Activate()

    x_axis, y_axis, z_axis, origin = values[0:3], values[3:6], values[6:9], values[9:12]
    transformed = [
        (
            origin[0] + x_axis[0] * p[0] + y_axis[0] * p[1] + z_axis[0] * p[2],
            origin[1] + x_axis[1] * p[0] + y_axis[1] * p[1] + z_axis[1] * p[2],
            origin[2] + x_axis[2] * p[0] + y_axis[2] * p[1] + z_axis[2] * p[2],
        )
        for p in vertices
    ]
    return transformed, triangles, [float(value) for value in values]


def closest_point_triangle(point: Point, a: Point, b: Point, c: Point) -> Point:
    ab, ac, ap = sub(b, a), sub(c, a), sub(point, a)
    d1, d2 = dot(ab, ap), dot(ac, ap)
    if d1 <= 0 and d2 <= 0:
        return a
    bp = sub(point, b)
    d3, d4 = dot(ab, bp), dot(ac, bp)
    if d3 >= 0 and d4 <= d3:
        return b
    vc = d1 * d4 - d3 * d2
    if vc <= 0 and d1 >= 0 and d3 <= 0:
        return add(a, scale(ab, d1 / (d1 - d3)))
    cp = sub(point, c)
    d5, d6 = dot(ab, cp), dot(ac, cp)
    if d6 >= 0 and d5 <= d6:
        return c
    vb = d5 * d2 - d1 * d6
    if vb <= 0 and d2 >= 0 and d6 <= 0:
        return add(a, scale(ac, d2 / (d2 - d6)))
    va = d3 * d6 - d5 * d4
    if va <= 0 and (d4 - d3) >= 0 and (d5 - d6) >= 0:
        return add(b, scale(sub(c, b), (d4 - d3) / ((d4 - d3) + (d5 - d6))))
    denominator = 1.0 / (va + vb + vc)
    return add(a, add(scale(ab, vb * denominator), scale(ac, vc * denominator)))


def segment_triangle_intersection(p: Point, q: Point, a: Point, b: Point, c: Point) -> Point | None:
    direction, edge1, edge2 = sub(q, p), sub(b, a), sub(c, a)
    cross_value = (
        direction[1] * edge2[2] - direction[2] * edge2[1],
        direction[2] * edge2[0] - direction[0] * edge2[2],
        direction[0] * edge2[1] - direction[1] * edge2[0],
    )
    determinant = dot(edge1, cross_value)
    if abs(determinant) <= 1e-12:
        return None
    inverse = 1.0 / determinant
    offset = sub(p, a)
    u = inverse * dot(offset, cross_value)
    if u < 0 or u > 1:
        return None
    qvec = (
        offset[1] * edge1[2] - offset[2] * edge1[1],
        offset[2] * edge1[0] - offset[0] * edge1[2],
        offset[0] * edge1[1] - offset[1] * edge1[0],
    )
    v = inverse * dot(direction, qvec)
    if v < 0 or u + v > 1:
        return None
    t = inverse * dot(edge2, qvec)
    return add(p, scale(direction, t)) if 0 <= t <= 1 else None


def segment_triangle_distance(p: Point, q: Point, a: Point, b: Point, c: Point) -> tuple[float, Point, Point]:
    intersection = segment_triangle_intersection(p, q, a, b, c)
    if intersection is not None:
        return 0.0, intersection, intersection
    candidates = []
    for point in (p, q):
        on_triangle = closest_point_triangle(point, a, b, c)
        candidates.append((norm(sub(point, on_triangle)), point, on_triangle))
    for first, second in ((a, b), (b, c), (c, a)):
        candidates.append(segment_distance(p, q, first, second))
    return min(candidates, key=lambda item: item[0])


def polyline_mesh_distance(polyline: list[Point], vertices: list[Point], triangles: list[tuple[int, int, int]]) -> tuple[float, Point, Point]:
    best = (math.inf, polyline[0], vertices[0])
    for start, end in zip(polyline, polyline[1:]):
        for ia, ib, ic in triangles:
            candidate = segment_triangle_distance(start, end, vertices[ia], vertices[ib], vertices[ic])
            if candidate[0] < best[0]:
                best = candidate
                if best[0] <= 1e-9:
                    return best
    return best


def mesh_bounds(vertices: list[Point]) -> list[float]:
    if not vertices:
        raise ValueError("Mesh contains no vertices")
    return [min(point[axis] for point in vertices) for axis in range(3)] + [
        max(point[axis] for point in vertices) for axis in range(3)
    ]


def _triangle_bounds(a: Point, b: Point, c: Point) -> tuple[float, ...]:
    return (
        min(a[0], b[0], c[0]), min(a[1], b[1], c[1]), min(a[2], b[2], c[2]),
        max(a[0], b[0], c[0]), max(a[1], b[1], c[1]), max(a[2], b[2], c[2]),
    )


def _bounds_separation(first: tuple[float, ...] | list[float], second: tuple[float, ...] | list[float]) -> float:
    squared = 0.0
    for axis in range(3):
        gap = max(first[axis] - second[axis + 3], second[axis] - first[axis + 3], 0.0)
        squared += gap * gap
    return math.sqrt(squared)


def triangle_triangle_distance(
    first: tuple[Point, Point, Point], second: tuple[Point, Point, Point],
) -> tuple[float, Point, Point]:
    """Return the exact Euclidean distance between two closed triangles."""
    best = (math.inf, first[0], second[0])
    for start, end in ((first[0], first[1]), (first[1], first[2]), (first[2], first[0])):
        candidate = segment_triangle_distance(start, end, *second)
        if candidate[0] < best[0]:
            best = candidate
            if best[0] <= 1e-9:
                return best
    for start, end in ((second[0], second[1]), (second[1], second[2]), (second[2], second[0])):
        distance, point2, point1 = segment_triangle_distance(start, end, *first)
        if distance < best[0]:
            best = (distance, point1, point2)
            if best[0] <= 1e-9:
                return best
    return best


def _point_on_mesh(point: Point, vertices: list[Point], triangles: list[tuple[int, int, int]], tolerance: float) -> bool:
    for ia, ib, ic in triangles:
        closest = closest_point_triangle(point, vertices[ia], vertices[ib], vertices[ic])
        if norm(sub(point, closest)) <= tolerance:
            return True
    return False


def point_inside_mesh(point: Point, vertices: list[Point], triangles: list[tuple[int, int, int]]) -> bool:
    """Odd/even ray test for a closed triangulated solid, with a non-axis-aligned ray."""
    if _point_on_mesh(point, vertices, triangles, 1e-7):
        return False
    direction = unit((1.0, 0.3713906763541037, 0.6948475392211846))
    bounds = mesh_bounds(vertices)
    extent = norm((bounds[3] - bounds[0], bounds[4] - bounds[1], bounds[5] - bounds[2]))
    end = add(point, scale(direction, max(1.0, extent * 3.0)))
    hits: list[Point] = []
    for ia, ib, ic in triangles:
        hit = segment_triangle_intersection(point, end, vertices[ia], vertices[ib], vertices[ic])
        if hit is not None and all(norm(sub(hit, prior)) > 1e-6 for prior in hits):
            hits.append(hit)
    return len(hits) % 2 == 1


def mesh_interference(
    vertices1: list[Point], triangles1: list[tuple[int, int, int]],
    vertices2: list[Point], triangles2: list[tuple[int, int, int]],
    contact_tolerance: float, *, closed1: bool = True, closed2: bool = True,
) -> dict[str, Any]:
    """Classify CATIA-derived meshes without treating open sheets as volumes."""
    if not math.isfinite(contact_tolerance) or contact_tolerance < 0:
        raise ValueError("contact_tolerance must be non-negative")
    bounds1, bounds2 = mesh_bounds(vertices1), mesh_bounds(vertices2)
    best = (math.inf, vertices1[0], vertices2[0])
    intersections: list[Point] = []
    triangle_data2 = [
        ((vertices2[a], vertices2[b], vertices2[c]), _triangle_bounds(vertices2[a], vertices2[b], vertices2[c]))
        for a, b, c in triangles2
    ]
    for ia, ib, ic in triangles1:
        first = (vertices1[ia], vertices1[ib], vertices1[ic])
        first_bounds = _triangle_bounds(*first)
        for second, second_bounds in triangle_data2:
            lower_bound = _bounds_separation(first_bounds, second_bounds)
            if lower_bound > best[0]:
                continue
            candidate = triangle_triangle_distance(first, second)
            if candidate[0] < best[0]:
                best = candidate
            if candidate[0] <= 1e-7 and all(norm(sub(candidate[1], p)) > 1e-5 for p in intersections):
                intersections.append(candidate[1])

    contained1 = bool(closed1 and closed2 and not intersections and
                      point_inside_mesh(vertices1[0], vertices2, triangles2))
    contained2 = bool(closed1 and closed2 and not intersections and
                      point_inside_mesh(vertices2[0], vertices1, triangles1))
    bounds_overlap = [
        max(0.0, min(bounds1[axis + 3], bounds2[axis + 3]) - max(bounds1[axis], bounds2[axis]))
        for axis in range(3)
    ]
    interference = bool(intersections or contained1 or contained2)
    state = "INTERFERENCE" if interference else ("CONTACT" if best[0] <= contact_tolerance else "CLEARANCE")
    return {
        "state": state,
        "minimum_surface_distance_mm": 0.0 if interference else best[0],
        "closest_point1_mm": best[1],
        "closest_point2_mm": best[2],
        "intersection_points_mm": intersections,
        "contained_component": 1 if contained1 else 2 if contained2 else None,
        "mesh_closed": [closed1, closed2],
        "bounding_box_overlap_mm": bounds_overlap,
        "bounds1_mm": bounds1,
        "bounds2_mm": bounds2,
    }
