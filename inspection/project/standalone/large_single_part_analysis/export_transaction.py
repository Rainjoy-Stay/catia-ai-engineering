"""Recoverable temporary STEP export transaction, independent from CATIA COM."""

from __future__ import annotations

from pathlib import Path
import tempfile
from typing import Any, Callable


def inspect_via_temporary_step(exporter: Callable[[Path], None],
                               inspector: Callable[[Path], dict[str, Any]]) -> dict[str, Any]:
    """Export, inspect, and guarantee deletion of the temporary geometry file."""
    with tempfile.TemporaryDirectory(prefix="catia-singlepart-") as directory:
        path = Path(directory) / "active_part.stp"
        exporter(path)
        if not path.is_file() or path.stat().st_size <= 0:
            raise RuntimeError("CATIA temporary STEP export produced no usable file")
        size = path.stat().st_size
        result = inspector(path)
        result["temporary_export_audit"] = {
            "format": "STEP", "size_bytes": size, "temporary_file_deleted": True,
            "source_modified": False,
        }
        return result
