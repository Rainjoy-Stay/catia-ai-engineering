import unittest

from catia_checker.brep_route_validation import (
    BoundaryRoutePolicy, ComponentRoutePolicy, classify_component_interaction,
    classify_route_containment,
)


class RouteComponentPolicyTests(unittest.TestCase):
    def test_required_contact_fails_when_route_is_detached(self):
        self.assertEqual(classify_component_interaction(
            0.5, 0, ComponentRoutePolicy("REQUIRED_CONTACT")),
            ("MISSING_REQUIRED_CONTACT", True))

    def test_allowed_contact_accepts_spa_zero(self):
        self.assertEqual(classify_component_interaction(
            0, 0, ComponentRoutePolicy("ALLOW_CONTACT")),
            ("ACCEPTED_CONTACT", False))

    def test_clearance_policy_enforces_configured_value(self):
        self.assertEqual(classify_component_interaction(
            2.0, 0, ComponentRoutePolicy("CLEARANCE", 3.0)),
            ("INSUFFICIENT_CLEARANCE", True))

    def test_permitted_volume_requires_nearly_all_route_volume(self):
        self.assertEqual(classify_route_containment(100, 99.99995, 0.999999),
                         ("CONTAINED_IN_PERMITTED_VOLUME", False))
        self.assertEqual(classify_route_containment(100, 99, 0.999999),
                         ("OUTSIDE_PERMITTED_VOLUME", True))

    def test_boundary_policy_rejects_unknown_mode(self):
        with self.assertRaises(ValueError):
            BoundaryRoutePolicy("domain", "BOX_ONLY")


if __name__ == "__main__":
    unittest.main()
