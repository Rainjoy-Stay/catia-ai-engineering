"""Standalone exact-evidence opening/nozzle interface analysis."""

from .analyzer import analyze_interface, analyze_interfaces
from .matching import match_openings_to_nozzles
from .pipeline import analyze_opening_network
from .adapters import adapt_exact_geometry
from .cylinders import merge_coaxial_cylinders
from .discovery import discover_adapter_payload
from .wall_thickness import infer_wall_thickness_from_opening_pairs

__all__ = ["analyze_interface", "analyze_interfaces", "match_openings_to_nozzles",
           "analyze_opening_network"]
__all__.append("adapt_exact_geometry")
__all__.append("merge_coaxial_cylinders")
__all__.append("discover_adapter_payload")
__all__.append("infer_wall_thickness_from_opening_pairs")
