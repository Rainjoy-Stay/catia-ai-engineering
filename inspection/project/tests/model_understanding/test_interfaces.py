import unittest

from catia_checker.model_understanding.features.interfaces import match_terminal_to_interfaces


class InterfaceTests(unittest.TestCase):
    def test_coincident_parallel_circle_is_direct_interface_evidence(self):
        terminal = {"position_mm": [10, 0, 0], "direction": [1, 0, 0],
                    "coordinate_space": "WORLD"}
        interfaces = [{"center_mm": [10.1, 0, 0], "normal": [-1, 0, 0], "radius_mm": 5}]
        matches = match_terminal_to_interfaces(terminal, interfaces)
        self.assertEqual(matches[0]["evidence_state"], "COINCIDENT_CIRCULAR_INTERFACE")

    def test_nearby_but_perpendicular_circle_is_not_interface_evidence(self):
        terminal = {"position_mm": [10, 0, 0], "direction": [1, 0, 0],
                    "coordinate_space": "WORLD"}
        interfaces = [{"center_mm": [10, 0, 0], "normal": [0, 1, 0], "radius_mm": 5}]
        self.assertEqual(match_terminal_to_interfaces(terminal, interfaces), [])
