# Standard format for CATIA automated inspection reports

## Current screenshot requirements (2026-10-13)

Follow the [native CATIA paired-view skill](../.agents/skills/catia-native-dual-view/SKILL.md). **Use equal-size images and the same orientation by default. For the overview, show the complete model and use Fit All In. For the detail, isolate the interference pair and use Fit All In on both objects.** This user-approved rule takes precedence over older guidance about neighborhood framing, unequal image sizes, and different orientations. Preserve object identity, annotation, display restoration, and report acceptance requirements.


## Report screenshot code reference (2026-10-10)

This section records the screenshot code used at the time and supersedes older yellow/red coloring, full-image scanning, and central fallback box rules for new reports. Other business requirements, historical facts, and confirmed results still apply.

Before creating images or reports for the current model, read the [original code and revision notes](../inspection/project/tools/report_capture_reference_20260920/README.md). Three original scripts describe neighborhood overviews, isolated pair details, and locator annotations. The generic capture and compass exclusion revisions are in the same directory.

Read `01_原始局部截图.py`, `02_原始整体截图.py`, and `03_原始红框与索引.py`. For production captures, use the applicable revisions from `capture_generic_dual_view_20261010.py`, `report_highlight_bounds.py`, and `annotate_report_highlights.py`. Preserve the raw image, camera, ROI, mask, and display restoration records for each object.

Use UI colors for A and B: orange RGB(255, 161, 56) and cyan RGB(31, 214, 224). Surrounding geometry uses about 20% opacity. Exclude the compass, tree, toolbars, and axes from the target screen ROI. Route items without reliable target pixels or masks to review. A locator box does not indicate the exact interference boundary. Original scripts contain fixed Body numbers, obsolete color thresholds, and a unified yellow color.

## Output Principles

- The same schema `1.1.0` check JSON produces only one official PDF report.
- Only problematic, subject to review, non-completion or unusual implementation areas are written in the body of the report; a clear PASS, risk-free combination, is included in the statistics only and not on a page-by-page basis.
- Each problem is supported by two levels of evidence, “overall positioning + local details”, and no longer provides only a quarantine view.
- The overall positioning map retains the necessary aggregate context; the non-problem parts are consolidated in semi-transparent grey, with approximately 15-25 per cent recommended non-transparent, and the problem is transparent, using orange/cyan brightness consistent with UI (A: RGB 255, 161, 56; B: RGB 31,214,224).
- Only the parties to the question are retained in the local detail maps, which are scaled to the common volume, the area of contact or the nearest point.
- The red box must cover the real problem area and leave a margin for identification, and cannot be fixed in the middle of the picture or simply frame the whole large part.
- Priority is given to CATIA V5 original screenshots. If you use analytical renderings such as OCCT/Matplotlib, you must clearly label them as "analytical renderings" and not pretend to be evidence of CATIA original interfaces.
- Geometric findings are derived only from CATIA's primary measurement and rule engine; the picture and AI text do not change the decision.
- Default to use A4 horizontal, ", deep blue/grey project reporting style.

## CATIA Interception Operational Guidelines

Each issue is implemented and recorded in the following order:

1. Confirms the active document, the complete object path of the question parties and the results of the current inspection.
2. Restores the collective context required for this batch and avoids the loss of location references by cutting only a small fraction.
3. Align non-issue objects to semi-transparent grey; complex assembly defaults about 20 per cent.
4. The parties to the question are not transparent, and orange (255,161,56) and cyan (31,214,224) are used in the order A/B of UI.
5. (b) Overview should see both the contours of the assembly, the parties to the problem and the area in which the problem is located.
6. Prioritizes positioning according to the common volume, area of contact or nearest point; when using high-light pixels, the compass, tree, toolbar and coordinate axis must be excluded and screened only within the target projection ROI. High-light boxes can only be called object locator frames and cannot be called precise interference with the boundary.
7. Hide the remaining objects, preserve only the parties to the problem, generate partial isolation maps and expand the position of the problem.
8. The original name of the object, complete path, classification, measured values, units, determinations and sources of evidence are shown below.
9. Revert the display after completion of the screenshot; transparency, colour or temporary selection shall not be misconstrued as a model structural change.
10. The report is generated by exporting PDF and page-by-page examination to confirm that the picture is uncut, the title is unlearnable, the red box is clear and the text is readable.

The same rule is applied to the road screenshot: the target route is clear, the surrounding parts are transparent, and the overall position chart and the quarantine magnification map are maintained. If the central line, cavity or engineering syntax cannot be confirmed, the reporting status remains `NOT_EVALUATED`.

## Report creation focus: double viewing and comment acceptance

### We have to read the original code first.

Before planning captures, consult the [historical code and revised workflow](../inspection/project/tools/report_capture_reference_20260920/README.md), then inspect the original local view, overview, and locator and index scripts. The source is retained with the project. Follow the UI color, display restoration, and compass exclusion revisions. Adapt hard-coded Body numbers and pixel thresholds, and remove central fallback boxes before executing original code.



