"""Read-only STEP identity and numerical-integration comparison for existing exports."""
import argparse
import json
import sys
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'project'))
from OCP.STEPControl import STEPControl_Reader
from OCP.IFSelect import IFSelect_RetDone
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.BRepClass3d import BRepClass3d
from OCP.TopoDS import TopoDS
from catia_checker.occt_brep import independent_geometry, _mass_properties, _bounds
from catia_checker.step_identity import transferred_shape_names
from catia_checker.geometry_fingerprint import match_geometry_records_with_labels


def adaptive_properties(shape,epsilon):
    volume,area=GProp_GProps(),GProp_GProps()
    ev=BRepGProp.VolumeProperties_s(shape,volume,float(epsilon),False,False)
    ea=BRepGProp.SurfaceProperties_s(shape,area,float(epsilon),False)
    center=volume.CentreOfMass()
    return {'volume_mm3':volume.Mass(),'surface_area_mm2':area.Mass(),
            'centroid_mm':[center.X(),center.Y(),center.Z()],
            'volume_integration_error_estimate':ev,'area_integration_error_estimate':ea}


def run(directory):
    audit=json.loads((directory/'benchmark.json').read_text(encoding='utf-8'));results=[]
    for case in audit['cases']:
        start=time.perf_counter();reader=STEPControl_Reader()
        if reader.ReadFile(case['step_path'])!=IFSelect_RetDone or reader.TransferRoots()<=0:
            raise RuntimeError('STEP import failed')
        items=independent_geometry(reader.OneShape());labels=transferred_shape_names(reader,items)
        rows=[]
        for i,((kind,shape),label) in enumerate(zip(items,labels),1):
            row={'shape_id':str(i),'source_name':label['name'],'geometry_kind':kind,'identity_evidence':label,
                 'bounds_mm':_bounds(shape),'default_properties':_mass_properties(shape),
                 'adaptive_properties':adaptive_properties(shape,1e-8)}
            if any(e['entity_type']=='StepShape_BrepWithVoids' for e in label['entities']):
                outer=BRepClass3d.OuterShell_s(TopoDS.Solid_s(shape));props=GProp_GProps()
                if not outer.IsNull():
                    BRepGProp.SurfaceProperties_s(outer,props,1e-8,False)
                    row['outer_shell_area_mm2']=props.Mass()
            rows.append(row)
        comparisons={}
        for mode in ('default_properties','adaptive_properties'):
            facts=[{**r,**r[mode]} for r in rows]
            comparisons[mode]=match_geometry_records_with_labels(facts,case['mapping'],source_id='shape_id',
                target_id='source_body_index',source_label='source_name',target_label='batch_body_name',
                tolerances={'relative_volume':1e-4,'relative_area':1e-4,'centroid_mm':1e-3,'bounds_mm':1e-3})
        label_counts={}
        for row in rows:
            if row['source_name']:label_counts[row['source_name']]=label_counts.get(row['source_name'],0)+1
        expected={r['batch_body_name'] for r in case['mapping']}
        identity_ok=len(rows)==len(expected) and set(label_counts)==expected and all(v==1 for v in label_counts.values())
        results.append({'mode':case['mode'],'identity_complete':identity_ok,'geometry':rows,
                        'comparisons':comparisons,'seconds':time.perf_counter()-start})
        print(json.dumps({'mode':case['mode'],'identity_complete':identity_ok,
            'default_matched':comparisons['default_properties']['matched_count'],
            'adaptive_matched':comparisons['adaptive_properties']['matched_count']}),flush=True)
        expected_by_label={r['batch_body_name']:r for r in case['mapping']}
        for row in rows:
            if 'outer_shell_area_mm2' in row:
                print(json.dumps({'void_label':row['source_name'],
                    'catia_area_mm2':expected_by_label[row['source_name']]['surface_area_mm2'],
                    'occt_total_area_mm2':row['adaptive_properties']['surface_area_mm2'],
                    'occt_outer_area_mm2':row['outer_shell_area_mm2']}),flush=True)
    (directory/'transfer-association-verification.json').write_text(json.dumps({'cases':results,
        'thresholds_changed':False,'source_modified':False,'full_model_check':False},ensure_ascii=False,indent=2),encoding='utf-8')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('directory',type=Path);run(parser.parse_args().directory)
