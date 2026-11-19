# CATIA AI Engineering

Model understanding, tubing and spatial geometry inspection, agent workflows, and evidence reporting for CATIA V5.

This repository contains a curated source snapshot from the development workspace, dated November 12, 2026. Supplier models, derived assemblies, actual case screenshots and reports, the corporate runtime environment, and offline binary dependencies were excluded. The original workspace and its Git staging area were preserved when the snapshot was prepared.

## Capabilities and validation status

| Module | Current capabilities | Validation limits |
| --- | --- | --- |
| Inspection baseline | Bounding-box inspection, geometry, rules, and reporting modules, and CATIA MCP | Based on the October 12, 2026 release. End-to-end acceptance on the corporate R30 intranet remains pending. |
| Native inspection workflow | STEP inventory, in-place reconstruction of inspection assemblies, DMU/GSD/SPA checks, paired views, and reporting | Case scripts retain hard-coded paths and object IDs. Adapt them before using them with other models. |
| Read-only model understanding | Product structure, definition/instance distinction, recursive rigid transforms, snapshots, and evidence queries | Validated with synthetic data and mock COM. Full native topology and engineering function recognition remain unimplemented. |
| AI orchestration | MCP tools, workflow skills, and interchangeable language model adapters | AI interprets results and orchestrates workflows. Deterministic checks and native tools supply geometry verdicts. |

The modules have yet to pass acceptance as a unified one-click product. Research code, case scripts, and planned work have separate maturity levels from production features.

## Repository layout

- `inspection/` contains the inspection source and preserves the package's relative `project/`, `scripts/`, and `vendor/` layout. The runtime is excluded.
- `model_understanding_workbench/` contains the standalone read-only model understanding module and its tests.
- `tools/` contains the model understanding CLI, standalone MCP launcher, and validation entry points.
- `workflows/` contains native inspection and in-place reconstruction case scripts for development reference.
- `.agents/skills/` contains documented agent workflows.
- `docs/` contains curation notes, historical requirements, reporting requirements, and the source manifest.

## Quick validation without CATIA

Run this command from the repository root with Python 3.12.

~~~powershell
python -m unittest discover -s model_understanding_workbench/tests -v
~~~

To validate the MCP protocol, install the dependencies and run the protocol check.

~~~powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-understanding.txt
.venv/Scripts/python.exe tools/validate_understanding.py --output output/understanding-validation-001 --protocol
~~~

Use a new output directory for each run. Acceptance on a live CATIA installation and engine model remains a separate step.

## CATIA model understanding

Use Windows, a valid CATIA V5 license, and a running CATIA instance registered with COM. Open the model to inspect, then run the applicable entry point.

~~~powershell
.venv/Scripts/python.exe tools/understand_model.py capture --output output/capture-001
.venv/Scripts/python.exe tools/start_understanding_mcp.py
~~~

This standalone entry point reads the currently open model and leaves opening, updating, and saving to the operator. See the [module documentation](model_understanding_workbench/README.md) for data coverage and reference limits. Offline runtime paths in the original module documentation refer to the source workspace. Use the virtual environment above in this source repository.

See [setup and validation](docs/SETUP.md) for inspection software installation and limitations.

## Operating limits

Inspection defaults to read-only operation. Obtain separate authorization before modifying or saving a supplier model, creating a derived inspection assembly, or running modeling experiments. Record unknown data as `UNKNOWN` or `NOT_EVALUATED` and exclude it from passing results. Engineering rules require an approved basis. Example thresholds do not establish aviation compliance.

Follow the root `AGENTS.md` and current screenshot skill for paired views. Use equal image dimensions and the same orientation by default. Fit the entire visible model in the overview, then isolate and fit only the interference pair in the detail view. Conflicting screenshot rules in older documents are historical.

## Provenance and licensing

`docs/source-manifest.json` records the source and pre-curation checksums for the inspection baseline and case code. See the curation notes for subsequent documentation and configuration changes. Third-party CATIA MCP derivatives retain the upstream MIT license. [Third-party notices](THIRD_PARTY_NOTICES.md)

Project-owned code and documentation are available under the [MIT License](LICENSE). Third-party components retain their own licenses and notices.

## Everyday natural-language workflows

Eight skills cover product tree and BOM export, revision comparison, model provenance, feature search and duplicate candidates, measurement summaries, display isolation and restoration, batch export, and metadata and delivery preflight. They use existing MCP capabilities. Complete revision matching, exact geometric equivalence, and proof of receipt still require additional tools or evidence. [Everyday CATIA operations](docs/CATIA_DAILY_OPERATIONS.md)

## Local release maintenance

On November 12, 2026, local package verification covered dependencies, 149 MCP tools, 550 offline regression tests, 6,035 release file hashes, and UI startup. Model understanding also had 32 tests and protocol validation. CATIA could not be attached, so live acceptance remains pending. Cleanup targeted only redundant extracted copies whose archives had been verified, preserving the MCP in use and referenced versions. The full runtime is excluded from GitHub, and the local launchers apply only to the documented local layout. [Maintenance record](docs/LOCAL_MAINTENANCE.md)
