import unittest

from catia_mcp.tools.measurement import MeasurementTools


class BodyGeometryToolDefinitionTests(unittest.TestCase):
    def test_batch_body_measurement_is_registered_read_only(self):
        tool = MeasurementTools(object())
        definition = next(item for item in tool.get_tool_definitions()
                          if item["name"] == "catia_get_body_geometry_batch")
        bbox = definition["inputSchema"]["properties"]["include_bounding_box"]
        self.assertFalse(bbox["default"])
        self.assertIn("without modifying", definition["description"])

    def test_part_inventory_keeps_surface_candidates(self):
        tool = MeasurementTools(object())
        definition = next(item for item in tool.get_tool_definitions()
                          if item["name"] == "catia_get_part_geometry_inventory")
        self.assertIn("Zero-volume surfaces are retained", definition["description"])
        self.assertTrue(definition["inputSchema"]["properties"]["include_reference_geometry"]["default"])

    def test_active_part_tessellation_is_read_only_and_bounded(self):
        tool = MeasurementTools(object())
        definition = next(item for item in tool.get_tool_definitions()
                          if item["name"] == "catia_export_active_part_tessellation")
        self.assertIn("does not create clipboard copies", definition["description"])
        self.assertEqual(definition["inputSchema"]["properties"]["max_triangles"]["default"], 200000)

    def test_product_instances_exposes_affine_transform(self):
        definition = next(item for item in MeasurementTools(object()).get_tool_definitions()
                          if item["name"] == "catia_get_product_component_instances")
        self.assertIn("affine transforms", definition["description"])


if __name__ == "__main__":
    unittest.main()
