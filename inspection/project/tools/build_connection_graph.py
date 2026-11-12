"""Build and persist a dumb-model engineering relationship graph."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from catia_checker.model_understanding.graph import ConnectionGraphRepository
from catia_checker.model_understanding.pipeline import analyze_step_connections


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cache", type=Path)
    args = parser.parse_args()
    graph = analyze_step_connections(args.source, cache_path=args.cache)
    ConnectionGraphRepository(args.output).save_graph(graph)
    print(json.dumps({"output": str(args.output.resolve()), "summary": graph["summary"]},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
