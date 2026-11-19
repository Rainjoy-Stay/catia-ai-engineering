# Setup and acceptance testing

## Read-only model understanding

Use Python 3.12. Core synthetic tests use only the standard library. Live reads require Windows and `pywin32`. The MCP service requires `mcp`. Install `requirements-understanding.txt` and run the entry points under `tools/` from the repository root.

## Inspection baseline

`inspection/` preserves the original package's relative layout. The repository excludes the original offline package's custom runtime, dependencies, and `.pth` setup. Running the original `.cmd` launchers directly is unverified.

For development, add `inspection/project`, `inspection/scripts`, and `inspection/vendor/catia-v5-mcp-server` to `PYTHONPATH`. See `dependency-versions.source.json` for the source environment's dependency versions. Portability on a clean environment remains unverified. Install OCCT, NumPy, reporting, and UI dependencies as required by the intended entry point, then repeat acceptance testing.

Before running scripts under `workflows/`, parameterize hard-coded paths, object IDs, and output locations. Verify the active document and permitted model changes. Obtain authorization before using tools that build, save, or delete geometry.

## Validation levels

1. Standard-library synthetic tests for snapshots, object identity, poses, and mock COM.
2. Offline MCP protocol tests for tool registration and error behavior.
3. Live Windows CATIA tests for reference ownership, coordinate transforms, geometry, and native interfaces.
4. End-to-end R30 intranet acceptance for licensing, dependencies, performance, data boundaries, and reporting.

Live CATIA and intranet acceptance require their own validation. The repository curation involved no live model operations.
