"""Repeatable offline acceptance and synthetic demonstration, never opens CATIA."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import argparse
import asyncio
import io
import json
import unittest
from model_understanding_workbench.snapshot import build_snapshot, find_objects, transform_point, describe
from model_understanding_workbench.tests.test_baseline import observation


async def check_protocol():
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    params = StdioServerParameters(command=sys.executable,
                                   args=["-X", "utf8", str(ROOT/"tools/start_understanding_mcp.py")])
    async with stdio_client(params) as streams:
        async with ClientSession(*streams) as session:
            await session.initialize()
            definitions = await session.list_tools()
            names = [tool.name for tool in definitions.tools]
            if len(names) != 4:
                raise AssertionError("Expected four read-only understanding tools")
            error = await session.call_tool("catia_understanding_describe_snapshot",
                                           {"snapshot_id": "missing", "object_id": "OCC_0"})
            if not error.isError:
                raise AssertionError("Missing snapshot must be an MCP error")
            return {"status": "PASS", "tool_names": names, "missing_snapshot_is_error": True,
                    "live_capture_attempted": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--protocol", action="store_true")
    args = parser.parse_args()
    folder = Path(args.output)
    folder.mkdir(parents=True, exist_ok=False)
    suite = unittest.defaultTestLoader.discover(str(ROOT/"model_understanding_workbench/tests"))
    log = io.StringIO()
    result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    (folder/"tests.log").write_text(log.getvalue(), encoding="utf-8")
    obs = observation()
    snap = build_snapshot(obs)
    demo = {"source": "SYNTHETIC_ONLY_NOT_ENGINE_VALIDATION", "query_duplicate": find_objects(snap, "Bolt.1"),
            "nested_point": transform_point(snap, "OCC_0_1_1", [2, 0, 0]),
            "description": describe(snap, "OCC_0_1_1")}
    for name, value in (("fixture_observation.json", obs), ("fixture_snapshot.json", snap), ("demo.json", demo)):
        (folder/name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    protocol = asyncio.run(check_protocol()) if args.protocol else {"status": "NOT_RUN"}
    report = {"scope": "OFFLINE_SYNTHETIC_AND_FAKE_COM_ONLY", "tests_run": result.testsRun,
              "failures": len(result.failures), "errors": len(result.errors),
              "skipped": len(result.skipped), "protocol": protocol, "live_model_validated": False,
              "status": "PASS" if result.wasSuccessful() else "FAIL"}
    (folder/"validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not result.wasSuccessful():
        raise SystemExit(1)


if __name__ == "__main__":
    main()
