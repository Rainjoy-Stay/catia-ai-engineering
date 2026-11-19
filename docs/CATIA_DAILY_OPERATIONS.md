# Everyday CATIA operations in natural language

Added November 12, 2026. These skills document agent workflows using existing capabilities. They add no CATIA MCP endpoints, buttons, or geometry algorithms. Acceptance on a live model remains pending. Execution depends on the tools registered in the target deployment, the CATIA version, and the available license.

## Workflows

| Task | Skill | Example request | Current coverage |
| --- | --- | --- | --- |
| Product tree and BOM export | [catia-tree-export](../.agents/skills/catia-tree-export/SKILL.md) | Export the current assembly tree with hierarchy, instance paths, part numbers, revisions, and descriptions. | Structure, instances, and part numbers are readable. Read revisions and descriptions separately. The agent converts the results into tables. |
| Revision comparison | [catia-revision-diff](../.agents/skills/catia-revision-diff/SKILL.md) | Compare these two revisions and list additions, removals, attribute changes, and changes in installation pose. | The current comparison covers captured structure only. General cross-revision matching and geometry diffing remain unimplemented. |
| Provenance and receipt chain | [catia-model-provenance](../.agents/skills/catia-model-provenance/SKILL.md) | Document provenance, receipt records, and the conversion chain. Flag gaps in the evidence. | File and reference facts can be collected. Supplier and receipt claims require authorized external records. |
| Feature and duplicate-part search | [catia-search-duplicates](../.agents/skills/catia-search-duplicates/SKILL.md) | Find all brackets and flag possible duplicates by volume and surface area. | Name search, feature and parameter reads, and part inertia tools are available. Batch signatures and exact shape matching are not standalone services. |
| Measurement summary | [catia-measurement-summary](../.agents/skills/catia-measurement-summary/SKILL.md) | Summarize volume, area, mass, and center of gravity. List parts with missing materials separately. | Native measurements depend on the object. Mass depends on density. Check units, scope, and pose before aggregating. |
| Locate and isolate | [catia-display-review](../.agents/skills/catia-display-review/SKILL.md) | Locate this part, isolate it temporarily, and restore the original display. | Selection and visibility are available. Full restoration of color, transparency, and camera requires tools that can read and restore those states. |
| Batch format export | [catia-batch-export](../.agents/skills/catia-batch-export/SKILL.md) | Export these parts to STEP and provide a file verification manifest. | Single-document export exists. Validate batch orchestration, translation licensing, and reimport checks on site. |
| Metadata and delivery preflight | [catia-metadata-audit](../.agents/skills/catia-metadata-audit/SKILL.md) | Check the BOM for missing items and revision mismatches. Produce findings for review before making changes. | Parameter and structure reads exist. Revision, description, material, and PLM access depend on the deployment. Writes are limited to supported fields. |

## Shared operating rules

