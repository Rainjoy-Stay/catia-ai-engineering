"""Release-baseline validation with explicit coverage and evidence semantics."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


VALID_LEVELS = {"NOT_IMPLEMENTED", "IMPLEMENTED", "UNIT_VERIFIED", "LIVE_VERIFIED", "PARTIAL"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_baseline(data: dict[str, Any], root: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if data.get("product_version") != "4.5.0-dev":
        errors.append("product_version must be 4.5.0-dev for this frozen baseline")
    if data.get("release_status") not in {"PARTIAL", "PASS", "FAIL"}:
        errors.append("release_status must be PARTIAL, PASS, or FAIL")

    chains = data.get("inspection_chains") or []
    ids = [item.get("id") for item in chains]
    if len(ids) != len(set(ids)):
        errors.append("inspection chain ids must be unique")
    for item in chains:
        level = item.get("verification_level")
        if level not in VALID_LEVELS:
            errors.append(f"invalid verification_level for {item.get('id')}: {level}")
        unresolved = int(item.get("not_evaluated_count", 0) or 0)
        if unresolved and level == "LIVE_VERIFIED":
            errors.append(f"{item.get('id')} cannot be LIVE_VERIFIED with unresolved items")
        if level in {"LIVE_VERIFIED", "PARTIAL"} and not item.get("evidence"):
            errors.append(f"{item.get('id')} requires evidence")

    checked_files: list[dict[str, Any]] = []
    for item in data.get("delivery_files") or []:
        rel = str(item.get("path") or "")
        path = root / rel
        exists = path.is_file()
        result = {"path": rel, "exists": exists}
        if not exists:
            errors.append(f"missing delivery file: {rel}")
        else:
            result["sha256"] = sha256_file(path)
            expected = item.get("sha256")
            if expected and expected != result["sha256"]:
                errors.append(f"hash mismatch: {rel}")
        checked_files.append(result)

    if any(item.get("verification_level") in {"PARTIAL", "NOT_IMPLEMENTED"} for item in chains):
        if data.get("release_status") == "PASS":
            errors.append("release_status cannot be PASS while chains are PARTIAL or NOT_IMPLEMENTED")
    if data.get("release_status") == "PARTIAL":
        warnings.append("baseline is reproducible but not a final full-model acceptance")
    return {
        "schema_version": "catia-release-baseline-validation.v1.0",
        "product_version": data.get("product_version"),
        "status": "PASS" if not errors else "FAIL",
        "release_status": data.get("release_status"),
        "errors": errors,
        "warnings": warnings,
        "inspection_chain_count": len(chains),
        "delivery_file_count": len(checked_files),
        "delivery_files": checked_files,
    }


def load_and_validate(baseline: Path, root: Path | None = None) -> dict[str, Any]:
    return validate_baseline(json.loads(baseline.read_text(encoding="utf-8")), root or baseline.parent.parent)
