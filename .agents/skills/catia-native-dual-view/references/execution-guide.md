# CATIA Dual-Specific Cross-Specific Mapping and Reporting Harmonization of Norms

Version: 2026-10-13. Applies to the original CATIA check screenshot and report.

This version of the General Dual-Specific Script Script 04_ Double-Specific Script Progressive Operation and Project Script Requirements, which combines the desktops, uses the user's definition of this confirmed view. The original document is retained and this version serves as the uniform basis for the implementation of this full-scale inspection of the screenshot and the report.

## 1 Fixed Requirements

** Two figures are large, except for changes in display range and view: Fit All In after overview shows the complete model; detail view hide objects other than inference level fit All In**.

| Item | Holistic Map | Local Details |
|---|---|---|
| Show Object | Complete check the entities in the model and limited numbers | Current reference level A/B |
| Background | Other objects are grey, about 20% opacity | Hide all non-target objects |
| Objective | AOrange, B-Cyan, completely opacity by default | Keep the same A/B and colour as overview |
| View | Set All In | Execute Fit All In for all of A/B when non-target objects are hidden |
| Observation direction | Default Axis Side | Default corresponds to overview |
| Images and Report Dimensions | Same as detail view | Same as overview |

A complete overview may not be replaced by a “maximum area object” or a local neighbourhood for the “most recent 24 objects”; targets may not be selected to keep other objects visible, but local isolation is claimed to have been completed.

The difference between the two diagrams should really come from the field of view that shows the range and the camera adapt. It is forbidden to repeat the layout with the same image. Overview must be able to identify the profile of the model and the location of the target, and detail view must be able to identify the parties and the interfaces.

The default report is in the A4 horizontal format; each page, overview and detail view uses the same painting, the same embedded width, and keeps objects, measurements, classifications and suggestions. Images, etc., are placed in scale, do not stretch and do not artificially make the "big map, small position map".

## 2 Conflict resolution in this edition

| Different statements in the original information | This unified result |
|---|---|
| Large detail view plus small overview, recommended A4 vertically | Not used; two figures are large, following A4 horizontal |
| Overview Limit Relevant Neighbourhoods | Not; after a complete check of the model display Fit All In |
| Force two different observation directions | Not forced;defaults in the same direction, displaying different ranges and horizons |
| Yellow, red, green, blue. | AOrange RGB (255,161,56), B Cyan RGB (31,214,224) |
| Full Image Scan, Central Bottom Box | Not used; limiting view and target areas, excluding interfaces and auxiliary geometry |
| Universal script is considered accepted and accepted when it is completed | Not used; real pictures must be checked and recovery results shown |

If there is a mask, degradation or projection overlap in the same direction, the local direction can be reoriented and the cause recorded; the third real detail view or CATIA cross-section is still not visible. The correct overall/local display range cannot be replaced by a different direction.

## 3 Intercept Queue and Object Identity

1. Creates a full queue from this structured result, covering FAIL, Warn, REVIEW, NOT_EVALUATED and the searchable ERRO; the normal connection or exemption cases required are listed separately.
2. No geometric object’s environmental error keeps logs and environmental evidence and does not forge geometric maps.
3. Each record is Issue ID, A/B object, real tree name, parent, complete path, type, carrying body/face and corresponding measurement evidence.
4. When a name is repeated, use the full example path or index for the current round to re-register. The index can only be used for the current model and the current tree structure, and history numbers cannot be used.
5. In CATPart, Body does not amount to the assembly of parts. Face, open surfaceshells, examples of components and Body are recorded separately and the background location of Body cannot be described as a precise face location.
6. The identity of the target is not determined by the number of candidates or by the physical appearance of the route; the route identification queue and the interference queue are registered separately.
7. The full result cannot be interrupted by the first 20 limits of the script default. The uncut item retains the number and cause, and the report is marked as incomplete.

## 4. Showing the transaction and correct control level

Priority is given to independently checking the copy screenshot, without preserving the supplier source model. Pre-operational records: original active document, selection, display/hidden, true colour, opacity, colour and transparency succession, camera origin/vision/up, scaling, projection, rendering mode and Saved state.

CATProduct layers, references to CATPart, Body, and final geometric features may be inherited differently; changes to component nodes cannot assume that the entity has become the target colour.

** Colours are given only to the actual entity or surface shell, and does not colour the satellite objects such as the default base plane, coordinates, empty Body, etc. ** The auxiliary object influences the viewing or label, and is recorded as its identity and original state, hidden and restored at the end.

Slightly background RGB (185,190,198). Untransparent default 52/255; target default 2255.52 indicates that about 20% is not transparent, not 52% transparent. The historical COM SetShow (0) is a display, SetShow(1) is hidden; the MCP uses the boolean value and does not mix polarity.

Undefined or mixed display properties may not be treated as uniform values. Groupings are allowed to be saved/restored only if the state returns clearly proves consistent; otherwise, object-by-object records are recorded.

## 5 Overview Operations

1. Check this activity document against A/B identity.
2. Displays the entities in the complete check model with limited surface shells; the necessary parent levels are also displayed.
3. Non-target objects are set to be grey and about 20 per cent non-transparent; A/B maintains the display as non-transparent oranges/greens.
4. Hides the registered non-physically assisted plane, coordinates or zero area support elements, without missing the actual limited entity and surface shells. Non-detectable objects cover the gap in a separate column and are not considered to pass the check.
5. Clears the temporary selection of highlight, refreshing the view, setting the side of the axis or the confirmed direction of this item.
6. Execute Fit All In; physically check if the complete model is painted, if the location reference is clear, if A/B is visible.
7. Keep original maps and camera records, and generate position indications.