1. Resolve the task, exact document or subtree, input revision, output format, and destination. Default to read-only, the readable scope of the active document, and a new output directory. If a comparison has only one revision, capture that baseline and request the missing revision. A copy of the current model cannot serve as the other revision.
2. Discover the available structured tools and obtain document information and a manifest or model-understanding snapshot. Record the name, type, full path or `SESSION` for unsaved documents, `Saved` state, `snapshot_id`, scope, method, units, and coordinate frame. Distinguish definitions from instances. Resolve duplicate names by path. Enumeration numbers do not establish cross-revision identity.
3. Look for `catia_list_documents`, `catia_get_active_document_info`, `catia_get_model_manifest`, `catia_get_part_geometry_inventory`, `catia_search_elements`, `catia_get_feature_details`, `catia_get_parameters`, `catia_get_inertia`, `catia_measure_distance`, `catia_select_elements`, `catia_set_visibility`, and `catia_export`. Check the actual input and output contracts before use. A documented tool name is a discovery hint, and registrations vary by package and session.
4. The standalone entry point is `tools/understand_model.py`. The MCP source is `model_understanding_workbench/mcp_tools.py`. Coverage includes structure, part numbers, definitions and instances, poses, and snapshot queries. Revision, description, native topology, mass, duplicate matching, receipt chain, and cross-revision mapping are outside scope. The CLI uses the same reader and runs locally. Deployment of the MCP service is separate.
5. Use the available `catia-model-understanding` skill for model operations. If unavailable, bind the exact document, capture read-only evidence, record results per object, and report failures and coverage. Avoid substituting generic desktop clicks or arbitrary COM writes. Document the required read or write interface and acceptance criteria when a tool is absent. Report partial completion.
6. Deduplicate definition reads, batch work within the tool budget, and report truncation. Counts must include at least `expected`, `read`, `failed`, and `omitted`. Preserve `UNKNOWN`, `NOT_READ`, `UNSUPPORTED`, `READ_FAILED`, `AMBIGUOUS`, and `NOT_EVALUATED` as distinct outcomes. Unread data and unmeasured values remain unknown.
7. Default to portable CSV and JSON. Emit CSV with a UTF-8 BOM and standard quote escaping. Protect imported text from Excel formula interpretation when it begins, after leading whitespace, with `=`, `+`, `-`, `@`, or a control character. Preserve the original in JSON and keep numeric columns typed. Use the available spreadsheet skill for genuine XLSX workbooks.
8. Reads and exports leave the source document untouched. Avoid `Save`, `SaveAs`, `Update`, relinking, geometry repair, and renaming. Restore temporary selection and visibility at the end unless the user asks to keep them. Limit changes to states that can be restored. Export into a new directory to avoid collisions and overwrites.
9. Evidence must include the object path, snapshot, original values, read method and status, and applicable scope. Distinguish filesystem facts, model claims, measured values, and engineering interpretation. Record missing provenance, revision, and standards evidence as gaps. Numeric signatures do not prove persistent identity or interchangeability.
10. State what completed, what remains, failed objects, data coverage, and whether a model was saved. Complete necessary authorized steps without requesting the same authorization again. External transmission, batch replacements, deletion, and model saves require their own authorization.

## Suggested output fields

- Envelope fields are `schema_version`, `task`, `captured_at` with time zone, `source_documents`, `snapshot_ids`, `scope`, `coverage`, `units`, `coordinate_frame`, `methods`, `limitations`, and `artifacts`.
- Inventory rows contain snapshot-scoped `object_id`, `occurrence_path`, `definition_reference`, `evidence_ref`, `read_status`, and `values`. Use `field_status` to distinguish a missing read from an empty value.
- Diff rows contain `before_ref`, `after_ref`, `match_basis`, `match_status`, `change_types`, `field`, `old_value`, `new_value`, `tolerance`, and `evaluation_status`. `ADDED` and `REMOVED` require complete coverage in the other revision. Keep ambiguous candidates outside those counts.
- Signature rows contain `definition_ref`, `closure_status`, `volume_mm3`, `area_mm2`, `method`, `tolerances`, `candidate_peer`, and `verification_status`. List open surface groups separately from closed solids.
- Provenance edges contain `from_artifact`, `to_artifact`, `event_type`, `event_time`, `record_ref`, and `verification_status`. Receipt and conversion edges remain `UNVERIFIED` without records.

## Manual checks

- Three instances of one part produce three tree rows, one definition measurement, and a quantity of three. Avoid double counting the root assembly and the instances.
- Keep sibling indices in paths for duplicate names or reordering. Across revisions, return `AMBIGUOUS` when identity cannot be established.
- An unloaded reference in one revision leaves additions or removals unresolved for the corresponding item.
- Different shapes with the same volume and area remain duplicate candidates pending exact shape evidence.
- Exclude open shells and missing-density items from applicable valid solid volume or mass totals. Preserve the missing or inapplicable status.
- The SHA-256 of an on-disk file covers only those bytes, even when an unsaved model is open in memory.
- Without a receipt record, report file facts and receipt-chain gaps. Leave the supplier and receipt time unknown.
- If display state cannot be read, limit the action to reversible operations. Showing all objects after hiding them does not restore the previous state.
- Protect formula-like names in CSV and keep the original in JSON. Sanitize names before using them as output paths.
- Preflight requests produce findings without writing parameters or saving models.

These are manual acceptance criteria. See `daily-skills-validation.json` for skill format and link checks. Live CATIA automation remains unverified.
