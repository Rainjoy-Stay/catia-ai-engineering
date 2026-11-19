---
name: catia-native-inspection-word
description: Inventory open STEP or CATPart geometry, reconstruct an in-place inspection assembly, verify interference using native DMU, GSD, and SPA, capture paired locator and transparent detail views, and deliver a portrait A4 Word report.
---

# Native CATIA inspection from STEP to Word

Work from a STEP or CATPart already open in CATIA, or an existing in-place inspection assembly. Use the scope of the current request. Treat historical reports, thresholds, IDs, and captures as workflow references. Confirm the active document, provenance, assembly hierarchy, save state, and current CATIA capabilities. Use the available `catia-model-understanding` skill for model identification and safe operations, `../catia-spatial-inspection-report/SKILL.md` for geometry verdicts, and `../catia-native-dual-view/SKILL.md` for screenshots. This skill coordinates reconstruction, inspection, and delivery, including acceptance at each stage.

## Inventory and in-place reconstruction

1. Record the active source inventory and save state. Distinguish a real CATProduct assembly from a single CATPart containing multiple Bodies or geometrical sets. Inventory all identifiable solids, bounded surface shells, other surfaces, and curves. Record unique source paths, original names, types, areas or volumes, centroids, bounding boxes, units, and hashes when available. Include bounded surface shells with zero volume.
2. For an assembly that supports component-level inspection, verify component identities and references. For independent geometry in a single CATPart, build a **separately saved derived inspection CATProduct**. Copy each uniquely mapped solid or bounded shell to its own CATPart and insert it at the original coordinates. Record source Body count separately from native assembly part count. The derived assembly preserves placement. Original supplier constraints, names, design intent, and feature history remain unknown. Leave the source model intact.
3. Map each derived instance's stable ID to its full source path, geometry type, and derived CATPart and instance names. After copying, read back SPA area or volume, centroid, bounding box, and placement. Verify units and assembly transforms. Record failures, degeneracy, unavailable finite area, and nonunique mappings as coverage gaps. Use verified evidence for mapping.
4. Reconcile total source entries with verified derived instances plus excluded or pending entries. List solids and shells separately. Verify copying, transforms, and measurements on a small sample before batching. Log progress and maintain recovery records. Save only authorized derived artifacts and read the source document's `Saved` state before and after.

## Inspection and screening

1. Start a new run record against the accepted inspection assembly. If reviewing existing native DMU results, record their source and settings. If the user requests a rerun, calculate from the current model.
2. Run the native DMU interference check appropriate to the scope, such as Between All. Preserve settings, raw results, any truncation, and the count of unique unordered object pairs. Deduplicate by unordered pair and use native results for candidate screening and location. Record thresholds and their sources. Screening values alone establish neither exact common volume, surface penetration, nor allowed interference. Include only the requested clear solid interferences and surface penetrations in the main issue list. Track contacts, small clearances, and insufficient evidence in the scope and unevaluated audit.
3. Verify solid candidates with exact common volume and applicable SPA or native measurements. Record values, units, tolerances, and success or failure. For surface shell candidates, use GSD intersection curves and independent evidence such as material entering both sides to distinguish penetration, edge contact, and coplanarity. An intersection curve alone does not establish penetration. Match verdicts to the evidence available.
4. Link each confirmed issue to unique A/B objects, the native candidate ID, measurement evidence, screenshot queue entry, and report ID. Keep unresolved or ambiguously mapped candidates as unevaluated. Record the limitation and next action.

## Native screenshots

Accept a small set of real captures with `catia-native-dual-view` before batching. Preserve the native overview and detail images and their camera and display records for every issue. **Use the same canvas and embedded sizes. Show the complete assembly and run Fit All In in the overview. Isolate A/B and run Fit All In on the pair in the detail. Use the same orientation by default.** Color A orange and B cyan. Use red boxes to locate the objects.

If one part obscures the other, adjust the occluding part's transparency so the other part and their relationship are visible. Preserve color and outline and record the actual setting on the issue page. Inspect the capture before acceptance. Adjust the angle or add a native view if needed. Record the display, camera, and active document before capture. Restore and verify afterward, using recorded state after an interruption.

## Portrait A4 Word delivery

Default to an editable portrait A4 `.docx`. State scope, confirmed counts, and screening criteria on the cover. Explain the difference between DMU candidates and confirmed geometry in the method section. Link the issue overview to its individual pages. Use one page per confirmed issue with A/B identities, evidence and units, relevant limitations, and equal-size overview and detail images. Label changes to detail transparency or orientation on the affected page. Use a caption such as “Red boxes locate the objects. The exact interference boundary is not shown.” Follow any format or layout requested for the current run.

Render the Word document. Check portrait A4 page size and page count, image-to-issue alignment, equal image sizes, complete model and targets, correct locator boxes, readable transparent views, and text clipping. Correct issues before delivery. Preserve raw and annotated images, measurement and mapping indexes, and display restoration records. Report only completed checks. The existing `tools/build_word_report.py` is a layout reference for the October 13, 2026 run and contains hard-coded paths and counts. Adapt it to current run data before reuse.
