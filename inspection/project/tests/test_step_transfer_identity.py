import tempfile
import unittest
from pathlib import Path
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCP.gp import gp_Pnt
from OCP.STEPControl import STEPControl_Writer,STEPControl_Reader,STEPControl_AsIs
from OCP.StepShape import StepShape_ManifoldSolidBrep
from OCP.TCollection import TCollection_HAsciiString
from OCP.IFSelect import IFSelect_RetDone
from catia_checker.occt_brep import OCCTBRepModel,independent_geometry,_mass_properties
from catia_checker.step_identity import transferred_shape_names


def export_named(path,entries):
    writer=STEPControl_Writer()
    for name,shape in entries:
        before=writer.Model().NbEntities()
        writer.Transfer(shape,STEPControl_AsIs)
        for number in range(before+1,writer.Model().NbEntities()+1):
            entity=writer.Model().Value(number)
            if isinstance(entity,StepShape_ManifoldSolidBrep):
                entity.SetName(TCollection_HAsciiString(name))
    if writer.Write(str(path))!=IFSelect_RetDone:raise RuntimeError('Export failed')


class TransferIdentityTests(unittest.TestCase):
    def test_names_follow_shapes_even_when_traversal_reversed(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'named.stp'
            export_named(path,[('small',BRepPrimAPI_MakeBox(1,1,1).Shape()),
                               ('large',BRepPrimAPI_MakeBox(gp_Pnt(10,0,0),2,2,2).Shape())])
            reader=STEPControl_Reader();reader.ReadFile(str(path));reader.TransferRoots()
            items=list(reversed(independent_geometry(reader.OneShape())))
            labels=transferred_shape_names(reader,items)
            for (_,shape),label in zip(items,labels):
                expected='small' if _mass_properties(shape)['volume_mm3']<2 else 'large'
                self.assertEqual(label['name'],expected)
                self.assertTrue(label['entities'])

    def test_void_solid_keeps_its_name_without_shifting_next_solid(self):
        hollow=BRepAlgoAPI_Cut(BRepPrimAPI_MakeBox(3,3,3).Shape(),
                              BRepPrimAPI_MakeBox(gp_Pnt(1,1,1),1,1,1).Shape()).Shape()
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'void.stp'
            export_named(path,[('hollow',hollow),('small',BRepPrimAPI_MakeBox(gp_Pnt(10,0,0),1,1,1).Shape())])
            manifest=OCCTBRepModel().load_step(path,lightweight=True)
            for shape in manifest['shapes'][1:]:
                self.assertEqual(shape['source_name'],'hollow' if shape['volume_mm3']>2 else 'small')
                self.assertEqual(shape['identity_source'],'STEP_TRANSFER_ENTITY_SHAPE_ASSOCIATION')

    def test_empty_label_stays_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'unnamed.stp';export_named(path,[('',BRepPrimAPI_MakeBox(1,1,1).Shape())])
            manifest=OCCTBRepModel().load_step(path,lightweight=True)
            self.assertIsNone(manifest['shapes'][1]['source_name'])


if __name__=='__main__':unittest.main()
