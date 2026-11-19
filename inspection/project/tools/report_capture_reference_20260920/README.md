# Report double view screenshot: original code and revised 2026-10-10

Before creating or reviewing a report with a screenshot, read the present note before reading the relevant code. The original code is from the actual execution record of 2026-09-20, saved as it is; a revised version of this directory can be copied with this item, without reliance on the workspace output or other published directories.

## Original code and order of execution

| Documentation | Original acts | New missions need to be noticed. |
| --- | --- | --- |
| [01_original local screenshot.py](01_原始局部截图.py) | Hide box selections of 22 Body and Shapes, showing only the parties to the problem; select both sides, and wait 0.2 seconds after Refame, CaptureToFile to generate JPEG and index | Fixed Body number must be replaced, and a single yellow ending is not an accurate recovery. |
| [02_original whole screenshot.py](02_原始整体截图.py) | Show the 22 objects concerned; background RGB185,190,198, opacity 52; target opacity 255; reframe waiting for 0.12 seconds | The neighbourhood is determined by this model and the whole machine is not shown by default |
| [03_original red box and index.py](03_原始红框与索引.py) | Scan red yellow pixels; extension 28 pixels, minimum box 90 pixels, red line 10 pixels; generation of double view index | Set a 300-1780 scanning range, bugging the interface, and the central bottom box is off limits. |

History question 20 is the separation of Body 833 from Body 841: Position +. Use it only to understand the view, and not to use the historical Body number, image, statistics or conclusions. The original script only follows the existing perspective and calls Refame, without saving the value of the direction of the initial camera at the time.

## Colouring and Official Revision Codes

- Object A: [255,161,56] Orange; Object B: [31,214,224] Cyan, consistent with current UI conversions [1,63,22] and [12,84,88]. Maintain A/B order, colour does not mean PASS/FAIL. Background grey, approximately 20% opacity and existing reporting layouts remain unchanged.
- [01_UI colour revision local screenshot.py](01_UI配色修订局部截图.py) and [02_UI colour revision overall screenshot.py](02_UI配色修订整体截图.py): Only historical target colours are adjusted for comparison; historical fixed numbering and state restoration limits are maintained and are not used as common access to the new model.
- [capture_generic_dual_view_20261010.py](capture_generic_dual_view_20261010.py): Formal generic display/interception portal; interpret the current object, save and restore the display and camera, and default orange/green colour. Check objects, neighbourhoods, observation direction, output parameters with --help; no automatic capacity to set a contact area is assumed to exist.
- [report_highlight_bounds.py](report_highlight_bounds.py): Identify the current UIO/Cyan light; define the real view and target ROI, explicitly exclude compasses and other interfaces and filter small fragments; return to NEEDS_REVIEW when the outer edge or extension frame intersects with the exclusion area, without default.
- [annotate_report_highlights.py](annotate_report_highlights.py): Batch labels are injected into mouths. Enter -- jobs JSON and --output directories, with an index of audit; NEEDS_REVIEW does not generate false conformity maps.

## Enter and accept

Each jobs item includes the original source chart path, label, viewport rectangular, the actual compass rectangle of Compass, the target projection range of target_roi, the list of excluded other interface rectangles. The rectangle is [left, top, right, bottom], the latter two are exclusive boundaries; measured by the actual window and updated with zoom and compass movement. ROI comes from the object projection or manual check, not guessed by full image colour.

The order of execution: Check the active document with the identity of both parties Save the display/camera/selection status Desalinize the area concerned Orange/Cyan displays the overall view of both sides, take the partial view of the parties, save the original map and camera records → Provide the visual/program/target ROI and mark the map-by-graph check → Precise restoration of the layout of the existing reporting template and PDF page-by-page acceptance.

The pixel frame is an object positioning box and is not an accurate interference with the boundary; the actual intersection/recent point must come from structured geometric measurements. The report audit records script version, A/B path and colour, relevant neighbourhood, camera front and rear, interface exclusion, ROI, original graphs/placards and review/restoration status.
