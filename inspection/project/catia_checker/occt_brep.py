"""Exact Open CASCADE B-Rep backend for STEP geometry inspection."""

from __future__ import annotations

from pathlib import Path
import math
import re
from typing import Any, Callable
from time import perf_counter

try:
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Common, BRepAlgoAPI_Section
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.BRep import BRep_Tool, BRep_Builder
    from OCP.BRepTools import BRepTools
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.BRepClass import BRepClass_FaceClassifier
    from OCP.BRepLProp import BRepLProp_SLProps
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepClass3d import BRepClass3d_SolidClassifier
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape
    from OCP.BRepGProp import BRepGProp
    from OCP.BRepBndLib import BRepBndLib
    from OCP.Bnd import Bnd_Box
    from OCP.GProp import GProp_GProps
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.IGESControl import IGESControl_Reader
    from OCP.STEPControl import STEPControl_Reader
    from OCP.TopAbs import (TopAbs_EDGE, TopAbs_FACE, TopAbs_IN, TopAbs_ON,
                            TopAbs_SOLID, TopAbs_SHELL, TopAbs_VERTEX, TopAbs_WIRE)
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopTools import TopTools_IndexedMapOfShape
    from OCP.TopoDS import TopoDS, TopoDS_Shape
    from OCP.GeomAPI import GeomAPI_ProjectPointOnSurf
    from OCP.gp import gp_Lin, gp_Pnt
    from OCP.GeomAbs import (GeomAbs_BSplineSurface, GeomAbs_BezierSurface, GeomAbs_Circle,
                             GeomAbs_Cone, GeomAbs_Cylinder, GeomAbs_OffsetSurface,
                             GeomAbs_OtherSurface, GeomAbs_Plane, GeomAbs_Sphere,
                             GeomAbs_Torus)
except ImportError:  # pragma: no cover - exercised by deployment preflight
    BRepAlgoAPI_Common = None


def backend_status() -> dict[str, Any]:
    return {"available": BRepAlgoAPI_Common is not None, "backend": "OCCT_BREP",
            "required_module": "cadquery-ocp", "fallback_to_mesh": False}


def _count(shape: Any, kind: Any) -> int:
    explorer, count = TopExp_Explorer(shape, kind), 0
    while explorer.More():
        count += 1
        explorer.Next()
    return count


def _subshapes(shape: Any, kind: Any) -> list[Any]:
    explorer, result = TopExp_Explorer(shape, kind), []
    while explorer.More():
        result.append(explorer.Current())
        explorer.Next()
    return result

def independent_geometry(root: Any) -> list[tuple[str, Any]]:
    """Keep free shells/faces in mixed files, without duplicating solid faces."""
    solids=_subshapes(root,TopAbs_SOLID)
    owned_shells=TopTools_IndexedMapOfShape()
    for solid in solids:
        for item in _subshapes(solid,TopAbs_SHELL): owned_shells.Add(item)
    shells=[x for x in _subshapes(root,TopAbs_SHELL) if not owned_shells.Contains(x)]
    owned_faces=TopTools_IndexedMapOfShape()
    for parent in [*solids,*shells]:
        for item in _subshapes(parent,TopAbs_FACE): owned_faces.Add(item)
    faces=[x for x in _subshapes(root,TopAbs_FACE) if not owned_faces.Contains(x)]
    result=[]
    for kind,items in [('SOLID',solids),('SHELL',shells),('FACE',faces)]:
        unique=[]; seen=TopTools_IndexedMapOfShape()
        for item in items:
            if not seen.Contains(item): unique.append(item);seen.Add(item)
        result.extend((kind,item) for item in unique)
    return result


def _decode_step_text(value: str) -> str:
    """Decode the common STEP ``\\X2\\UTF16HEX\\X0\\`` string form."""
    def replace(match: re.Match[str]) -> str:
        try:
            return bytes.fromhex(match.group(1)).decode("utf-16-be")
        except (ValueError, UnicodeDecodeError):
            return match.group(0)
    return re.sub(r"\\X2\\([0-9A-Fa-f]+)\\X0\\", replace, value).replace("''", "'")


def _step_solid_names(path: Path) -> list[str | None]:
    """Read ordered MANIFOLD_SOLID_BREP labels without changing geometry."""
    text = path.read_text(encoding="latin-1", errors="replace")
    names = re.findall(r"MANIFOLD_SOLID_BREP\('((?:''|[^'])*)'\s*,", text, re.IGNORECASE)
    return [(_decode_step_text(item).strip() or None) for item in names]


