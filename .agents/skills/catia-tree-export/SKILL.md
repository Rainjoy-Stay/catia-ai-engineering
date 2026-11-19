---
name: catia-tree-export
description: Export CATIA hierarchy, instance paths, part numbers, revisions, descriptions, and quantities with field provenance and read coverage.
---

# Product tree and BOM export

Read the shared operating rules in [Everyday CATIA operations](../../../docs/CATIA_DAILY_OPERATIONS.md). Discover the structured CATIA tools registered in the current session and verify their contracts. Follow the available `catia-model-understanding` skill for model operations, or use the documented minimum read-only workflow if it is unavailable. Consult the current paired-view skill when the user requests images.

## Natural Language Entry

- "Forcing the current whole structure tree into a list that Excel can open, with hierarchy, path, part number, version and description."
- "Export only the lower three stages of the attachment box, aggregated by part number and version."
- “List all installation locations of the same component and do not treat examples as different parts.”

## Implementation

1. The solver/specify the sub-tree, maximum depth, root content, example detail or part aggregation, format and output position. When the user does not specify the full readable level, example breakdown and UTF-8 BOM CSV of the current active document; JSON is saved as evidence. Use the available table skills for real xx without changing the extension.
2. Defines and examples with document information, model model method and registered structure reading ability. A path is indexed using the original subnode; the path is maintained with paragraph names and indexes to avoid being overwritten by the same brother. Priority is given to a snapshot of the independent understanding module; versions and descriptions are not captured by the module and must be read and supplemented by the validated properties, otherwise marked as NOT_READ.
3. Output per line snapshot_id, occurrence_id, parent_id, level, instance_path, instance_name, definition_reference, part_number, revision, description, source_document, read_status, evidence_ref. Root level is 0. Differentiating nodes is missing, fields are empty strings, properties are not supported and read failed.
4. A multiple example shows the details separately; aggregate priority is given to the validated definition identity and version. Only part number is used to disclose potential collisions, without a silent combination of references to part number. Statistics on the number of direct sub-items and the number of expanded leaves are given separately; no serial number is used as a permanent identity.
5. The CATPart Body/ Curve List output geometry_inventory separately, indicating that it is not a assembly BOM; it does not assume the supplier part number from geometry.

## Acceptance and delivery

Verify the root, target subtree, and sample paths. Report expected and read node counts, depth truncation, unloaded references, failed rows, and aggregation criteria. Protect external names and descriptions from CSV formula injection and preserve original values in JSON. Keep missing values and revisions unknown. Deliver `tree.csv`, `tree.json`, and `summary.json` with a completeness statement. Leave the model unsaved.
