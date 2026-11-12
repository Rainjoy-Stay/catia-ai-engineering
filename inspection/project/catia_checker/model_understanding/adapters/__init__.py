"""Model source adapters."""

from .base import AdapterCapabilities, ModelAdapter
from .catia import CATIAManifestAdapter
from .step_brep import inspect_step_brep

__all__ = ["AdapterCapabilities", "CATIAManifestAdapter", "ModelAdapter", "inspect_step_brep"]