def _bounds(shape: Any) -> dict[str, list[float]] | None:
    box = Bnd_Box()
    BRepBndLib.Add_s(shape, box, False)
    if box.IsVoid():
        return None
    xmin, ymin, zmin, xmax, ymax, zmax = box.Get()
    return {"min": [xmin, ymin, zmin], "max": [xmax, ymax, zmax]}


def _mass_properties(shape: Any) -> dict[str, Any]:
    volume_props, area_props = GProp_GProps(), GProp_GProps()
    # Open boundaries have a signed volume moment, but no material volume.
    # A mixed compound's free faces must not affect its solid mass or centroid.
    for solid in _subshapes(shape, TopAbs_SOLID):
        solid_props = GProp_GProps()
        BRepGProp.VolumeProperties_s(solid, solid_props)
        volume_props.Add(solid_props)
    BRepGProp.SurfaceProperties_s(shape, area_props)
    center = volume_props.CentreOfMass() if volume_props.Mass() > 0 else area_props.CentreOfMass()
    return {"volume_mm3": max(0.0, float(volume_props.Mass())),
            "surface_area_mm2": max(0.0, float(area_props.Mass())),
            "centroid_mm": [center.X(), center.Y(), center.Z()]}


def _face_normal(face: Any, point: Any) -> list[float] | None:
    geometric_surface = BRep_Tool.Surface_s(face)
    projection = GeomAPI_ProjectPointOnSurf(point, geometric_surface)
    if not projection.IsDone() or projection.NbPoints() < 1:
        return None
    u, v = projection.LowerDistanceParameters()
    properties = BRepLProp_SLProps(BRepAdaptor_Surface(face), u, v, 1, 1e-9)
    if not properties.IsNormalDefined():
        return None
    normal = properties.Normal()
    return [normal.X(), normal.Y(), normal.Z()]


def _face_features(shape: Any) -> dict[str, Any] | None:
    faces = _subshapes(shape, TopAbs_FACE)
    if len(faces) != 1:
        return None
    face = TopoDS.Face_s(faces[0])
    adaptor = BRepAdaptor_Surface(face)
    kind = adaptor.GetType()
    names = {GeomAbs_Plane: "PLANE", GeomAbs_Cylinder: "CYLINDER",
             GeomAbs_Cone: "CONE", GeomAbs_Sphere: "SPHERE", GeomAbs_Torus: "TORUS",
             GeomAbs_BezierSurface: "BEZIER", GeomAbs_BSplineSurface: "BSPLINE",
             GeomAbs_OffsetSurface: "OFFSET", GeomAbs_OtherSurface: "OTHER"}
    properties = GProp_GProps()
    BRepGProp.SurfaceProperties_s(face, properties)
    center = properties.CentreOfMass()
    result: dict[str, Any] = {"surface_type": names.get(kind, "OTHER"),
                              "underlying_surface_type": BRep_Tool.Surface_s(face).DynamicType().Name(),
                              "area_mm2": max(0.0, float(properties.Mass())),
                              "centroid_mm": [center.X(), center.Y(), center.Z()]}
    if kind == GeomAbs_Plane:
        plane = adaptor.Plane()
        plane_axis = plane.Axis()
        direction = plane_axis.Direction()
        location = plane.Location()
        result["plane_origin_mm"] = [location.X(), location.Y(), location.Z()]
        result["normal"] = [direction.X(), direction.Y(), direction.Z()]
        outer_wire = BRepTools.OuterWire_s(face)
        circular_inner_boundaries = []
        for wire_shape in _subshapes(face, TopAbs_WIRE):
            wire = TopoDS.Wire_s(wire_shape)
            if not outer_wire.IsNull() and wire.IsSame(outer_wire):
                continue
            edges = _subshapes(wire, TopAbs_EDGE)
            if not edges or not wire.Closed():
                continue
            curves = [BRepAdaptor_Curve(TopoDS.Edge_s(edge)) for edge in edges]
            if any(curve.GetType() != GeomAbs_Circle for curve in curves):
                continue
            circle = curves[0].Circle()
            if any(abs(curve.Circle().Radius()-circle.Radius()) > 1e-7 or
                   curve.Circle().Location().Distance(circle.Location()) > 1e-7 or
                   abs(abs(curve.Circle().Axis().Direction().Dot(circle.Axis().Direction()))-1) > 1e-8
                   for curve in curves):
                continue
            span = sum(abs(curve.LastParameter()-curve.FirstParameter()) for curve in curves)
            if not math.isclose(span,2*math.pi,rel_tol=1e-7,abs_tol=1e-7):
                continue
            location = circle.Location()
            axis_direction = circle.Axis().Direction()
            circular_inner_boundaries.append({
                "boundary_id": f"INNER_CIRCLE_{len(circular_inner_boundaries) + 1:03d}",
                "center_mm": [location.X(), location.Y(), location.Z()],
                "normal": [axis_direction.X(), axis_direction.Y(), axis_direction.Z()],
                "radius_mm": circle.Radius(), "closed": bool(wire.Closed()),
                "exact_brep": True, "edge_count": len(edges),
            })
        result["circular_inner_boundaries"] = circular_inner_boundaries
        result["host_discontinuity_confirmed"] = bool(circular_inner_boundaries)
    primitive = None
    if kind == GeomAbs_Cylinder:
        value = adaptor.Cylinder()
        primitive = (value.Axis(), {"radius_mm": value.Radius()})
    elif kind == GeomAbs_Torus:
        value = adaptor.Torus()
        primitive = (value.Axis(), {"major_radius_mm": value.MajorRadius(),
                                    "minor_radius_mm": value.MinorRadius()})
    elif kind == GeomAbs_Cone:
        value = adaptor.Cone()
        primitive = (value.Axis(), {"reference_radius_mm": value.RefRadius(),
                                    "semi_angle_rad": value.SemiAngle()})
    elif result["underlying_surface_type"] == "Geom_SurfaceOfRevolution":
        revolution = BRep_Tool.Surface_s(face)
        basis = revolution.BasisCurve()
        while basis.DynamicType().Name() == "Geom_TrimmedCurve":
            basis = basis.BasisCurve()
        axis = revolution.Axis()
        axis_line = gp_Lin(axis)
        basis_type = basis.DynamicType().Name()
        result["revolution_basis_curve_type"] = basis_type
        if basis_type == "Geom_Line":
            generator = basis.Lin()
            alignment = abs(axis.Direction().Dot(generator.Direction()))
            result["axis_generator_alignment"] = alignment
            if alignment >= math.cos(math.radians(0.1)):
                result["surface_type"] = "CYLINDER"
                primitive = (axis, {"radius_mm": axis_line.Distance(generator)})
                result["recognition_source"] = "REVOLUTION_OF_PARALLEL_LINE"
        elif basis_type == "Geom_Circle":
            minor_radius = float(basis.Radius())
            major_radius = float(axis_line.Distance(basis.Location()))
            if major_radius > minor_radius + 1e-7:
                result["surface_type"] = "TORUS"
                primitive = (axis, {"major_radius_mm": major_radius,
                                    "minor_radius_mm": minor_radius})
                result["recognition_source"] = "REVOLUTION_OF_OFFSET_CIRCLE"
            elif major_radius <= 1e-7:
                result["surface_type"] = "SPHERE"
                result["radius_mm"] = minor_radius
                result["recognition_source"] = "REVOLUTION_OF_AXIS_CENTERED_CIRCLE"
    if primitive:
        axis, dimensions = primitive
        origin, direction = axis.Location(), axis.Direction()
        result.update(dimensions)
        result["axis_origin_mm"] = [origin.X(), origin.Y(), origin.Z()]
        result["axis_direction"] = [direction.X(), direction.Y(), direction.Z()]
    return result


