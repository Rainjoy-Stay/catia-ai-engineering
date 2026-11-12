"""Train and run the offline enterprise engine semantic classifier."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from catia_checker.model_understanding.semantic_learning import (
    load_jsonl, load_model, predict, save_model, train,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="发动机零件与管路系统离线语义学习")
    commands = parser.add_subparsers(dest="command", required=True)
    training = commands.add_parser("train", help="使用已审核 JSONL 样本训练")
    training.add_argument("--samples", required=True)
    training.add_argument("--model", required=True)
    training.add_argument("--minimum-examples", type=int, default=2)
    inference = commands.add_parser("predict", help="对待识别 JSONL 执行推理")
    inference.add_argument("--model", required=True)
    inference.add_argument("--input", required=True)
    inference.add_argument("--output", required=True)
    inference.add_argument("--threshold", type=float, default=0.72)
    args = parser.parse_args()
    if args.command == "train":
        samples = load_jsonl(args.samples)
        model = train(samples, minimum_examples_per_label=args.minimum_examples)
        save_model(model, args.model)
        print(json.dumps({"status": "OK", "samples": len(samples), "model": args.model}, ensure_ascii=False))
        return 0
    model = load_model(args.model)
    samples = load_jsonl(args.input, labelled=False)
    results = [predict(model, sample, confidence_threshold=args.threshold) for sample in samples]
    Path(args.output).write_text("\n".join(json.dumps(item, ensure_ascii=False) for item in results) + "\n",
                                 encoding="utf-8")
    print(json.dumps({"status": "OK", "objects": len(results), "output": args.output,
                      "review": sum(item["requires_human_review"] for item in results)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

