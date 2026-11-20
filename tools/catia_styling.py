"""Generate an editable, symmetric CATIA GSD concept panel."""

import argparse
import asyncio
import json
import math
import os
from pathlib import Path
import sys
from uuid import uuid4


SET_NAME = "CAS_Panel"
SURFACE_NAME = "Panel_Surface"
DEFAULT_ROOT = Path(__file__).resolve().parents[1] / "release_build/CATIA_Offline_20261012"


def panel_plan(length, width, crown, shoulder):
    """Build a typed GSD operation plan in millimeters."""
    if not all(math.isfinite(value) for value in (length, width, crown, shoulder)):
        raise ValueError("All dimensions and style controls must be finite.")
    if min(length, width) < 1 or max(length, width) > 10000:
        raise ValueError("Length and width must be between 1 and 10000 mm.")
    if not 0 < crown <= min(length, width) / 4 or not 0 <= shoulder <= 1:
        raise ValueError("Crown must be positive and at most one quarter of the smaller dimension. Shoulder must be 0–1.")

    operations = []

    def add(tool, name, **inputs):
        operations.append((f"catia_gsd_{tool}", {"name": name, "set_name": SET_NAME, **inputs}))
        return name

    sections = []
    endpoints = []
    for station in range(5):
        length_fraction = station / 4
        envelope = 4 * length_fraction * (1 - length_fraction)
        samples = (-1, 1) if station in (0, 4) else (-1, -0.75, -0.5, 0, 0.5, 0.75, 1)
        points = []
        for index, across in enumerate(samples, start=1):
            rounded = 1 - across**2
            full_shoulder = 1 - across**4
            height = crown * envelope * ((1 - shoulder) * rounded + shoulder * full_shoulder)
            points.append(add("point", f"P{station}_{index}", x=length * length_fraction,
                              y=width * across / 2, z=height))
        endpoints.append((points[0], points[-1]))
        name = f"Section_{station}"
        if len(points) == 2:
            sections.append(add("line", name, point1=points[0], point2=points[1]))
        else:
            sections.append(add("spline", name, points=points))

    guides = [
        add("line", f"Boundary_{side}", point1=endpoints[0][index], point2=endpoints[-1][index])
        for index, side in enumerate(("Left", "Right"))
    ]
    add("loft", SURFACE_NAME, sections=sections, guides=guides)
    return operations


async def call(session, tool, arguments=None, structured=True):
    result = await session.call_tool(tool, arguments or {})
    message = "\n".join(block.text for block in result.content if block.type == "text")
    if result.isError or not message or message.lstrip().lower().startswith("error"):
        raise RuntimeError(f"{tool}: {message or 'empty response'}")
    return json.loads(message) if structured else message


async def build_panel(session, operations):
    connection = await call(session, "catia_connect", structured=False)
    if not connection.startswith("Connected to CATIA V5"):
        raise RuntimeError(f"Unexpected CATIA connection response: {connection}")

    part_number = f"CAS_Panel_{uuid4().hex[:10]}"
    created = await call(session, "catia_new_part", {"name": part_number}, structured=False)
    if created != f"Created new Part document: '{part_number}'":
        raise RuntimeError(f"CATIA did not confirm the new part identifier: {created}")
    document = await call(session, "catia_get_active_document_info")
    if document.get("type") != "CATPart" or not document.get("name") or document.get("geometrical_sets") != []:
        raise RuntimeError("Active document is not the expected empty CATPart.")
    identity = (document["name"], document["path"])

    async def verify_active():
        active = await call(session, "catia_get_active_document_info")
        if active.get("type") != "CATPart" or (active.get("name"), active.get("path")) != identity:
            raise RuntimeError("The active CATPart changed during the build.")

    try:
        await verify_active()
        created_set = await call(session, "catia_gsd_create_set", {"name": SET_NAME})
        if created_set.get("created") != SET_NAME:
            raise RuntimeError("CATIA did not confirm the geometrical set.")
        for tool, arguments in operations:
            await verify_active()
            feature = await call(session, tool, arguments)
            if feature.get("name") != arguments["name"] or feature.get("set") != SET_NAME:
                raise RuntimeError(f"CATIA did not confirm feature {arguments['name']}.")
        await verify_active()
        health = await call(session, "catia_validate_part")
        expected = [arguments["name"] for _, arguments in operations]
        shapes = next((item["shapes"] for item in health["geometrical_sets"] if item["name"] == SET_NAME), [])
        if health["update_ok"] is not True or health["stale_features_before_update"] or shapes != expected:
            raise RuntimeError(f"CATIA structural validation failed: {health}")
    except Exception as error:
        raise RuntimeError(f"Build stopped. Inspect the unsaved document {identity[0]} in CATIA. {error}") from error
    return {"document": identity[0], "part_number": part_number, "surface": SURFACE_NAME,
            "feature_count": len(expected), "saved": False, "structural_update_ok": True}


async def run_live(root, operations):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(
        command=str(root / "runtime/python.exe"),
        args=["-X", "utf8", str(root / "scripts/start_mcp.py")],
        env=dict(os.environ, PYTHONUTF8="1", CATIA_AGENT_MODE="full"),
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await build_panel(session, operations)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--length", type=float, default=300)
    parser.add_argument("--width", type=float, default=180)
    parser.add_argument("--crown", type=float, default=18, help="Center section crown in mm.")
    parser.add_argument("--shoulder", type=float, default=0.45, help="Shoulder fullness from 0 to 1.")
    parser.add_argument("--build", action="store_true", help="Build in a new unsaved CATPart.")
    parser.add_argument("--mcp-root", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args()
    try:
        operations = panel_plan(args.length, args.width, args.crown, args.shoulder)
        result = asyncio.run(run_live(args.mcp_root.resolve(), operations)) if args.build else operations
    except Exception as error:
        while isinstance(error, BaseExceptionGroup) and len(error.exceptions) == 1:
            error = error.exceptions[0]
        print(error, file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
