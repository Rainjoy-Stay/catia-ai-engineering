"""Persistent JSON-lines worker for isolated OCCT BREP-pair evaluation."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

from catia_checker.occt_brep import OCCTBRepModel
from tools.inspect_cached_brep_pair import inspect_pair

PREFIX = "PAIR_RESULT "


def main() -> int:
    model = OCCTBRepModel()
    loaded: dict[str, str] = {}

    def shape_id(value: str) -> str:
        path = str(Path(value).resolve())
        if path not in loaded:
            identifier = "S_" + hashlib.sha256(path.encode("utf-8")).hexdigest()[:24]
            model.load_brep(identifier, path)
            loaded[path] = identifier
        return loaded[path]

    for line in sys.stdin:
        try:
            request = json.loads(line)
            first_id = shape_id(request["first"])
            second_id = shape_id(request["second"])
            result = inspect_pair(
                model, first_id=first_id, second_id=second_id,
                common_volume_distance_threshold_mm=float(request.get("threshold_mm", 0.0)))
            response = {"ok": True, "result": result, "cached_shape_count": len(loaded)}
        except Exception as exc:
            response = {"ok": False, "error_type": type(exc).__name__, "error": str(exc)}
        sys.stdout.write(PREFIX + json.dumps(response, ensure_ascii=False) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
