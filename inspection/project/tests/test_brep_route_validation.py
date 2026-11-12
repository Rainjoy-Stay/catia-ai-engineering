import tempfile
import unittest
from pathlib import Path

from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.STEPControl import STEPControl_AsIs, STEPControl_Writer
from OCP.IFSelect import IFSelect_RetDone
from OCP.gp import gp_Pnt

from catia_checker.brep_route_validation import (
    BRepRouteValidationRequest, validate_route_brep,
)


class BRepRouteValidationTests(unittest.TestCase):
    def test_exact_clearance_and_interference(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "route.step"
            writer = STEPControl_Writer()
            shapes = (
                BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), gp_Pnt(10, 10, 10)).Shape(),
                BRepPrimAPI_MakeBox(gp_Pnt(20, 0, 0), gp_Pnt(30, 10, 10)).Shape(),
                BRepPrimAPI_MakeBox(gp_Pnt(25, 2, 2), gp_Pnt(28, 8, 8)).Shape(),
            )
            for shape in shapes:
                writer.Transfer(shape, STEPControl_AsIs)
            self.assertEqual(writer.Write(str(path)), IFSelect_RetDone)
            result = validate_route_brep(BRepRouteValidationRequest(
                path, "STEP_SOLID_0003",
                {"clear": ("STEP_SOLID_0001",), "hit": ("STEP_SOLID_0002",)},
            ))
            self.assertEqual(result["status"], "FAIL")
            states = {item["component"]: item["state"] for item in result["components"]}
            self.assertEqual(states, {"clear": "CLEARANCE", "hit": "INTERFERENCE"})


if __name__ == "__main__":
    unittest.main()