Overview should not be isolated in an empty background. If the target under the complete model is small, the location box is used to indicate its location; the detailed relationship is covered by a large detail view, which does not readily hide the remote actual parts changing overview definition.

## 6 detail view operation

1. Hide entities other than inference pair, surface shells and auxiliary geometry, retaining the required parent level to make A/B visible; do not delete geometry.
2. A/B maintains the same identity and orange/green order as overview, and the default is not transparent.
3. Keeps the observation direction of the overview, clears the temporary selection highlight and refreshs.
4. Execute Fit All In to complete the painting and leave the edges behind; the overview scaling cannot be continued.
5. Physically check the clarity of the parties, interfaces and end/wall boundaries relevant to the conclusions.
6. In the case of cover-up, the barrier could be changed temporarily to about 30-50 per cent non-transparent, while the other side remained clear and recorded actual values; local orientations could be adjusted or real profiling could be increased, if necessary.
7. Saves original maps and camera records. Both drawings are of the same size; it is forbidden to reduce critical geometry in pursuit of ratio.

"local" refers firstly to the display of only inference pair and to its Fit All In. Additional intersection zooming or profiling is used as a supplement and does not replace the detail view.

## 7 Red Box & Interface Exclusion

The original map is used as a JPG, BMP, or TIFF exported by CATIA. The original file is retained. The latter processing is used only to cut the interface edges, format conversions and labels, and does not generate or erase the geometry of the model.

The positioning box can be derived from the confirmed range of the object screen, the selected difference with the camera, or a structured three-dimensional projection. The respective camera is used to calculate the positioning area, and the pixel coordinates of the other map cannot be used directly.

The exclusion area of the real vision mouth, target ROI, compass, tree, toolbar, coordinate axis and other supporting elements must be recorded. The window size, camera or compass is re-approved when the position is changed. Coordinate axis, default plane and tree highlight cannot enter the target mask.

When using the selected difference, the camera, display range, colour, window size cannot be changed between the two shots. The stand-alone object assistive positioning map must also use the same camera as the corresponding map and exclude the auxiliary geometry.

The red box only indicates the object or problem location, and does not indicate precise interference with the boundary, penetration or size. When no reliable target is found, the target touches the edge of the exclusion or the frame over the support element, returns NEEDS_REVIEW; preserves the original map and reasons, does not fill the central box, and does not refer to the unboxed figure as a qualified one.

The figure should include Issue ID, integral/local role, direction, A/B actual name or short path, positioning level, and corresponding measurements. The number is taken only from the results of the structuralization of this item.

## 8. Figure-by-case and report acceptance and inspection

Each check: correct identity; A/B and related location visible; complete environment, partially isolated; different and complementary visions; correct colour and transparency; red box not enclosed or supported geometry; Chinese name, unit and number.

Both images must have the same original canvas and the same report embedded in sizes and equal proportions. The original picture should have sufficient resolution; details could be enhanced by increasing the actual CATIA view without plug-in to enhance the quality of the forgery.

The index records at least: Issue ID, object keys and path, original/marked, image width and Hash, actual camera, A/B colour and opacity, hidden object, ROI and exclusion area, QA state and cause of failure.

Rendering Word/PDF after assembly: two large, uncut key geometry, no overlap of words or clear headers, red boxes, and graphics. You cannot return a successful acceptance by using an amplogram function alone.

## 9 Recovery and failure processing

Read back the original records and write display_restoration results.

Resume failed to list specific objects, attributes and remedial actions, and not end up " show all, unify gray ". Saved sign changes are not eliminated by saving the source model.

The mandatory closure process, CATIA collapse or power outage may not be possible; previously kept state records must be used to restore.

Only the temporary object created in this instance and confirmed that it is not necessary to keep it, keep a check of copies and evidence and do not close the user's other documents.

## 10 Existing scripts and enforcement boundaries

The existing common entry for the workspace is `CATIA管路智能检查系统_内网移植包_4.8.0_20260924/project/tools/capture_generic_dual_view.py`; the accompanying reference and revised script is in the same directory as `report_capture_reference_20260920`.

The original universal access is based on the CATPart Body and CATProduc subcomponents as the selection units. Its default background, succession treatment and perspective parameters should not automatically be considered as satisfying this norm; Face/Independent Surface Shells needs a specific object analysis. Use the front-line object, check the actual parameters, and receive a genuine double-graph first.

The offline test or historical R30 acceptance status in the original information is recorded only as a source and does not represent the current actual acceptance. Old scripts containing historical Body numbers, uniform colour restoration, or central background boxes should not be directly run.

This geometric fact is derived from the original CATIA DMU/GSD/SPA; screenshots and pixel analysis do not change geometric determinations.

## 11 Sources and priorities

1. User 2026-10-13 confirms: two large maps, etc.; whole model Fit All In; only partially.
2. Desktop " Generic dual-view script.md " 04_two-view screenshot step by step.md.
3. Project `REPORT_FORMAT.md`, cross-reference to space inspection skills and generic foot note.

The layout, perimeter limitation or mandatory direction requirements in the above document, which conflict with item 1, are carried out in this mandate in accordance with this norm; other identification, evidence, labelling and restoration requirements continue to be retained.
