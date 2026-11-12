"""Select the exact CATIA Bodies referenced by one inspection Issue ID."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from catia_checker.result_locator import load_issue_bodies, select_issue_bodies
from r18_connection import R18Connection


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("issue_id")
    args = parser.parse_args()
    connection = R18Connection()
    connection.connect()
    resolved = load_issue_bodies(args.report, args.issue_id)
    result = select_issue_bodies(connection.active_document, resolved)
    print(json.dumps(result, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
