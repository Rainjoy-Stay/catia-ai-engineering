"""Offline, auditable enterprise semantic learning for engine components.

The learner intentionally combines model metadata, geometry and graph context.  It
never upgrades a geometric resemblance into a fluid-system identity without
system evidence such as a line identifier, connected equipment or an approved
enterprise tag.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import json
import math
from pathlib import Path
import re
from typing import Any, Iterable, Mapping


SCHEMA_VERSION = "engine-semantic-sample.v1"
MODEL_VERSION = "engine-semantic-model.v1"
UNKNOWN = "UNKNOWN"
NUMERIC_FIELDS = (
    "volume_mm3", "surface_area_mm2", "length_mm", "outside_diameter_mm",
    "inside_diameter_mm", "wall_thickness_mm", "bend_radius_mm",
    "port_count", "neighbor_count", "support_count",
)
TEXT_FIELDS = (
    "part_number", "instance_name", "source_name", "material", "specification",
    "line_id", "system_tag", "connected_equipment", "connected_port_names",
    "neighbor_object_types", "zone", "supplier_code", "feature_names",
)
SYSTEM_EVIDENCE_FIELDS = {
    "line_id", "system_tag", "connected_equipment", "connected_port_names",
    "specification",
}
TARGETS = ("object_type", "system_type")


def _tokens(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        value = " ".join(str(item) for item in value)
    return [token for token in re.split(r"[^0-9A-Za-z_\u4e00-\u9fff]+", str(value).casefold())
            if token]


def validate_sample(sample: Mapping[str, Any], *, labelled: bool = True) -> list[str]:
    errors = []
    if sample.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    if not str(sample.get("object_id", "")).strip():
        errors.append("object_id is required")
    features = sample.get("features")
    if not isinstance(features, Mapping):
        errors.append("features must be an object")
    if labelled:
        labels = sample.get("labels")
        if not isinstance(labels, Mapping):
            errors.append("labels must be an object")
        elif not any(str(labels.get(target, "")).strip() for target in TARGETS):
            errors.append("at least one supported label is required")
        if not str(sample.get("label_source", "")).strip():
            errors.append("label_source is required for traceability")
    return errors


def load_jsonl(path: str | Path, *, labelled: bool = True) -> list[dict[str, Any]]:
    records = []
    for line_number, line in enumerate(Path(path).read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        record = json.loads(line)
        errors = validate_sample(record, labelled=labelled)
        if errors:
            raise ValueError(f"{path}:{line_number}: {'; '.join(errors)}")
        records.append(record)
    if not records:
        raise ValueError(f"No records found in {path}")
    return records


def _feature_tokens(features: Mapping[str, Any]) -> list[str]:
    result = []
    for field in TEXT_FIELDS:
        for token in _tokens(features.get(field)):
            result.append(f"{field}={token}")
    return result


def train(samples: Iterable[Mapping[str, Any]], *, minimum_examples_per_label: int = 2
          ) -> dict[str, Any]:
    samples = list(samples)
    for sample in samples:
        errors = validate_sample(sample)
        if errors:
            raise ValueError(f"Invalid sample {sample.get('object_id')}: {'; '.join(errors)}")
    tasks: dict[str, Any] = {}
    for target in TARGETS:
        grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
        for sample in samples:
            label = str((sample.get("labels") or {}).get(target, "")).strip().upper()
            if label and label != UNKNOWN:
                grouped[label].append(sample)
        labels = {}
        vocabulary = set()
        for label, rows in sorted(grouped.items()):
            token_counts = Counter()
            numeric_values: dict[str, list[float]] = defaultdict(list)
            for row in rows:
                features = row["features"]
                tokens = _feature_tokens(features)
                token_counts.update(tokens)
                vocabulary.update(tokens)
                for field in NUMERIC_FIELDS:
                    value = features.get(field)
                    if value is not None:
                        numeric_values[field].append(float(value))
            numeric = {}
            for field, values in numeric_values.items():
                mean = sum(values) / len(values)
                variance = sum((value - mean) ** 2 for value in values) / max(len(values), 1)
                numeric[field] = {"mean": mean, "std": max(math.sqrt(variance), abs(mean) * 0.02, 1e-6),
                                  "count": len(values)}
            labels[label] = {"count": len(rows), "token_counts": dict(token_counts),
                             "token_total": sum(token_counts.values()), "numeric": numeric}
        tasks[target] = {"labels": labels, "vocabulary_size": max(len(vocabulary), 1),
                         "labelled_count": sum(len(rows) for rows in grouped.values())}
    return {"model_version": MODEL_VERSION, "sample_schema_version": SCHEMA_VERSION,
            "training_sample_count": len(samples),
            "minimum_examples_per_label": int(minimum_examples_per_label), "tasks": tasks,
            "policy": {"system_identity_requires_context": True,
                       "system_evidence_fields": sorted(SYSTEM_EVIDENCE_FIELDS)}}


def _score(features: Mapping[str, Any], task: Mapping[str, Any]) -> list[tuple[str, float, int]]:
    tokens = _feature_tokens(features)
    total = max(int(task.get("labelled_count", 0)), 1)
    vocab = int(task.get("vocabulary_size", 1))
    scored = []
    for label, stats in task.get("labels", {}).items():
        count = int(stats["count"])
        value = math.log((count + 1) / (total + len(task["labels"])))
        denominator = int(stats["token_total"]) + vocab
        counts = stats["token_counts"]
        for token in tokens:
            value += math.log((int(counts.get(token, 0)) + 1) / denominator)
        used_numeric = 0
        for field, numeric in stats.get("numeric", {}).items():
            if features.get(field) is None:
                continue
            z = (float(features[field]) - float(numeric["mean"])) / float(numeric["std"])
            value += -0.5 * min(z * z, 25.0)
            used_numeric += 1
        scored.append((label, value, count))
    return sorted(scored, key=lambda item: item[1], reverse=True)


def predict(model: Mapping[str, Any], sample: Mapping[str, Any], *, confidence_threshold: float = 0.72
            ) -> dict[str, Any]:
    errors = validate_sample(sample, labelled=False)
    if errors:
        raise ValueError("; ".join(errors))
    features = sample["features"]
    predictions = {}
    review_reasons = []
    minimum = int(model.get("minimum_examples_per_label", 2))
    for target in TARGETS:
        scored = _score(features, model["tasks"][target])
        if not scored:
            predictions[target] = {"label": UNKNOWN, "confidence": 0.0,
                                   "status": "REVIEW", "reason": "NO_TRAINING_LABELS"}
            review_reasons.append(f"{target}:NO_TRAINING_LABELS")
            continue
        top = scored[0]
        second_score = scored[1][1] if len(scored) > 1 else top[1] - 2.0
        confidence = 1.0 / (1.0 + math.exp(-max(min(top[1] - second_score, 20.0), -20.0)))
        context_fields = sorted(field for field in SYSTEM_EVIDENCE_FIELDS if features.get(field))
        reason = None
        if top[2] < minimum:
            reason = "INSUFFICIENT_LABEL_EXAMPLES"
        elif confidence < confidence_threshold:
            reason = "LOW_OR_AMBIGUOUS_CONFIDENCE"
        elif target == "system_type" and not context_fields:
            reason = "SYSTEM_CONTEXT_REQUIRED"
        accepted = reason is None
        predictions[target] = {
            "label": top[0] if accepted else UNKNOWN,
            "candidate_label": top[0], "confidence": round(confidence, 6),
            "status": "ACCEPTED" if accepted else "REVIEW", "reason": reason,
            "training_examples": top[2], "system_context_fields": context_fields,
            "alternatives": [{"label": label, "relative_score": round(score - top[1], 6)}
                             for label, score, _ in scored[:3]],
        }
        if not accepted:
            review_reasons.append(f"{target}:{reason}")
    return {"schema_version": "engine-semantic-prediction.v1",
            "object_id": sample["object_id"], "predictions": predictions,
            "requires_human_review": bool(review_reasons), "review_reasons": review_reasons,
            "policy": "Predictions are hypotheses; accepted engineering identity still requires approved enterprise evidence."}


def save_model(model: Mapping[str, Any], path: str | Path) -> None:
    Path(path).write_text(json.dumps(model, ensure_ascii=False, indent=2), encoding="utf-8")


def load_model(path: str | Path) -> dict[str, Any]:
    model = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if model.get("model_version") != MODEL_VERSION:
        raise ValueError(f"Unsupported model version: {model.get('model_version')}")
    return model

