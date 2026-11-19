# CATIA Model Understanding Workbench v0.1

This standalone read-only baseline extends the inspection project. Its development directory is separate from historical releases. The original workspace reused `release_build/CATIA_Offline_20261012/runtime/python.exe` without changing the legacy inspection entry point or the active MCP configuration. In this source repository, use the virtual environment documented in the [repository README](../README.md).

The module reads CATPart and CATProduct structure, distinguishes part definitions from installed instances, composes rigid transforms recursively, reports read coverage, assigns snapshot-scoped object IDs, and queries captured evidence. It attaches only to a running CATIA instance registered with COM and leaves model objects, source files, and the CATIA selection untouched.

Native face and edge adjacency, persistent face references, complete surface inventories, dimensional measurements, contact and functional recognition, a natural-language front end, and cross-revision geometry matching remain unimplemented. HybridBody coverage is limited to a top-level count. Parameters and constraints are outside the current read scope. Structure coverage alone establishes neither geometry nor engineering semantics.

## Run

Run from the repository root and choose a new output directory for each capture.

~~~powershell
.venv/Scripts/python.exe tools/understand_model.py capture --output output/model_understanding_run_001
~~~

The entry point reads the active model without opening, switching, updating, or saving documents. If CATIA is unavailable or the source state changes, it records a failure diagnostic and withholds a successful snapshot. The CATIA `Saved` flag is a supplementary signal and cannot establish that all geometry stayed identical.

~~~powershell
.venv/Scripts/python.exe tools/understand_model.py query output/model_understanding_run_001/snapshot.json 'Bolt'
.venv/Scripts/python.exe tools/understand_model.py describe output/model_understanding_run_001/snapshot.json OCC_0_1
.venv/Scripts/python.exe tools/understand_model.py point output/model_understanding_run_001/snapshot.json OCC_0_1 0 0 0
~~~

`point` applies a coordinate transform. The root product defines the root coordinate frame. An unknown instance pose yields `UNKNOWN` for that instance and its descendants' world poses. Duplicate names and part numbers return candidates for review.

`compare` compares only captured data. Geometry change detection remains unavailable. Use every object ID together with its `snapshot_id`. Enumeration IDs are scoped to a snapshot and cannot serve as persistent CATIA references or cross-snapshot identities.

## Standalone MCP server

~~~powershell
.venv/Scripts/python.exe tools/start_understanding_mcp.py
~~~

The service exposes `catia_understanding_capture`, `catia_understanding_query_snapshot`, `catia_understanding_describe_snapshot`, and `catia_understanding_point_snapshot`. To use these tools in Codex, configure this standalone service or integrate the module into the maintained CATIA MCP server. This implementation is testable independently of whichever tools are loaded in the current session.

Queries require the `snapshot_id` returned by capture. A failed recapture clears the previous snapshot. Queries against historical captures return `CAPTURED_SNAPSHOT_NOT_LIVE_STATE`. The offline CLI and MCP server share the same read and query implementation.

## Validation

~~~powershell
.venv/Scripts/python.exe tools/validate_understanding.py --output output/model_understanding_validation_001 --protocol
~~~

The tool emits unit test logs, synthetic observations and snapshots, query examples, and machine-readable results. Tests use hand-written synthetic data and mock COM. Validate live CATIA `GetComponents` marshaling, units, instance reference ownership, and deep assembly coordinates separately.

## Remaining acceptance work

Start with a small real CATProduct and verify multiple instances of the same part, nested rotations and translations, unreadable components, and source state. Then validate native B-Rep and resolvable references. Gather evidence from the real interfaces and geometry kernel before extending engineering semantics to cases, disks, shafts, blades, bearings, seals, and tubing systems.
