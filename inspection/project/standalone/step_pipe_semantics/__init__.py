"""Conservative straight hollow geometry candidates, without design inference."""
import math

VERSION = 'step-pipe-semantics.v0.3'


def _cylinder_groups(faces, tolerance):
    """Group supporting cylinders using all-member checks, retaining Face IDs."""
    groups=[]
    def compatible(a,b):
        da,db=a['axis_direction'],b['axis_direction']
        dot=sum(x*y for x,y in zip(da,db))
        if abs(abs(dot)-1)>1e-8 or abs(a['radius_mm']-b['radius_mm'])>tolerance:
            return False
        d=[x-y for x,y in zip(a['axis_origin_mm'],b['axis_origin_mm'])]
        axial=sum(x*y for x,y in zip(d,da))
        return math.sqrt(sum((d[i]-axial*da[i])**2 for i in range(3)))<=tolerance
    for face in faces:
        f=face['surface_features']
        values=[f['radius_mm'],f['area_mm2'],*f['axis_origin_mm'],*f['axis_direction']]
        if not all(math.isfinite(v) for v in values) or f['radius_mm']<=0 or f['area_mm2']<=0 or abs(sum(v*v for v in f['axis_direction'])-1)>1e-7:
            raise ValueError('Invalid cylinder evidence')
        matches=[g for g in groups if all(compatible(f,m['surface_features']) for m in g)]
        if len(matches)>1:
            raise ValueError('Ambiguous supporting cylinders')
        if matches: matches[0].append(face)
        else: groups.append([face])
    return [{**g[0]['surface_features'],'area_mm2':sum(m['surface_features']['area_mm2'] for m in g),
             'source_face_ids':[m['shape_id'] for m in g]} for g in groups]


def straight_candidate(solid, faces, tolerance_mm=1e-5):
    if not math.isfinite(tolerance_mm) or tolerance_mm <= 0:
        raise ValueError('Positive finite tolerance required')
    result = {'schema_version': VERSION, 'solid_id': solid.get('shape_id'),
              'status': 'NOT_EVALUATED', 'geometry_kind': 'UNDETERMINED',
              'engineering_pipe_confirmed': False,
              'face_ids': [f.get('shape_id') for f in faces]}
    def reject(reason):
        return {**result, 'reason': reason}
    if solid.get('valid') is not True or solid.get('solid_count') != 1:
        return reject('REQUIRES_VALID_SINGLE_SOLID')
    if solid.get('face_count') != len(faces) or len(set(result['face_ids'])) != len(faces) or any(f.get('valid') is not True or 'EXACT_BREP' not in f.get('capabilities', []) for f in faces):
        return reject('INCOMPLETE_OR_UNVERIFIED_FACE_EVIDENCE')
    features = [f.get('surface_features') or f for f in faces]
    cylinder_faces = [f for f in faces if (f.get('surface_features') or {}).get('surface_type') == 'CYLINDER']
    planes = [f for f in features if f.get('surface_type') == 'PLANE']
    if len(planes) != 2 or len(cylinder_faces)+len(planes) != len(faces):
        return reject('UNSUPPORTED_FACE_TOPOLOGY')
    try:
        cylinders = _cylinder_groups(cylinder_faces,tolerance_mm)
    except (KeyError,TypeError,ValueError):
        return reject('INVALID_OR_AMBIGUOUS_CYLINDER_GROUPS')
    if len(cylinders) != 2:
        return reject('REQUIRES_TWO_CYLINDERS_AND_TWO_ENDS')
    def dot(a,b): return sum(x*y for x,y in zip(a,b))
    def delta(a,b): return [x-y for x,y in zip(a,b)]
    def norm(a): return math.sqrt(dot(a,a))
    try:
        outer, inner = sorted(cylinders, key=lambda f: f['radius_mm'], reverse=True)
        ro, ri = outer['radius_mm'], inner['radius_mm']
        axis = outer['axis_direction']; origin = outer['axis_origin_mm']
        numeric = [ro,ri,*axis,*origin,*inner['axis_direction'],*inner['axis_origin_mm']]
        if not all(math.isfinite(v) for v in numeric) or not ro > ri > 0:
            return reject('INVALID_DIMENSIONS')
        if abs(norm(axis)-1) > 1e-7 or abs(norm(inner['axis_direction'])-1) > 1e-7:
            return reject('INVALID_AXIS')
        if abs(abs(dot(axis,inner['axis_direction']))-1) > 1e-8:
            return reject('AXES_NOT_PARALLEL')
        def off_axis(point):
            d = delta(point,origin); z = dot(d,axis)
            return norm([d[i]-z*axis[i] for i in range(3)])
        if off_axis(inner['axis_origin_mm']) > tolerance_mm:
            return reject('CYLINDERS_NOT_COAXIAL')
        centers = []
        for plane in planes:
            holes = plane.get('circular_inner_boundaries') or []
            if len(holes) != 1 or holes[0].get('closed') is not True or holes[0].get('exact_brep') is not True:
                return reject('END_BORE_NOT_CONFIRMED')
            hole = holes[0]; center = hole['center_mm']
            if off_axis(center) > tolerance_mm or abs(hole['radius_mm']-ri) > tolerance_mm:
                return reject('END_BORE_MISMATCH')
            if abs(abs(dot(plane['normal'],axis))-1) > 1e-8:
                return reject('END_NOT_NORMAL_TO_AXIS')
            expected_area = math.pi*(ro*ro-ri*ri)
            if not math.isclose(plane['area_mm2'],expected_area,rel_tol=1e-6,abs_tol=1e-7):
                return reject('END_ANNULUS_AREA_MISMATCH')
            centers.append(center)
        length = abs(dot(delta(centers[1],centers[0]),axis))
        if length <= tolerance_mm:
            return reject('ZERO_LENGTH')
        if not math.isclose(solid['volume_mm3'],math.pi*(ro*ro-ri*ri)*length,rel_tol=1e-6,abs_tol=1e-7):
            return reject('HOLLOW_VOLUME_MISMATCH')
        for cylinder in cylinders:
            if not math.isclose(cylinder['area_mm2'],2*math.pi*cylinder['radius_mm']*length,rel_tol=1e-6,abs_tol=1e-7):
                return reject('CYLINDER_WALL_COVERAGE_MISMATCH')
    except (KeyError,TypeError,ValueError):
        return reject('INCOMPLETE_ANALYTIC_EVIDENCE')
    return {**result,'geometry_kind':'STRAIGHT_HOLLOW_CANDIDATE',
            'reason':'COAXIAL_WALL_TWO_ANNULAR_ENDS_VOLUME_VERIFIED',
            'outer_radius_mm':ro,'inner_radius_mm':ri,'wall_thickness_mm':ro-ri,
            'length_mm':length,'axis_direction':axis,'end_centers_mm':centers,
            'wall_face_groups':[c['source_face_ids'] for c in (outer,inner)],
            'tolerance_mm':tolerance_mm,
            'ports': [{'center_mm':c, 'outward_direction':
                       [(c[i]-centers[1-j][i])/length for i in range(3)],
                       'inner_radius_mm':ri,'outer_radius_mm':ro}
                      for j,c in enumerate(centers)]}


