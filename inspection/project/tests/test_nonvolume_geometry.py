import tempfile
import unittest
from pathlib import Path
from OCP.BRep import BRep_Builder
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.TopoDS import TopoDS_Compound
from OCP.gp import gp_Pln,gp_Pnt,gp_Dir
from OCP.STEPControl import STEPControl_Writer,STEPControl_AsIs
from OCP.IFSelect import IFSelect_RetDone
from catia_checker.occt_brep import OCCTBRepModel,independent_geometry
from tools.inspect_cached_brep_pair import inspect_pair
from standalone.large_single_part_analysis import analyze_large_single_part
from catia_checker.large_single_part import inspect_large_single_part_batches_isolated,build_large_single_part_result

def face(z):
    return BRepBuilderAPI_MakeFace(gp_Pln(gp_Pnt(0,0,z),gp_Dir(0,0,1)),0,2,0,2).Face()

class NonVolumeTests(unittest.TestCase):
    def test_mixed_geometry_keeps_free_face_and_not_owned_faces(self):
        root=TopoDS_Compound();builder=BRep_Builder();builder.MakeCompound(root)
        builder.Add(root,BRepPrimAPI_MakeBox(1,1,1).Shape());builder.Add(root,face(5))
        items=independent_geometry(root)
        self.assertEqual([kind for kind,_ in items],['SOLID','FACE'])
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'mixed.stp';writer=STEPControl_Writer();writer.Transfer(root,STEPControl_AsIs)
            self.assertEqual(writer.Write(str(path)),IFSelect_RetDone)
            manifest=OCCTBRepModel().load_step(path,lightweight=True)
            physical=[x for x in manifest['shapes'] if x['shape_id']!='STEP_ROOT']
            self.assertTrue(any(x['solid_count']==1 for x in physical))
            self.assertTrue(any(x['solid_count']==0 for x in physical))

    def test_surface_worker_volume_is_not_applicable(self):
        model=OCCTBRepModel();model.register_shape('A',face(0));model.register_shape('B',face(1))
        fact=inspect_pair(model)
        self.assertIsNone(fact['common']['intersection_volume_mm3'])
        self.assertFalse(fact['common']['applicable'])
        self.assertAlmostEqual(fact['distance']['minimum_distance_mm'],1)
        self.assertTrue(fact['surface']['exact_brep'])

    def test_surface_candidates_are_actually_evaluated(self):
        model=OCCTBRepModel();model.register_shape('A',face(0));model.register_shape('B',face(1))
        manifest={'shapes':[model.describe('A'),model.describe('B')]}
        result=analyze_large_single_part(model,manifest,broad_phase_margin_mm=2)
        self.assertEqual(result['exact_pair_count'],1)
        self.assertEqual(len(result['findings']),1)
        self.assertEqual(result['findings'][0]['code'],'SURFACE_CLEAR')
        self.assertIsNone(result['findings'][0]['intersection_volume_mm3'])

    def test_isolated_solid_surface_check_and_formal_filter(self):
        with tempfile.TemporaryDirectory() as folder:
            paths=[]
            for index,shape in enumerate([BRepPrimAPI_MakeBox(1,1,1).Shape(),face(.5)]):
                path=Path(folder)/f'{index}.stp';writer=STEPControl_Writer();writer.Transfer(shape,STEPControl_AsIs);writer.Write(str(path));paths.append(path)
            rules={'ruleset_id':'surface-test','large_single_part':{'max_pair_workers':1,'max_exact_pairs':10}}
            bundle=inspect_large_single_part_batches_isolated(paths,rules=rules,pair_timeout_seconds=10,max_pair_workers=1)
            self.assertEqual(len(bundle['analysis']['findings']),1)
            finding=bundle['analysis']['findings'][0]
            self.assertIn('surface_evidence',finding)
            self.assertIsNone(finding['intersection_volume_mm3'])
            result=build_large_single_part_result(bundle,document='offline test',rules=rules,run_id='test',generated_at='2026-09-30')
            self.assertEqual(result['findings'][0]['status'],'NOT_EVALUATED')

if __name__=='__main__': unittest.main()
