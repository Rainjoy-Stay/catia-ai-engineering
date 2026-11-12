"""Offline pilot diagnostics; never changes production tolerances or source models."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from reverify_bulk_transfer import adaptive_properties, independent_geometry, transferred_shape_names
from OCP.STEPControl import STEPControl_Reader
from OCP.IFSelect import IFSelect_RetDone
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepClass3d import BRepClass3d
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.TopoDS import TopoDS
from OCP.TopAbs import TopAbs_SHELL
from OCP.TopExp import TopExp_Explorer


def relative(a, b):
    return abs(a-b)/max(abs(a), abs(b), 1e-12)


def run(directory):
    audit=json.loads((directory/'benchmark.json').read_text(encoding='utf-8'))
    case=next(c for c in audit['cases'] if c['mode']=='bulk')
    expected={r['batch_body_name']:r for r in case['mapping']}
    reader=STEPControl_Reader()
    if reader.ReadFile(case['step_path'])!=IFSelect_RetDone or reader.TransferRoots()<=0:
        raise RuntimeError('STEP import failed')
    items=independent_geometry(reader.OneShape())
    rows=[]
    for (kind,shape),identity in zip(items,transferred_shape_names(reader,items)):
        source=expected[identity['name']]
        measures={str(e):adaptive_properties(shape,e) for e in (1e-6,1e-8,1e-10)}
        final=measures[str(1e-10)]
        outer=BRepClass3d.OuterShell_s(TopoDS.Solid_s(shape))
        props=GProp_GProps()
        if outer.IsNull():
            raise RuntimeError('Missing outer shell')
        BRepGProp.SurfaceProperties_s(outer,props,1e-10,False)
        outer_area=props.Mass()
        shells=0; explorer=TopExp_Explorer(shape,TopAbs_SHELL)
        while explorer.More():
            shells+=1; explorer.Next()
        volume_delta=relative(final['volume_mm3'],source['volume_mm3'])
        center_delta=max(abs(a-b) for a,b in zip(final['centroid_mm'],source['centroid_mm']))
        total_delta=relative(final['surface_area_mm2'],source['surface_area_mm2'])
        outer_delta=relative(outer_area,source['surface_area_mm2'])
        rows.append({'name':identity['name'],'source_body_index':source['source_body_index'],
            'valid_topology':bool(BRepCheck_Analyzer(shape).IsValid()),'shell_count':shells,
            'source_area_scope':'UNVERIFIED','source':source,'integration':measures,
            'total_surface_area_mm2':final['surface_area_mm2'],
            'outer_shell_area_mm2':outer_area,
            'inner_shell_area_mm2':final['surface_area_mm2']-outer_area,
            'relative_volume_delta':volume_delta,'centroid_max_delta_mm':center_delta,
            'relative_total_area_delta':total_delta,'relative_outer_area_delta':outer_delta,
            'volume_centroid_within_original_limits':volume_delta<=1e-4 and center_delta<=1e-3,
            'total_scope_comparison_within_limits':volume_delta<=1e-4 and center_delta<=1e-3 and total_delta<=1e-4,
            'outer_scope_hypothesis_within_limits':volume_delta<=1e-4 and center_delta<=1e-3 and outer_delta<=1e-4,
            'volume_convergence_relative':relative(measures[str(1e-8)]['volume_mm3'],final['volume_mm3'])})
        print(identity['name'],flush=True)
    summary={'objects':len(rows),'invalid_topology':sum(not r['valid_topology'] for r in rows),
        'volume_centroid_within_limits':sum(r['volume_centroid_within_original_limits'] for r in rows),
        'total_scope_within_limits':sum(r['total_scope_comparison_within_limits'] for r in rows),
        'outer_scope_hypothesis_within_limits':sum(r['outer_scope_hypothesis_within_limits'] for r in rows),
        'multiple_shell_objects':sum(r['shell_count']>1 for r in rows)}
    result={'summary':summary,'geometry':rows,'production_changed':False,
        'source_modified':False,'full_model_check':False,
        'warning':'Area scope is unverified; hypothesis comparisons are not engineering PASS.'}
    (directory/'measurement-scope-review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('directory',type=Path)
    run(parser.parse_args().directory)