def bend_candidate(solid, faces, tolerance_mm=1e-5):
    """Recognize circular hollow bends below 180 degrees from analytic evidence."""
    if not math.isfinite(tolerance_mm) or tolerance_mm <= 0:
        raise ValueError('Positive finite tolerance required')
    base = {'schema_version':VERSION,'solid_id':solid.get('shape_id'),
            'status':'NOT_EVALUATED','geometry_kind':'UNDETERMINED',
            'engineering_pipe_confirmed':False,'face_ids':[f.get('shape_id') for f in faces]}
    def reject(reason): return {**base,'reason':reason}
    if solid.get('valid') is not True or solid.get('solid_count') != 1:
        return reject('REQUIRES_VALID_SINGLE_SOLID')
    if solid.get('face_count') != len(faces) or len(set(base['face_ids'])) != len(faces) or any(f.get('valid') is not True or 'EXACT_BREP' not in f.get('capabilities',[]) for f in faces):
        return reject('INCOMPLETE_OR_UNVERIFIED_FACE_EVIDENCE')
    features = [f.get('surface_features') or f for f in faces]
    tori = [f for f in features if f.get('surface_type') == 'TORUS']
    planes = [f for f in features if f.get('surface_type') == 'PLANE']
    if len(faces) != 4 or len(tori) != 2 or len(planes) != 2:
        return reject('REQUIRES_TWO_TORI_AND_TWO_ENDS')
    def dot(a,b): return sum(x*y for x,y in zip(a,b))
    def delta(a,b): return [x-y for x,y in zip(a,b)]
    def norm(v): return math.sqrt(dot(v,v))
    def cross(a,b): return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
    try:
        outer,inner = sorted(tori,key=lambda f:f['minor_radius_mm'],reverse=True)
        ro,ri,R = outer['minor_radius_mm'],inner['minor_radius_mm'],outer['major_radius_mm']
        origin,axis = outer['axis_origin_mm'],outer['axis_direction']
        numbers = [ro,ri,R,inner['major_radius_mm'],solid['volume_mm3'],*origin,*axis,*inner['axis_origin_mm'],*inner['axis_direction']]
        if not all(math.isfinite(v) for v in numbers) or not R > ro > ri > 0:
            return reject('INVALID_TORUS_DIMENSIONS')
        if abs(norm(axis)-1) > 1e-7 or abs(norm(inner['axis_direction'])-1) > 1e-7:
            return reject('INVALID_AXIS')
        if norm(delta(origin,inner['axis_origin_mm'])) > tolerance_mm or abs(R-inner['major_radius_mm']) > tolerance_mm or abs(abs(dot(axis,inner['axis_direction']))-1) > 1e-8:
            return reject('TORI_NOT_CONCENTRIC')
        annulus = math.pi*(ro*ro-ri*ri)
        sweep = solid['volume_mm3']/(annulus*R)
        if not 1e-6 < sweep < math.pi-1e-6:
            return reject('UNSUPPORTED_SWEEP_RANGE')
        centers,radials,tangents = [],[],[]
        for plane in planes:
            holes = plane.get('circular_inner_boundaries') or []
            if len(holes) != 1 or holes[0].get('closed') is not True or holes[0].get('exact_brep') is not True:
                return reject('END_BORE_NOT_CONFIRMED')
            center = holes[0]['center_mm']; radial = delta(center,origin)
            if abs(norm(radial)-R) > tolerance_mm or abs(dot(radial,axis)) > tolerance_mm or abs(holes[0]['radius_mm']-ri) > tolerance_mm:
                return reject('END_NOT_ON_CENTERLINE_CIRCLE')
            radial = [v/R for v in radial]; tangent = cross(axis,radial)
            if abs(abs(dot(plane['normal'],tangent))-1) > 1e-8 or not math.isclose(plane['area_mm2'],annulus,rel_tol=1e-6,abs_tol=1e-7):
                return reject('END_ANNULUS_OR_TANGENT_MISMATCH')
            centers.append(center); radials.append(radial); tangents.append(tangent)
        if not math.isclose(dot(radials[0],radials[1]),math.cos(sweep),rel_tol=1e-6,abs_tol=1e-7):
            return reject('SWEEP_ENDPOINT_MISMATCH')
        for torus in tori:
            if not math.isclose(torus['area_mm2'],2*math.pi*torus['minor_radius_mm']*R*sweep,rel_tol=1e-6,abs_tol=1e-7):
                return reject('TORUS_AREA_SWEEP_MISMATCH')
        ports = []
        for j,center in enumerate(centers):
            tangent = tangents[j]
            sign = -1 if dot(tangent,delta(centers[1-j],center)) > 0 else 1
            ports.append({'center_mm':center,'outward_direction':[sign*v for v in tangent],
                          'inner_radius_mm':ri,'outer_radius_mm':ro})
    except (KeyError,TypeError,ValueError,ZeroDivisionError):
        return reject('INCOMPLETE_ANALYTIC_EVIDENCE')
    return {**base,'geometry_kind':'CIRCULAR_HOLLOW_BEND_CANDIDATE',
            'reason':'CONCENTRIC_TORI_ANNULAR_ENDS_SWEEP_VERIFIED',
            'outer_radius_mm':ro,'inner_radius_mm':ri,'wall_thickness_mm':ro-ri,
            'centerline_bend_radius_mm':R,'sweep_angle_rad':sweep,
            'centerline_length_mm':R*sweep,'end_centers_mm':centers,'ports':ports,
            'tolerance_mm':tolerance_mm,'bend_radius_compliance':'NOT_EVALUATED'}


