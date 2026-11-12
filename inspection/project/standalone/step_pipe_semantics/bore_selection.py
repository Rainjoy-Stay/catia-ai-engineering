"""Select a straight test axis; selection never confirms a bore or pipe."""
import math


def select_straight_bore_review(detail, tolerance_mm=1e-5):
    if not math.isfinite(tolerance_mm) or tolerance_mm<=0: raise ValueError('Invalid tolerance')
    def skip(reason): return {'eligible':False,'reason':reason,'status':'NOT_EVALUATED'}
    openings=detail.get('opening_seeds') or []
    if len(openings)!=2: return skip('MULTIPLE_OPENINGS_REQUIRE_BRANCH_REVIEW')
    try:
        a,b=openings; centers=[a['center_mm'],b['center_mm']]
        length=math.dist(*centers)
        radii=[a['radius_mm'],b['radius_mm']]
        if not all(math.isfinite(v) for v in [length,*radii,*centers[0],*centers[1]]) or min(radii)<=0 or length<=tolerance_mm:
            return skip('INVALID_OPENING_DIMENSIONS')
        if abs(radii[0]-radii[1])>tolerance_mm: return skip('OPENING_RADII_DIFFER')
        axis=[(centers[1][i]-centers[0][i])/length for i in range(3)]
        def parallel(direction):
            return len(direction)==3 and all(math.isfinite(v) for v in direction) and abs(sum(v*v for v in direction)-1)<=1e-7 and abs(abs(sum(x*y for x,y in zip(axis,direction)))-1)<=1e-8
        if not all(parallel(o['normal']) for o in openings): return skip('OPENINGS_NOT_NORMAL_TO_STRAIGHT_AXIS')
        coaxial=[]
        for face in detail['faces']:
            f=face.get('surface_features') or {}
            if f.get('surface_type')!='CYLINDER' or not parallel(f['axis_direction']): continue
            d=[f['axis_origin_mm'][i]-centers[0][i] for i in range(3)]
            axial=sum(x*y for x,y in zip(d,axis))
            if math.sqrt(sum((d[i]-axial*axis[i])**2 for i in range(3)))<=tolerance_mm:
                if math.isfinite(f['radius_mm']) and f['radius_mm']>0: coaxial.append(f['radius_mm'])
        ri=min(radii)
        if not any(abs(r-ri)<=tolerance_mm for r in coaxial): return skip('NO_COAXIAL_INNER_CYLINDER')
        outer=[r for r in coaxial if r>ri+tolerance_mm]
        if not outer: return skip('NO_COAXIAL_OUTER_RADIUS_FOR_SAMPLING')
    except (KeyError,TypeError,ValueError,IndexError): return skip('INCOMPLETE_OPENING_OR_AXIS_EVIDENCE')
    return {'eligible':True,'centers_mm':centers,'inner_radius_mm':ri,
            'radial_search_outer_radius_mm':max(outer),'length_mm':length,
            'reason':'COAXIAL_TWO_OPENING_TEST_AXIS_ONLY','status':'NOT_EVALUATED'}
