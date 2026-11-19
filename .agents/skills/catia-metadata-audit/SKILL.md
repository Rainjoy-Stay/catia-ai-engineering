---
name: catia-metadata-audit
description: Check part numbers, revisions, descriptions, names, materials, references, and assembly records. Report gaps and propose verifiable, authorized edits.
---

# Metadata and delivery preflight

Read the shared operating rules in [Everyday CATIA operations](../../../docs/CATIA_DAILY_OPERATIONS.md). Discover the structured CATIA tools registered in the current session and verify their contracts. Follow the available `catia-model-understanding` skill for model operations, or use the documented minimum read-only workflow if it is unavailable. Consult the current paired-view skill when the user requests images.

## Natural Language Entry

- "Check whether part number, file name and description are empty or inconsistent, and do not change it."
- "Figure, repeat part number and version inconsistent against this approval BOM."
- "Change parameters to this map table to list specific objects and old new values. ".

## Implementation

1. Defines the source of the rule and the scope of the readout first; only missing, colliding and manifestly inconsistent business rules are reported when no naming criteria exist, and no business rules are created. A tree list is used to distinguish definitions from examples, and a version/description/material is reported without reading NOT_READ, which is not judged to be non-compliant by empty value.
2. Retains the original field and regularized values compared to the authorized BOM/map; Part number zero, case, full half and spaces are price equivalents determined by the rules and are not rewrited. Distinguishing between duplicate installation, different versions of part number and definitions of part number.
3. Default read-only for the delivery review; no Update, link fixation or Save is called for check in state updates, references to solvency, materials and parameter units. Record when reading a cache/light expression limit without automatically loading all large packages.
4. When changes are authorized by the user, the gentleman becomes the precise object, the field, the old value, the new value, the expected type/unit and the relying impact table; the old value is read again before execution, the change skips to STALE_INPUT. Only the type-writing tool that is actually supported is used to modify and read back; PartNumber/Revision/Description is not assumed to be written because normal parameters can be written.
5. Do not expand the "read-only inspection" request to a batch correction. Writing parameters need to consider the formula driver, unit and downstream dependence, fail to preserve the result-by-product and recoverable; do not claim that multiple COMs are written to atomization. Preservation is determined by the explicit authorization in the user task.

## Acceptance and delivery

Output metadata-findings.csv; change-plan.csv, writeback-results.json, if authorized. Contains rule source, object evidence, state, old new values and unprocessed reasons. The change is not equal to implemented candidate, and the update is not equal to satisfactory project.