def connection_candidates(candidates, tolerance_mm=1e-5):
    """Geometric mating only; never supply verified connection evidence to filter."""
    if not math.isfinite(tolerance_mm) or tolerance_mm <= 0:
        raise ValueError('Positive finite tolerance required')
    matches = []
    for i,a in enumerate(candidates):
        if a.get('geometry_kind') not in ('STRAIGHT_HOLLOW_CANDIDATE','CIRCULAR_HOLLOW_BEND_CANDIDATE'):
            continue
        for b in candidates[i+1:]:
            if b.get('solid_id') == a.get('solid_id') or b.get('geometry_kind') not in ('STRAIGHT_HOLLOW_CANDIDATE','CIRCULAR_HOLLOW_BEND_CANDIDATE'):
                continue
            for ai,ap in enumerate(a['ports']):
                for bi,bp in enumerate(b['ports']):
                    gap = math.dist(ap['center_mm'],bp['center_mm'])
                    alignment = sum(x*y for x,y in zip(ap['outward_direction'],bp['outward_direction']))
                    if gap <= tolerance_mm and alignment <= -1+1e-8 and all(abs(ap[k]-bp[k]) <= tolerance_mm for k in ('inner_radius_mm','outer_radius_mm')):
                        matches.append({'solid_a':a['solid_id'],'port_a':ai,'solid_b':b['solid_id'],
                                        'port_b':bi,'endpoint_gap_mm':gap,'direction_dot':alignment,
                                        'status':'NOT_EVALUATED','category':'GEOMETRIC_CONNECTION_CANDIDATE',
                                        'verified':False,'reason':'DESIGN_AND_FULL_OVERLAP_SCOPE_UNCONFIRMED'})
    for match in matches:
        match['ambiguous'] = any(other is not match and any(
            (match['solid_'+s],match['port_'+s]) == (other['solid_'+t],other['port_'+t])
            for s in ('a','b') for t in ('a','b')) for other in matches)
    return matches
