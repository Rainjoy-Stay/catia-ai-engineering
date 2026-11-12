"""Diagnostic only: sample cached void-derived solids without repairing geometry."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from catia_checker.occt_brep import OCCTBRepModel
from catia_checker.occt_session_cache import atomic_json, digest
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_SOLID
from OCP.TopoDS import TopoDS
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.BRepClass3d import BRepClass3d_SolidClassifier
from OCP.gp import gp_Pnt


def audit(root):
    review = root / 'shape-review'
    path = review / 'original-3066' / 'target.brep'
    before = digest(path)
    model = OCCTBRepModel()
    model.load_brep('S', path)
    explorer = TopExp_Explorer(model._shape('S'), TopAbs_SOLID)
    solids = []
    while explorer.More():
        solids.append(TopoDS.Solid_s(explorer.Current()))
        explorer.Next()
    if len(solids) != 3:
        raise RuntimeError('Unexpected cached topology: expected three solids')
    valid = [BRepCheck_Analyzer(s).IsValid() for s in solids]
    rows = []
    for index, solid in enumerate(solids[1:], 2):
        props = GProp_GProps()
        BRepGProp.VolumeProperties_s(solid, props)
        center = props.CentreOfMass()
        samples = []
        # Centroid is not necessarily interior. Always classify it in its own solid.
        for dx, dy, dz in [(0, 0, 0), (.01, 0, 0), (-.01, 0, 0),
                           (0, .01, 0), (0, -.01, 0), (0, 0, .01), (0, 0, -.01)]:
            point = gp_Pnt(center.X()+dx, center.Y()+dy, center.Z()+dz)
            states = [str(BRepClass3d_SolidClassifier(s, point, 1e-7).State()) for s in solids]
            samples.append({'point_mm': [point.X(), point.Y(), point.Z()],
                            'states_by_solid': states})
        rows.append({'solid_index': index, 'signed_volume_mm3': props.Mass(),
                     'valid': valid[index-1], 'samples': samples})
    after = digest(path)
    if before != after:
        raise RuntimeError('BREP changed during diagnostic')
    result = {'state': 'COMPLETE_DIAGNOSTIC_ONLY', 'brep_sha256': before,
              'input_valid_by_solid': valid, 'rows': rows,
              'geometry_modified': False, 'formal_results_modified': False,
              'screen_pass': False,
              'limitation': 'Classification against invalid solid 1 is diagnostic only; '
                            'finite samples cannot certify cavity containment or material semantics.'}
    atomic_json(review / 'original-void-component-samples.json', result)
    return result


if __name__ == '__main__':
    import json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.root.resolve()), ensure_ascii=True))
