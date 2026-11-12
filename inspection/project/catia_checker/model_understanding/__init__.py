"""Read-only engineering model-understanding primitives."""

from .domain import (
    MODEL_UNDERSTANDING_SCHEMA_VERSION,
    Body,
    ClosureState,
    Component,
    GeometryCapability,
    GeometryKind,
    GeometryState,
    ModelSource,
    SemanticLevel,
    Transform,
    UnifiedGeometryModel,
)
from .semantic_level import SemanticEvaluation, evaluate_semantic_level
from .semantic_learning import load_jsonl, load_model, predict, save_model, train
from .knowledge_inference import compile_knowledge_base, infer_object, propagate_over_graph

__all__ = [
    "MODEL_UNDERSTANDING_SCHEMA_VERSION",
    "Body",
    "ClosureState",
    "Component",
    "GeometryCapability",
    "GeometryKind",
    "GeometryState",
    "ModelSource",
    "SemanticEvaluation",
    "SemanticLevel",
    "Transform",
    "UnifiedGeometryModel",
    "evaluate_semantic_level",
    "load_jsonl",
    "load_model",
    "predict",
    "save_model",
    "train",
    "compile_knowledge_base",
    "infer_object",
    "propagate_over_graph",
]
