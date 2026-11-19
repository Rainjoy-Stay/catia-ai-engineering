# Opening Interface Analysis


## Description of the report's amplification codes (2026-10-10)

This section is a description of the current screenshot code; the description of the old yellow/red colour, full image scan or central default box in this document is amended in the creation of the new report by this section. Other business requirements, historical facts and established reporting results remain as they are.

When it comes to the creation of the current model layout or report, read the [original code and revision portal](../../tools/report_capture_reference_20260920/README.md). Three original paragraphs explain the overall view of the relevant neighbourhood, the isolated local view and the high-profile mark; the official generic cut-off and compass exclusion amendment codes are also kept in the same directory and can be used with the project.

Object A/B uses UI orange RGB (255,161,56) and CGGB (31,214,224) with a background of about 20% which is not transparent, with a view to finding the same layout. The compass, tree, toolbar and coordinates are explicitly excluded and only the target screen ROI is detected; the absence of a reliable pixel or mask impact target is subject to review without filling the central frame. Highlight frames do not interfere precisely with borders, and the original script fixes the Body number, the old colour threshold and the unified yellow value.

Takeover - The core module of the open geometric determination. The module does not call CATIA directly by itself. It has now been accessed through `project/catia_checker/opening_interfaces.py` to the primary checker, one-key check, report generation and MCP `catia_check_assembly`.

The input must be CATIA SPA or the exact fact that B-Rep has been extracted: the centre of the opening, the direction, the radius, the integrity of the boundary, the evidence of the discontinuity of the barrel wall, and the taking over axis, the outer radius and the range of the axis.

Determination of coverage: same axle deviations, angles, trajectories, whether or not to cross the open surface, whether or not to cross the whole barrel wall and whether the evidence is sufficient. Insufficient evidence to return `REVIEW`, clearly geometrically ineligible for return `FAIL`, all content to return `PASS`. The grid result is not used as the basis for input.

`match_openings_to_nozzles` carries out the X-axis scan first to take over the limited-axis encircling box, then selects the axis angle, centre deviation, radius and axis range. It produces one-to-one matches, different candidates, isolated openings, holes-free takeovers, and theoretical combinations/actual candidates, with no exact two-to-two calculations.

`analyze_opening_network` is the independent master entrance: normal match to access accurate interface determination; no match to take over return `FAIL/NO_MATCHING_OPENING`;Isolated openings and multiple candidate returns `REVIEW`. The portal only consumes the fact that the source model is not modified.

`adapt_exact_geometry` receives the resolution geometric records of CATIA SPA or OCCT B-Rep. Only the full circle boundaries and deconstructing cylinders will be admitted; records with no central, legal, radius, axis or limited axis range will enter the cause log and will not be supplemented with data.

`merge_coaxial_cylinders` restores the contour column surface of the coaxial and overlapping axis to a receiver candidate. The maximum radius is the outer radius and the smaller radius is the inner radius; `INNER_RADIUS_NOT_OBSERVED` is retained when a single column is present and `MULTIPLE_CONCENTRIC_RADII` is retained when multiple concentric layers are present.

The main item default attempts from `geometry_inventory` Or OCT automatically discovers input, also via CLI `--opening-interface-facts` or MCP Parameters `opening_interface_facts` Provides external precision facts. If only the cylinder lacks reliable evidence of porous boundaries and non-continuation of silos, the main process skips the interface to determine and preserve the cause and does not generate speculative unopened FAIL.

The current reliable range is the full circle boundary, the decomposed cylinder, and the symmetric radius. Complex curves, irrecoverable subarctics, and degradation expansion still need to be enhanced, with the return of `REVIEW` or denial of records at this stage.