def sweep_and_prune_pairs(shapes: list[dict[str, Any]], *, margin_mm: float = 1e-5) -> dict[str, Any]:
    """Build spatially plausible pairs without enumerating every possible pair."""
    margin = max(0.0, float(margin_mm))
    bounded = [item for item in shapes if isinstance(item.get("bounds_mm"), dict)]
    ordered = sorted(bounded, key=lambda item: item["bounds_mm"]["min"][0])
    active: list[dict[str, Any]] = []
    pairs: list[tuple[str, str]] = []
    for current in ordered:
        cmin, cmax = current["bounds_mm"]["min"], current["bounds_mm"]["max"]
        active = [item for item in active
                  if item["bounds_mm"]["max"][0] + margin >= cmin[0]]
        for other in active:
            omin, omax = other["bounds_mm"]["min"], other["bounds_mm"]["max"]
            if (omax[1] + margin >= cmin[1] and cmax[1] + margin >= omin[1] and
                    omax[2] + margin >= cmin[2] and cmax[2] + margin >= omin[2]):
                pairs.append((other["shape_id"], current["shape_id"]))
        active.append(current)
    return {"method": "AABB_SWEEP_AND_PRUNE", "margin_mm": margin,
            "shape_count": len(bounded),
            "total_possible_pairs": len(bounded) * (len(bounded) - 1) // 2,
            "candidate_pair_count": len(pairs), "pairs": pairs,
            "mesh_used": False}


