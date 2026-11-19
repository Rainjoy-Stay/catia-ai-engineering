---
name: catia-native-dual-view
description: Capture and validate native CATIA overview and detail images for interference reports. Use equal-size views, Fit All In on the complete model for the overview, and Fit All In on the isolated interference pair for the detail. Covers screenshots, transparency, visibility, locator boxes, and display restoration.
---

# Equal-size native CATIA views

These requirements were confirmed on October 13, 2026. Follow the user's instructions for the current run when they supersede this guidance. Use the current model's object IDs, captures, and review decisions.

## Framing and layout

- **Use equal-size images. Show the complete inspection model and run Fit All In for the overview. Hide all objects outside the interference pair and run Fit All In on that pair for the detail.** The overview must cover the complete model.
- Use the same isometric orientation by default. The overview must show the model outline and target location. Both parts must fit in the detail, with the interface visible. If occlusion or a degenerate projection obscures evidence, adjust the detail angle, record the reason, and add a native view or section if needed.
- Use orange RGB(255, 161, 56) for A and cyan RGB(31, 214, 224) for B. Both are opaque by default. Use light gray RGB(185, 190, 198) at about 20% opacity (52/255) for surrounding geometry in the overview. If needed, lower only the occluding part's opacity to 30–50% in the detail and record the actual setting.
- Default to a landscape A4 issue page unless the current report specification says otherwise. Match the two original canvas sizes and embedded sizes. Preserve aspect ratio and retain all relevant geometry.

## Capture procedure

1. Confirm the document, real names and paths for A and B, object types, and measurement source. Follow the available `catia-model-understanding` skill for model operations. Describe Body-level location at its actual resolution.
2. Prefer a separate inspection copy. Record affected objects' visibility, colors, opacity and inheritance, plus the camera, rendering mode, selection, active document, and `Saved` state. Test one change and read it back to identify which level controls the visible geometry.
3. **Color only actual solids and surface shells.** Exclude default planes, axes, empty Bodies, and other helpers from coloring and locator boxes. Record and restore any helper visibility changes. Read back the reference geometry to verify that a component-level change reached it.
4. Set up the full model, clear selection highlights, refresh, and run Fit All In. Save the raw overview and camera. Hide non-target objects, refresh, and run Fit All In on A and B. Save the raw detail and camera.
5. Place locator boxes using a reliable object projection, same-camera selection differencing, or projected measurement locations. Record the viewport, target region of interest, and exclusions for UI and helper elements. Reevaluate them when the view changes. A red box locates the object only.
6. Inspect both images. Verify object identity, complete model context, only A and B in the detail, complementary framing, legible colors and interfaces, and locator boxes free from planes, axes, the tree, or compass. Accept a small set of real captures before processing the full batch. Exclude rejected images from the report.
7. Restore and verify state in `finally`, including helpers, camera, selection, and active document. After an interruption, restore from the recorded state. Report any source `Saved` state change without saving the source to suppress it.

## Gaps and delivery

Keep any item with ambiguous mapping, missing display readback, unreliable locator boxes, or unresolved occlusion in the queue as `NEEDS_REVIEW`, with the action needed to finish it. Use only current evidence and leave unsupported boxes empty. Geometry verdicts come from the current native DMU/GSD/SPA checks.

Consult the [execution guide](references/execution-guide.md) as needed for the complete queue, index fields, scripts, and exception handling. Previously unsuccessful experiments require validation before use.

Render the report and check image sizes, completeness of the geometry, and caption legibility. Keep raw and annotated images, camera and display records, hashes, and restoration results. Report only completed checks and acceptance steps.
