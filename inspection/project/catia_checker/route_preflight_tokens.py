"""In-process, one-time authorization tokens for validated CATIA route creation."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import secrets
from time import monotonic
from typing import Any


@dataclass(frozen=True)
class ValidatedRoutePayload:
    points: tuple[tuple[float, float, float], ...]
    bend_radii: tuple[float, ...]
    section_diameter: float
    source_result: str
    source_sha256: str
    candidate_rank: int
    component_policies: tuple[tuple[str, str, float], ...]


_TOKENS: dict[str, tuple[float, ValidatedRoutePayload]] = {}
TOKEN_LIFETIME_SECONDS = 900.0


def issue_preflight_token(result_file: str | Path, candidate_rank: int) -> dict[str, Any]:
    path = Path(result_file).resolve()
    raw = path.read_bytes()
    result = json.loads(raw.decode("utf-8"))
    if result.get("schema_version") != "route-development-pipeline.v1.0":
        raise ValueError("Unsupported route development result schema")
    candidate = next((item for item in result.get("candidates", ())
                      if int(item.get("rank", -1)) == candidate_rank), None)
    if candidate is None:
        raise ValueError(f"Candidate rank {candidate_rank} was not found")
    validation = candidate.get("validation") or {}
    envelope = candidate.get("envelope") or {}
    if validation.get("status") != "PASS":
        raise ValueError("Preflight token requires exact B-Rep PASS")
    if validation.get("geometry_authority") != "OCCT_EXACT_BREP":
        raise ValueError("Preflight token requires OCCT exact B-Rep authority")
    if envelope.get("valid_brep") is not True:
        raise ValueError("Candidate envelope is not a valid B-Rep")
    components = validation.get("components")
    if not isinstance(components, list) or not components:
        raise ValueError("Preflight token requires a non-empty exact component validation scope")
    policies = []
    for component in components:
        policy = component.get("policy") or {}
        name, mode = component.get("component"), policy.get("mode")
        if not name or mode not in {"REQUIRED_CONTACT", "ALLOW_CONTACT", "CLEARANCE"}:
            raise ValueError("Every validated component requires an explicit route policy")
        policies.append((str(name), str(mode), float(policy.get("minimum_clearance_mm", 0.0))))
    points = tuple(tuple(map(float, point)) for point in candidate["points_mm"])
    radii = tuple(map(float, candidate["bend_radii_mm"]))
    diameter = float(candidate["diameter_mm"])
    if len(radii) != max(0, len(points) - 2):
        raise ValueError("Candidate bend radius count does not match its point count")
    token = secrets.token_urlsafe(32)
    payload = ValidatedRoutePayload(
        points, radii, diameter, str(path), sha256(raw).hexdigest(), candidate_rank,
        tuple(policies))
    _TOKENS[token] = (monotonic() + TOKEN_LIFETIME_SECONDS, payload)
    return {
        "preflight_token": token,
        "expires_in_seconds": TOKEN_LIFETIME_SECONDS,
        "candidate_rank": candidate_rank,
        "source_result": str(path),
        "source_sha256": payload.source_sha256,
        "bound_point_count": len(points),
        "bound_bend_radii_mm": list(radii),
        "bound_section_diameter_mm": diameter,
        "bound_component_policies": [
            {"component": name, "mode": mode, "minimum_clearance_mm": clearance}
            for name, mode, clearance in policies],
    }


def consume_preflight_token(token: str) -> ValidatedRoutePayload:
    record = _TOKENS.pop(str(token), None)
    if record is None:
        raise ValueError("Unknown or already consumed route preflight token")
    expiry, payload = record
    if monotonic() > expiry:
        raise ValueError("Route preflight token has expired")
    return deepcopy(payload)
