---
name: catia-revision-diff
description: Compare two CATIA revisions for structural, metadata, pose, and verified geometry changes. Report additions, removals, modifications, and unmatched objects.
---

# CATIA revision comparison

Read the shared operating rules in [Everyday CATIA operations](../../../docs/CATIA_DAILY_OPERATIONS.md). Discover the structured CATIA tools registered in the current session and verify their contracts. Follow the available `catia-model-understanding` skill for model operations, or use the documented minimum read-only workflow if it is unavailable. Consult the current paired-view skill when the user requests images.

## Natural Language Entry

- "Comparison versions A and B, add or delete to the list and list separately the changes in the location of the installation."
- "When this part is resized, which pieces have been resized and which are simply repositioned?"
- “As opposed to the two supplier assembly according to the approved part number mapping, do not mix the duplicates.”

## Implementation

1. Ties a clear prefore/after document or snapshot to record the range of collection, root coordinate, unit, model version and read-over. The same name of the two files still records the full source separately. Do not overwrite existing unsaved documents; opening the second edition would create a conflict with the same name, using an independent CATIA session or split collection, without changing/restoring the source file.
2. Priority is given to matching the PLM stabilization mark or the approved case map; it is followed by generating candidates such as " Parent matching + part number + instance properties" and retaining the basis. The same name, reordered index, snapshot OCC ID and volume signature do not independently constitute cross-version matching. Multiple pairs of multi-conflict columns AMBIGUOUS do not fit strongly. The byte hash documents are the same.
3. Compared ATTRIBUTE_CHANGED, PLACEMENT_CHANGED, GEOMETRY_CHANGED, RENAMED, RERARENTED.pose compares by a consistent coordinate system; the movement of the world coordinates is not reported when the root is unknown, allowing reporting of local variations comparable to those of the patrilineal family. The horizontal and rotational differences are recorded separately.
4. Geometric changes must come from primary geometry of the same range, argument/characteristic evidence or validated geometry. Characteristic tree changes do not change the shape of the result; shapes are similar or do not represent the history of the parameters. Size and area change cannot prove geometry; no output GEOMETRY_NOT_EVALUATED is measured.
5. Keep UNMATCHED/UNKNOWN only when the matching policy is sufficiently supported for another version. Different versions can change the matching key, and not "part number + version must be the same " directly to make additions or deletions.

## Acceptance and delivery

Deliver `differences.csv`, `matching.json`, and `comparison-summary.json`. Include before and after paths and evidence, the match basis, changed fields, old and new values, method, tolerance, and status. Allow multiple change labels per object. Summarize matched, ambiguous, and unevaluated proportions.

The current snapshot. compare_snapshots only reports whether the capture structure is identical and whether the evidence is invalid, and there is no cross-version mapping and geometric discrepancy detection. It is not possible to package its CHANGED_REQUIRES_REBINDING as an addition or deletion list. If there is no matching or comparison tool, deliver the identifiable parts and gaps and do not make up the result.