This process must be completed before the assembly report is assembled and carried out according to the historical question 20 viewing method; the layout of the overall positioning + local details is maintained, the color of the interferant pair is changed to the current UI colour, and the colour of the red box and reporting state is unchanged.

1. ** Records identity and initial state.** Save object A/B real path, list of relevant adjacent areas, display/colour/transparency/inheritance properties, camera origin/view/up/ project/scaling and selection status. No hard-coding history Body number is allowed.
2. ** Overview defines the relevant neighbourhood.** Historical cases are 22 objects; the new model selects the neighbourhood based on the actual problem, without defaulting the entire object. The background follows grey and about 20 per cent opacity, and A/B is non-transparent orange/cyan. After selecting the object, Reframe; check the identity, direction and mask of the object. Refame follows the current direction and does not guarantee a suitable perspective on its own.
3. ** Detail view parties.** Hide unrelated objects, maintain the same A/B colour, reframe check the parties ' complete lenses, proportional images and clear interfaces; re-directe the camera as necessary. The overall positioning and local detail diagrams are useful and cannot be replaced by the same duplicate screenshot.
4. ** Remark the original map after saving it. ** Use tools/annotate_report_highlights.py; exclude rectangles such as the actual visual rectangle, the compass rectangle, the target screen ROI and the tree/toolbar/coordinate axis for each original map. Re-defining these areas with changes in the size of the window does not allow the replicating of the fixed 300-1780 pixel scanning range, nor does it assume that the compass is permanently located in a fixed corner. The compass must be visible and there is a lack of configuration to stop processing.
5. ** The target is highlighted only.** The pixel detection of the orange/cyan identification of UI is synchronized; the view, target ROI and interface are removed and the small pixel fragments are removed. Target ROI is obtained from the object screen projection or manual check, not from the full image colour. No reliable pixels, or high-light touch ROI/ exclusion area boundary, marked NEEDS_REVIEW, is found; no central patching of the default box is allowed, and it is prohibited to fill the eligible image with a non-boxed image.
6. ** Checks the meaning of the red box. ** The pixel surrounding frame only indicates the location of the highlighted object; only structured intersection/recent evidence can locate the actual geometry range. The red box should not cover the compass or use the whole machine encirclement as local evidence.
7. ** Reactivate post-acceptance assembly reports.** Exact restoration of the pre-interception display and camera state without preserving the original model of the supplier; check the visibility, colour, mask, locator frame and label on a piece-by-piece basis, and release the PDF page-by-page review using the existing template. Audit index record colours, visuals, exclusion areas, target ROI, original diagrams, illustrations and review status are not completed. NEEDS_REVIEW Retains the item to be processed.

Historic integrity commands are kept in the output/old cut-off process retroactively_20261010; the original text is only retroactive. Two UI revised scripts maintain historical view and transparency, but still have historical restoration limits; official tasks prioritize the preservation and restoration of the displayed status of capture_generic_dual_view.py. Old reports and old video pictures do not overlap because of this process modification.

## Fixed Chapter

1. Cover: Models, general conclusions, report number, rule set, inspection method and timing.
2. Executive summary: PASS/WARN/FAIL/ NOT_EVALUATED / EXEMPTED/ERROOR number.
3. Scope and methodology of inspection: Component range, scanning threshold, cut-off of results, temporary product and source model retention.
4. Problem overview: Issue ID, state, severity, rules, component pairs, measured values and type of problem.
5. Baseline change: new, addressed, ongoing, changing, regression and improvement.
6. Checking borders and credibility: checked, uninspected, hypothetical and downgrade items.
7. Detailed questions: Parameters for each individual, statement of determination, rectification recommendations and photographic evidence.

Question breakdown page recommends layout: the first half is an overall semi-transparent map, the second half is a detailed map of local isolation; a single issue page. Complex clusters can appropriately expand the cut-off range, but not at the expense of the visibility of the problem area.

## Status Colour

| Status | Colours | Purpose |
|---|---|---|
| PASS | Green | Complete inspection and meet rules |
| WARN | Orange | Need for engineering review or close to limit |
| FAIL | Red | Violating clear rules |
| NOT_EVALUATED | Grey | Lack of context or algorithm not applicable |
| EXEMPTED | Blue | Exemptions granted by explicit rules |
| ERROR | Dark red. | Check execution or data anomaly |

## Auto Generate

```powershell
python .\tools\generate_visual_pdf_report.py `
  --input .\output\dmu\Model_dmu_check.json `
  --evidence-dir .\measurements\visual_evidence `
  --output .\output\pdf\Model_可视化检查报告.pdf
```

Output:

- `output/pdf/Model_可视化检查报告.pdf`

DMU values are derived from the original CATIA geometry; the red box is used only for visual positioning and not for inverse 3D interference with borders.