class OCCTBRepModel:
    """In-memory exact shape registry; TopoDS objects never enter JSON reports."""

    def __init__(self) -> None:
        if BRepAlgoAPI_Common is None:
            raise RuntimeError("OCCT B-Rep backend is unavailable; mesh fallback is disabled")
        self._shapes: dict[str, Any] = {}
        self._shape_names: dict[str, str] = {}
        self.source_file: str | None = None

    def register_shape(self, shape_id: str, shape: Any) -> dict[str, Any]:
        if not shape_id or shape.IsNull():
            raise ValueError("shape_id and non-null TopoDS shape are required")
        self._shapes[shape_id] = shape
        return self.describe(shape_id)

    def write_brep(self, shape_id: str, path: str | Path) -> None:
        if not BRepTools.Write_s(self._shape(shape_id),str(Path(path).resolve())): raise RuntimeError("OCCT failed to write BREP cache")

    def load_brep(self, shape_id: str, path: str | Path) -> None:
        shape=TopoDS_Shape()
        if not BRepTools.Read_s(shape,str(Path(path).resolve()),BRep_Builder()): raise RuntimeError("OCCT failed to read BREP cache")
        self._shapes[shape_id]=shape

    def load_step(self, path: str | Path, *, lightweight: bool = False,
                  progress: Callable[[dict[str, Any]], None] | None = None) -> dict[str, Any]:
        source = Path(path).resolve()
        if source.suffix.lower() not in {".stp", ".step"}:
            raise ValueError("OCCT B-Rep input must be STEP/STP")
        started = perf_counter(); reader = STEPControl_Reader()
        if reader.ReadFile(str(source)) != IFSelect_RetDone:
            raise RuntimeError(f"OCCT failed to read STEP: {source}")
        if progress: progress({"stage":"OCCT_STEP_READ_COMPLETE","elapsed_seconds":round(perf_counter()-started,3),"roots":reader.NbRootsForTransfer()})
        if reader.TransferRoots() <= 0:
            raise RuntimeError("OCCT STEP reader transferred no roots")
        if progress: progress({"stage":"OCCT_STEP_TRANSFER_COMPLETE","elapsed_seconds":round(perf_counter()-started,3),"transferred_shapes":reader.NbShapes()})
        self.source_file = str(source)
        self._shapes.clear()
        self._shape_names.clear()
        root = reader.OneShape()
        self._shapes["STEP_ROOT"] = root
        items = independent_geometry(root)
        from .step_identity import transferred_shape_names
        shape_names = transferred_shape_names(reader, items)
        counters={}; kinds={}
        for (prefix, shape), identity in zip(items, shape_names):
            counters[prefix]=counters.get(prefix,0)+1; index=counters[prefix]
            shape_id = f"STEP_{prefix}_{index:04d}"
            self._shapes[shape_id] = shape
            kinds[shape_id]=prefix
            if identity['name']:
                self._shape_names[shape_id] = _decode_step_text(identity['name'])
        if lightweight:
            descriptions = [{"shape_id":shape_id,"source_name":self._shape_names.get(shape_id),
                "identity_source":"STEP_TRANSFER_ENTITY_SHAPE_ASSOCIATION" if shape_id in self._shape_names else None,
                "valid":None,"geometry_kind":kinds[shape_id],"solid_count":1 if kinds[shape_id]=="SOLID" else 0,"face_count":None,"edge_count":None,
                "capabilities":["EXACT_BREP"],"bounds_mm":_bounds(self._shapes[shape_id]),
                **_mass_properties(self._shapes[shape_id]),
                **({'volume_mm3':None} if kinds[shape_id]!='SOLID' else {}),
                "surface_features":None,"geometry_authority":"OCCT_TOPO_DS_SHAPE"}
                for shape_id in self._shapes if shape_id!="STEP_ROOT"]
            descriptions.insert(0,{"shape_id":"STEP_ROOT","source_name":None,"identity_source":None,
                "valid":None,"solid_count":counters.get('SOLID',0),"face_count":None,"edge_count":None,
                "capabilities":["EXACT_BREP"],"bounds_mm":_bounds(root),"surface_features":None,
                "geometry_authority":"OCCT_TOPO_DS_SHAPE"})
        else: descriptions=[self.describe(shape_id) for shape_id in self._shapes]
        if progress: progress({"stage":"OCCT_MANIFEST_COMPLETE","elapsed_seconds":round(perf_counter()-started,3),"registered_shapes":len(descriptions),"lightweight":lightweight})
        for record in descriptions:
            if record['shape_id'] != 'STEP_ROOT' and kinds.get(record['shape_id']) == 'SOLID':
                sid = record['shape_id']
                record['face_ids'] = [f"{sid}::FACE_{index:06d}" for index, _ in
                                      enumerate(_subshapes(self._shapes[sid], TopAbs_FACE), 1)]
                record['faces_complete'] = True
                record['face_ownership_method'] = 'OCCT_SOLID_SUBSHAPE_TRAVERSAL'
        return {"schema_version": "occt-brep-model.v1.0", "source_file": self.source_file,
                "backend": "OCCT", "root_shape_id": "STEP_ROOT",
                "shapes": descriptions}

    def load_iges(self, path: str | Path) -> dict[str, Any]:
        source = Path(path).resolve()
        if source.suffix.lower() not in {".igs", ".iges"}:
            raise ValueError("OCCT B-Rep input must be IGES/IGS")
        reader = IGESControl_Reader()
        if reader.ReadFile(str(source)) != IFSelect_RetDone:
            raise RuntimeError(f"OCCT failed to read IGES: {source}")
        if reader.TransferRoots() <= 0:
            raise RuntimeError("OCCT IGES reader transferred no roots")
        self.source_file = str(source)
        self._shapes.clear()
        self._shape_names.clear()
        root = reader.OneShape()
        self.register_shape("IGES_ROOT", root)
        faces = _subshapes(root, TopAbs_FACE)
        for index, shape in enumerate(faces, 1):
            self.register_shape(f"IGES_FACE_{index:06d}", shape)
        return {"schema_version": "occt-brep-model.v1.0", "source_file": self.source_file,
                "backend": "OCCT", "root_shape_id": "IGES_ROOT",
                "shapes": [self.describe(shape_id) for shape_id in self._shapes]}

    def load_step_faces(self, path: str | Path) -> dict[str, Any]:
        """Load STEP and expose every exact face while retaining root Solid count."""
        base = self.load_step(path, lightweight=False)
        root = self._shapes["STEP_ROOT"]
        faces = _subshapes(root, TopAbs_FACE)
        descriptions = list(base["shapes"])
        for index, face in enumerate(faces, 1):
            shape_id = f"STEP_FACE_{index:06d}"
            self._shapes[shape_id] = face
            descriptions.append(self.describe(shape_id))
        return {**base, "schema_version": "occt-step-face-inventory.v1.0",
                "face_count": len(faces), "shapes": descriptions, "mesh_used": False}

    def solid_face_provenance(self, solid_id: str) -> dict[str, Any]:
        """Register exact faces under their owning solid; no STEP ordering guess."""
        faces = _subshapes(self._shape(solid_id), TopAbs_FACE)
        ids = []
        for index, face in enumerate(faces, 1):
            face_id = f"{solid_id}::FACE_{index:06d}"
            self._shapes[face_id] = face
            ids.append(face_id)
        return {"shape_id": solid_id, "face_ids": ids, "faces_complete": True,
                "ownership_method": "OCCT_SOLID_SUBSHAPE_TRAVERSAL"}

    def _shape(self, shape_id: str) -> Any:
        try:
            return self._shapes[shape_id]
        except KeyError as exc:
            raise ValueError(f"Unknown OCCT shape_id: {shape_id}") from exc

    def describe(self, shape_id: str) -> dict[str, Any]:
        shape = self._shape(shape_id)
        analyzer = BRepCheck_Analyzer(shape)
        bounds = _bounds(shape)
        return {"shape_id": shape_id, "source_name": self._shape_names.get(shape_id),
                "identity_source": ("STEP_TRANSFER_ENTITY_SHAPE_ASSOCIATION"
                                    if shape_id in self._shape_names else None),
                "valid": bool(analyzer.IsValid()),
                "solid_count": _count(shape, TopAbs_SOLID), "face_count": _count(shape, TopAbs_FACE),
                "edge_count": _count(shape, TopAbs_EDGE), "capabilities": ["EXACT_BREP"],
                "bounds_mm": bounds,
                **_mass_properties(shape),
                **({'volume_mm3':None} if _count(shape,TopAbs_SOLID)==0 else {}),
                "surface_features": _face_features(shape),
                "geometry_authority": "OCCT_TOPO_DS_SHAPE"}

    def distance(self, first_id: str, second_id: str) -> dict[str, Any]:
        operation = BRepExtrema_DistShapeShape(self._shape(first_id), self._shape(second_id))
        operation.Perform()
        if not operation.IsDone() or operation.NbSolution() < 1:
            raise RuntimeError("OCCT exact distance failed")
        point1, point2 = operation.PointOnShape1(1), operation.PointOnShape2(1)
        return {"minimum_distance_mm": float(operation.Value()),
                "closest_point_a_mm": [point1.X(), point1.Y(), point1.Z()],
                "closest_point_b_mm": [point2.X(), point2.Y(), point2.Z()],
                "method": "OCCT_BREP_EXTREMA_DIST_SHAPE_SHAPE", "exact_brep": True}

    def distance_to(self, first_id: str, other: "OCCTBRepModel", second_id: str) -> dict[str, Any]:
        operation = BRepExtrema_DistShapeShape(self._shape(first_id), other._shape(second_id)); operation.Perform()
        if not operation.IsDone() or operation.NbSolution() < 1: raise RuntimeError("OCCT exact cross-batch distance failed")
        p1,p2=operation.PointOnShape1(1),operation.PointOnShape2(1)
        return {"minimum_distance_mm":float(operation.Value()),"closest_point_a_mm":[p1.X(),p1.Y(),p1.Z()],"closest_point_b_mm":[p2.X(),p2.Y(),p2.Z()],"method":"OCCT_BREP_EXTREMA_CROSS_BATCH","exact_brep":True}

    def section(self, first_id: str, second_id: str) -> dict[str, Any]:
        operation = BRepAlgoAPI_Section(self._shape(first_id), self._shape(second_id), False)
        operation.Build()
        if not operation.IsDone():
            raise RuntimeError("OCCT B-Rep section failed")
        result = operation.Shape()
        section_edges = _subshapes(result, TopAbs_EDGE)
        edge_count = len(section_edges)
        boundary_only = False
        sample_points = []
        normal_alignments = []
        for item in section_edges:
            curve = BRepAdaptor_Curve(TopoDS.Edge_s(item))
            parameter = (curve.FirstParameter() + curve.LastParameter()) / 2.0
            point = curve.Value(parameter)
            sample_points.append([point.X(), point.Y(), point.Z()])
        first_faces = _subshapes(self._shape(first_id), TopAbs_FACE)
        second_faces = _subshapes(self._shape(second_id), TopAbs_FACE)
        # For a Face-to-Face section, distinguish a shared trim boundary from a
        # curve passing through either face interior. SPA distance alone reports
        # zero for both cases, so this is the exact topological discriminator.
        if edge_count and len(first_faces) == 1 and len(second_faces) == 1:
            face_a, face_b = TopoDS.Face_s(first_faces[0]), TopoDS.Face_s(second_faces[0])
            midpoint_states = []
            for xyz in sample_points:
                point = gp_Pnt(*xyz)
                state_a = BRepClass_FaceClassifier(face_a, point, 1e-7).State()
                state_b = BRepClass_FaceClassifier(face_b, point, 1e-7).State()
                midpoint_states.append((state_a, state_b))
                normal_a, normal_b = _face_normal(face_a, point), _face_normal(face_b, point)
                if normal_a and normal_b:
                    normal_alignments.append(abs(sum(a * b for a, b in zip(normal_a, normal_b))))
            boundary_only = all(a == TopAbs_ON and b == TopAbs_ON for a, b in midpoint_states)
        minimum_normal_alignment = min(normal_alignments) if normal_alignments else None
        coincident_area = 0.0
        if boundary_only and len(first_faces) == 1 and len(second_faces) == 1:
            common = BRepAlgoAPI_Common(face_a, face_b)
            common.Build()
            if common.IsDone():
                properties = GProp_GProps()
                BRepGProp.SurfaceProperties_s(common.Shape(), properties)
                coincident_area = max(0.0, float(properties.Mass()))
        continuous_surface_contact = bool(
            boundary_only and minimum_normal_alignment is not None and
            minimum_normal_alignment >= math.cos(math.radians(3.0)) and
            coincident_area <= 1e-8)
        section_bounds = _bounds(result) if edge_count else None
        section_center = None if section_bounds is None else [
            (section_bounds["min"][axis] + section_bounds["max"][axis]) / 2.0 for axis in range(3)]
        return {"intersects": edge_count > 0, "section_edge_count": edge_count,
                "section_vertex_count": _count(result, TopAbs_VERTEX),
                "section_bounds_mm": section_bounds,
                "section_center_mm": section_center,
                "section_sample_points_mm": sample_points,
                "section_on_both_boundaries": boundary_only,
                "minimum_abs_normal_alignment": minimum_normal_alignment,
                "coincident_surface_area_mm2": coincident_area,
                "coincident_surface_overlap": coincident_area > 1e-8,
                "continuous_surface_contact": continuous_surface_contact,
                "surface_continuity_angle_tolerance_deg": 3.0,
                "section_relation": ("BOUNDARY_CONTACT" if boundary_only else
                                     "INTERIOR_INTERSECTION" if edge_count else "DISJOINT"),
                "method": "OCCT_BREP_ALGO_SECTION", "exact_brep": True}

    def penetration_evidence(self, solid_id: str, surface_id: str,
                             sample_points_mm: list[list[float]], *,
                             sample_offset_mm: float = 0.05) -> dict[str, Any]:
        """Test whether a solid occupies both normal sides of a trimmed Face."""
        surface_faces = _subshapes(self._shape(surface_id), TopAbs_FACE)
        if _count(self._shape(solid_id), TopAbs_SOLID) < 1 or len(surface_faces) != 1:
            return {"penetration_confirmed": False, "penetration_evidence_available": False,
                    "reason": "REQUIRES_ONE_SOLID_AND_ONE_FACE"}
        face = TopoDS.Face_s(surface_faces[0])
        adaptor = BRepAdaptor_Surface(face)
        geometric_surface = BRep_Tool.Surface_s(face)
        offset = max(float(sample_offset_mm), 1e-6)
        common = BRepAlgoAPI_Common(self._shape(solid_id), face)
        common.Build()
        common_area = 0.0
        common_center = None
        if common.IsDone():
            properties = GProp_GProps()
            BRepGProp.SurfaceProperties_s(common.Shape(), properties)
            common_area = max(0.0, float(properties.Mass()))
            if common_area > 0.0:
                center = properties.CentreOfMass()
                common_center = [center.X(), center.Y(), center.Z()]
        evaluation_points = ([common_center] if common_center is not None
                             else list(sample_points_mm))
        samples = []
        for xyz in evaluation_points:
            point = gp_Pnt(*[float(value) for value in xyz])
            projection = GeomAPI_ProjectPointOnSurf(point, geometric_surface)
            if not projection.IsDone() or projection.NbPoints() < 1:
                continue
            u, v = projection.LowerDistanceParameters()
            properties = BRepLProp_SLProps(adaptor, u, v, 1, 1e-9)
            if not properties.IsNormalDefined():
                continue
            normal = properties.Normal()
            plus = [point.X() + offset * normal.X(), point.Y() + offset * normal.Y(),
                    point.Z() + offset * normal.Z()]
            minus = [point.X() - offset * normal.X(), point.Y() - offset * normal.Y(),
                     point.Z() - offset * normal.Z()]
            plus_state = self.classify_point(solid_id, plus, 1e-7)["point_state"]
            minus_state = self.classify_point(solid_id, minus, 1e-7)["point_state"]
            samples.append({"intersection_point_mm": list(xyz),
                            "surface_normal": [normal.X(), normal.Y(), normal.Z()],
                            "positive_sample_mm": plus, "positive_side_state": plus_state,
                            "negative_sample_mm": minus, "negative_side_state": minus_state,
                            "solid_on_both_sides": plus_state == "IN" and minus_state == "IN"})
        confirmed = any(item["solid_on_both_sides"] for item in samples)
        return {"penetration_confirmed": confirmed,
                "penetration_evidence_available": bool(samples),
                "crosses_surface_normal_sides": confirmed,
                "solid_surface_common_area_mm2": common_area,
                "solid_surface_common_center_mm": common_center,
                "normal_sample_offset_mm": offset, "side_samples": samples,
                "penetration_method": "OCCT_FACE_NORMAL_TWO_SIDE_SOLID_CLASSIFICATION"}

    def common_volume(self, first_id: str, second_id: str) -> dict[str, Any]:
        operation = BRepAlgoAPI_Common(self._shape(first_id), self._shape(second_id))
        operation.Build()
        if not operation.IsDone():
            raise RuntimeError("OCCT B-Rep common failed")
        properties = GProp_GProps()
        BRepGProp.VolumeProperties_s(operation.Shape(), properties)
        return {"intersection_volume_mm3": max(0.0, float(properties.Mass())),
                "method": "OCCT_BREP_ALGO_COMMON", "exact_brep": True}

    def local_overlap_evidence(self, first_id: str, second_id: str) -> dict[str, Any]:
        """Locate exact overlap and probe interior witnesses; never infer intent."""
        operation = BRepAlgoAPI_Common(self._shape(first_id), self._shape(second_id))
        operation.Build()
        if not operation.IsDone():
            raise RuntimeError('OCCT local common failed')
        common = operation.Shape()
        common_properties = _mass_properties(common)
        bounds = _bounds(common)
        valid = bool(BRepCheck_Analyzer(common).IsValid())
        tolerance = max(1e-7, *(BRep_Tool.MaxTolerance_s(self._shape(s), k)
                           for s in (first_id, second_id) for k in
                           (TopAbs_FACE, TopAbs_EDGE, TopAbs_VERTEX)))
        witnesses = []
        if bounds and common_properties['volume_mm3'] > 0:
            points = [common_properties['centroid_mm']]
            # A centroid can lie outside concave or hollow common geometry.
            points += [[bounds['min'][i] + (bounds['max'][i]-bounds['min'][i])*f[i]
                        for i in range(3)] for f in
                       ((x,y,z) for x in (.1,.3,.5,.7,.9) for y in (.1,.3,.5,.7,.9)
                        for z in (.1,.3,.5,.7,.9))]
            probe = max(.001, 2*tolerance)
            for point in points:
                states = [self.classify_point(s, point, tolerance)['point_state']
                          for s in (first_id, second_id)]
                if states != ['IN', 'IN']:
                    continue
                offsets = []
                for axis in range(3):
                    for sign in (-1,1):
                        shifted = list(point); shifted[axis] += sign*probe
                        offsets.append(all(self.classify_point(s, shifted, tolerance)['point_state']=='IN'
                                           for s in (first_id, second_id)))
                witnesses.append({'point_mm': point, 'states': states,
                                  'six_axis_margin_probe_mm': probe,
                                  'six_axis_margin_confirmed': all(offsets)})
                if all(offsets) or len(witnesses) >= 3:
                    break
        return {'exact_brep': True, 'method': 'OCCT_COMMON_AND_INTERIOR_POINT_PROBES',
                'common_valid': valid, 'common_bounds_mm': bounds,
                'common_solid_count': _count(common, TopAbs_SOLID),
                **common_properties, 'classification_tolerance_mm': tolerance,
                'interior_witnesses': witnesses,
                'robust_interior_witness_found': any(w['six_axis_margin_confirmed'] for w in witnesses),
                'engineering_intent_inferred': False}

    def common_volume_to(self, first_id: str, other: "OCCTBRepModel", second_id: str) -> dict[str, Any]:
        operation=BRepAlgoAPI_Common(self._shape(first_id),other._shape(second_id)); operation.Build()
        if not operation.IsDone(): raise RuntimeError("OCCT B-Rep cross-batch common failed")
        properties=GProp_GProps(); BRepGProp.VolumeProperties_s(operation.Shape(),properties)
        return {"intersection_volume_mm3":max(0.0,float(properties.Mass())),"method":"OCCT_BREP_ALGO_CROSS_BATCH_COMMON","exact_brep":True}

    def classify_point(self, solid_id: str, point_xyz_mm: list[float], tolerance_mm: float) -> dict[str, Any]:
        from OCP.gp import gp_Pnt
        solid = self._shape(solid_id)
        if _count(solid, TopAbs_SOLID) < 1:
            raise ValueError("containment classification requires a solid")
        classifier = BRepClass3d_SolidClassifier(
            solid, gp_Pnt(*[float(value) for value in point_xyz_mm]), float(tolerance_mm))
        state = classifier.State()
        label = "IN" if state == TopAbs_IN else "ON" if state == TopAbs_ON else "OUT"
        return {"point_state": label, "contained": label == "IN", "on_boundary": label == "ON",
                "method": "OCCT_BREP_CLASS3D_SOLID_CLASSIFIER", "exact_brep": True}

    def pair_fact(self, first_id: str, second_id: str, *, entity_a: dict[str, Any],
                  entity_b: dict[str, Any]) -> dict[str, Any]:
        distance = self.distance(first_id, second_id)
        section = self.section(first_id, second_id)
        fact = {"object_a": first_id, "object_b": second_id, "entity_a": entity_a,
                "entity_b": entity_b, **distance, **section,
                "method": "OCCT_EXACT_BREP_DISTANCE_AND_SECTION"}
        if entity_a.get("geometry_kind") == "SOLID" and entity_b.get("geometry_kind") == "SOLID":
            fact.update(self.common_volume(first_id, second_id))
            fact["method"] = "OCCT_EXACT_BREP_DISTANCE_SECTION_COMMON"
        else:
            fact["surface_intersection"] = bool(section["intersects"] and not section["section_on_both_boundaries"])
            fact["boundary_contact"] = bool(section["section_on_both_boundaries"])
            fact["intersection_type"] = ("CONTACT" if fact["boundary_contact"] else
                                         "SURFACE_INTERSECTION" if fact["surface_intersection"] else
                                         "SURFACE_CLEARANCE")
            kinds = (entity_a.get("geometry_kind"), entity_b.get("geometry_kind"))
            if fact["surface_intersection"] and kinds.count("SOLID") == 1:
                solid_id, surface_id = ((first_id, second_id) if kinds[0] == "SOLID"
                                        else (second_id, first_id))
                fact.update(self.penetration_evidence(
                    solid_id, surface_id, section.get("section_sample_points_mm") or []))
        return fact

    def surface_pair_fact(self, first_id: str, second_id: str, *, entity_a: dict[str, Any],
                          entity_b: dict[str, Any]) -> dict[str, Any]:
        if entity_a.get("geometry_kind") == "SOLID" and entity_b.get("geometry_kind") == "SOLID":
            raise ValueError("surface_pair_fact requires at least one non-solid entity")
        return self.pair_fact(first_id, second_id, entity_a=entity_a, entity_b=entity_b)
