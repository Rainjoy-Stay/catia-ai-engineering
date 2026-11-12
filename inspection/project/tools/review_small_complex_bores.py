import json
from pathlib import Path
from catia_checker.occt_brep import OCCTBRepModel
from standalone.step_pipe_semantics.bore_evidence import inspect_straight_bore


def main():
    directory=Path(__file__).resolve().parents[1]/'artifacts'/'step_pipe_complex_discovery'
    results=[]
    for sid in ('SOURCE_SOLID_0835','SOURCE_SOLID_0836'):
        detail=json.loads((directory/(sid+'.json')).read_text(encoding='utf-8'))
        cylinders=[f['surface_features'] for f in detail['faces'] if f['surface_features']['surface_type']=='CYLINDER']
        inner,outer=sorted(cylinders,key=lambda f:f['radius_mm'])
        centers=[s['center_mm'] for s in detail['opening_seeds']]
        model=OCCTBRepModel(); model.load_brep(sid,directory/(sid+'.brep'))
        evidence=inspect_straight_bore(model,sid,centers,inner['radius_mm'],outer['radius_mm'])
        torus=next(f['surface_features'] for f in detail['faces'] if f['surface_features']['surface_type']=='TORUS')
        results.append({'solid_id':sid,'evidence':evidence,'inner_diameter_mm':2*inner['radius_mm'],
            'cylindrical_outer_diameter_mm':2*outer['radius_mm'],
            'cylindrical_wall_thickness_mm':outer['radius_mm']-inner['radius_mm'],
            'length_mm':evidence['witness_length_mm'],'torus_major_radius_mm':torus['major_radius_mm'],
            'torus_minor_radius_mm':torus['minor_radius_mm'],
            'interpretation':'SHORT_COAXIAL_HOLLOW_GEOMETRY_WITH_END_ROUNDING_REVIEW_ONLY',
            'centerline_bend_radius_mm':None,'status':'NOT_EVALUATED'})
    (directory/'small_complex_bore_review.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    for r in results: print(r['solid_id'],r['evidence']['clear_passage_witness_confirmed'],r['evidence']['sampled_wall_min_mm'],r['evidence']['sampled_wall_max_mm'])


if __name__=='__main__': main()
