import json
import tempfile
import unittest
from pathlib import Path

from catia_checker.route_preflight_tokens import (
    consume_preflight_token, issue_preflight_token,
)


class RoutePreflightTokenTests(unittest.TestCase):
    def _result(self, folder, status="PASS"):
        path = Path(folder) / "result.json"
        path.write_text(json.dumps({
            "schema_version": "route-development-pipeline.v1.0",
            "candidates": [{
                "rank": 1, "diameter_mm": 4,
                "points_mm": [[0,0,0],[20,0,0],[20,20,0]],
                "bend_radii_mm": [5],
                "envelope": {"valid_brep": True},
                "validation": {"status": status,
                               "geometry_authority": "OCCT_EXACT_BREP",
                               "components": [{"component":"equipment",
                                   "policy":{"mode":"CLEARANCE","minimum_clearance_mm":2}}]},
            }],
        }), encoding="utf-8")
        return path

    def test_token_binds_route_and_is_single_use(self):
        with tempfile.TemporaryDirectory() as folder:
            issued = issue_preflight_token(self._result(folder), 1)
            payload = consume_preflight_token(issued["preflight_token"])
            self.assertEqual(payload.section_diameter, 4)
            self.assertEqual(payload.bend_radii, (5,))
            self.assertEqual(payload.component_policies, (("equipment", "CLEARANCE", 2.0),))
            with self.assertRaisesRegex(ValueError, "consumed"):
                consume_preflight_token(issued["preflight_token"])

    def test_non_pass_candidate_cannot_receive_token(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, "PASS"):
                issue_preflight_token(self._result(folder, "FAIL"), 1)


if __name__ == "__main__":
    unittest.main()
