import os
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from catia_mcp.tools.tubing import TubingTools
from catia_checker.route_preflight_tokens import issue_preflight_token


class _TransactionalTubing(TubingTools):
    def __init__(self, mismatch, dmu_pass=True):
        super().__init__(None)
        self.exists = False
        self.mismatch = mismatch
        self.dmu_pass = dmu_pass

    def _resolve_arrangement_run(self, route_name):
        if not self.exists:
            raise ValueError(f"No Arrangement Run named '{route_name}'")
        return object(), 1

    def _create_arrangement_run(self, arguments):
        self.exists = True
        point = [20.5,0,0] if self.mismatch else [20,0,0]
        return json.dumps({
            "name": arguments["name"], "SectionDiameter": 4,
            "nodes": [{"point":[0,0,0]},
                      {"point":point, "bend_radius":5},
                      {"point":[20,20,0]}],
        })

    def _delete_route(self, route_name):
        self.exists = False
        return json.dumps({"deleted": route_name})

    def _validate_created_route_dmu(self, route_name, policies):
        return {"status":"PASS" if self.dmu_pass else "FAIL",
                "complete":True, "components":[]}


class RouteCreationGateTests(unittest.TestCase):
    def _token(self, folder):
        path = Path(folder) / "pass.json"
        path.write_text(json.dumps({
            "schema_version":"route-development-pipeline.v1.0",
            "candidates":[{"rank":1,"diameter_mm":4,
                "points_mm":[[0,0,0],[20,0,0],[20,20,0]],
                "bend_radii_mm":[5], "envelope":{"valid_brep":True},
                "validation":{"status":"PASS","geometry_authority":"OCCT_EXACT_BREP",
                    "components":[{"component":"equipment",
                        "policy":{"mode":"CLEARANCE","minimum_clearance_mm":0}}]}}]
        }), encoding="utf-8")
        return issue_preflight_token(path, 1)["preflight_token"]

    def test_raw_arrangement_creation_is_disabled_by_default(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CATIA_ALLOW_UNVALIDATED_ROUTE_CREATE", None)
            with self.assertRaisesRegex(RuntimeError, "Unvalidated"):
                TubingTools(None).execute("catia_tubing_create_arrangement_run", {
                    "name": "unsafe", "points": [[0,0,0],[1,0,0]],
                    "section_diameter": 1, "bend_radii": [],
                })

    def test_post_create_mismatch_rolls_back_new_route(self):
        with tempfile.TemporaryDirectory() as folder:
            tubing = _TransactionalTubing(mismatch=True)
            with self.assertRaisesRegex(RuntimeError, "ROLLED_BACK"):
                tubing._create_validated_arrangement_run({
                    "name":"route", "preflight_token":self._token(folder)})
            self.assertFalse(tubing.exists)

    def test_matching_readback_remains_unsaved_in_memory(self):
        with tempfile.TemporaryDirectory() as folder:
            tubing = _TransactionalTubing(mismatch=False)
            result = json.loads(tubing._create_validated_arrangement_run({
                "name":"route", "preflight_token":self._token(folder)}))
            self.assertEqual(result["transaction"], "COMMITTED_IN_MEMORY")
            self.assertFalse(result["saved"])
            self.assertTrue(tubing.exists)

    def test_native_dmu_failure_rolls_back_new_route(self):
        with tempfile.TemporaryDirectory() as folder:
            tubing = _TransactionalTubing(mismatch=False, dmu_pass=False)
            with self.assertRaisesRegex(RuntimeError, "NATIVE_DMU_VALIDATION_FAILED"):
                tubing._create_validated_arrangement_run({
                    "name":"route", "preflight_token":self._token(folder)})
            self.assertFalse(tubing.exists)


if __name__ == "__main__":
    unittest.main()
