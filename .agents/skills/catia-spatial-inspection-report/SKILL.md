---
name: catia-spatial-inspection-report
description: Rerun bounding-box inspection on an existing CATIA model, import solids and surface shells, display live progress, and deliver paired-view interference reports with AI review of unevaluated items.
---

# CATIA bounding-box inspection and reporting

Use the region, object scope, and verdict criteria from the current request. Follow the available `catia-model-understanding` skill for CATIA reads and writes. This skill specifies result semantics, UI behavior, and report acceptance.

## Scope and fresh run data

- Confirm the active document, source file, save state, and structure inventory. Record the number of Bodies in a single CATPart separately from native assembly part count.
- For a rerun, create a separate run directory and export from the current geometry. Preserve the source hash, export audit, scope, object names, and source paths. Measure again for the new run.
- Select the agreed scope with the bounding box and include valid solids and bounded surface shells. Record inventory, export, unique name mapping, and spatial selection counts, plus any gaps. Include shells with zero volume. Keep ambiguous source mappings unevaluated and identify objects from evidence.
- Follow the current tool authorization for cache deletion. Use an independent run directory for isolation. Report any earlier cache as deleted only when deletion is verified.

## Calculation and verdicts

- Reconcile the unique unordered pair count with the complete combination count. Track bounding-box exclusions, exact calculations, completed pairs, failures, and retries. Record engineering rule coverage independently of geometry calculation completion.
- Display the recorded verdicts consistently. The user removed relaxed mode and its minor-overlap override.
- Fail geometric interference when the exact common volume of valid solids exceeds the stated numerical tolerance. A previous run used 1e-6 mm³ as its numerical tolerance. Establish tolerance independently of any engineering limit. Review allowed design fits separately and preserve confirmed overlaps even when the design purpose is unknown.
- Surface shells have no solid volume. Distinguish boundary contact, coplanarity, interior crossing, and evidence of penetration on both sides. An intersection curve alone is insufficient proof. Leave invalid or unsupported cases unresolved.
- Preserve a bounding-box exclusion when it has a traceable lower-bound distance calculation, even if an exact pairwise measurement is unavailable.
- Use the recorded `geometry_kind` to choose the solid or shell evaluation path. A `surface` dictionary alone cannot determine the type.
- Treat unapproved values such as 1 mm as screening thresholds. Engineering compliance requires an approved clearance rule, connection basis, or documented exemption.
- When the user delegates clearance selection, document the basis for each applicable type, connection, function, and requirement. The referenced run allowed clearance and zero-common-volume contact to pass and allowed a single open plane to pass. These are run-specific exceptions and do not automatically cover solid overlap or ambiguous interior shell intersections.

## UI and delivery

- Identify tubing by a uniform scan of the model geometry. Include multi-segment sweeps, spline surfaces, and tubular regions joined to fittings within composite Bodies. A fitting, capped export, or absent cavity can coexist with tubular geometry. Keep excluded non-tubing objects out of the report and screenshot package. Retain exclusions in the audit as needed.
- Use geometric evidence to exclude solid pins, bolts, rods, and discs. A cylinder or axis alone does not establish tubing. An imported bent form can qualify as a tubular region without a cavity, while flow passage, wall thickness, and engineering function remain unconfirmed. Measure bend radius from a reliably reconstructed centerline. A local fillet or toroidal support surface is insufficient. Mark radius unevaluated when the route is unavailable. [Tubing recognition guide](references/model-piping-recognition.md)
- Show only current-run objects, real active pairs, and actual concurrency. When processing ends, reset the active window to zero and retain results, gaps, and report download.
- Reconcile grouped UI totals with JSON, CSV, and the report. Distinguish geometry failures from pending engineering review. Display identifiable names, source paths, measured values, units, and reasons.
- Follow the [native paired-view skill](../catia-native-dual-view/SKILL.md) for equal-size images. Fit the complete model in the overview and the isolated interference pair in the detail. Use the same orientation by default. This supersedes older neighborhood and unequal-size guidance. For AI review, see the relevant section of the [capture and review guide](references/capture-and-review.md).
- Render the rebuilt PDF or Word file and inspect affected pages. Verify that the download matches the local deliverable. Report validation only for inspected items.
- When updating an intranet package, verify the actual call chain and test the relocated installation. A successful run in the development workspace does not establish offline package acceptance. [Portable release guide](references/portable-release.md)

## Reference entry points

Historical implementation references under `tools/` include `complete40_pair.py`, `complete40_monitor.py`, `complete40_report.py`, and `fresh40-ui/`. Validate and parameterize the historical scope and output paths before use. Replace run-specific dates, model names, and hashes.

`review40_pending_ai.py` serializes judgments already completed in that session. Reviewing a new model requires current evidence and a new assessment.
