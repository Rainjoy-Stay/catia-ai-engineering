---
name: catia-measurement-summary
description: Summarize CATIA volume, surface area, mass, bounding boxes, centers of gravity, and specified distances. Use precise geometry checks for interference verdicts.
---

# CATIA measurement summaries

Read the shared operating rules in [Everyday CATIA operations](../../../docs/CATIA_DAILY_OPERATIONS.md). Discover the structured CATIA tools registered in the current session and verify their contracts. Follow the available `catia-model-understanding` skill for model operations, or use the documented minimum read-only workflow if it is unavailable. Consult the current paired-view skill when the user requests images.

## Natural Language Entry

- “The size, surface area and centre of gravity of the spare parts are listed and sorted by volume.”
- "The total mass of this component is measured, and parts without materials are listed separately."
- “to measure the minimum spacing of these two items and to give a reversible reference.”

## Implementation

1. Parsing objects and statistical calibrations, distinguishing between definition measurements and examples. Confirms the range of parts/Body/shells and avoids mixing multiple Body whole parts with single Body. Using registered raw inertia, geometric counts, ranging tools and object-by-object measurements, check the tool back to the unit and not guess the unit by numerical size.
2. Records volume, area, mass, density source, gravity and coordinates. UNKNOWN Mass when no authorized density/material; CATIA default density values are marked ASSUMED_DENSITY and are not commingled in the approved quality. The focus of the component example must be changed to root coordinates along the complete pose chain and unknown pose dissemination UNKNOWN.
3. Summarizes only the physical cases of the leaf class within the expected range, with the addition of both the father's assembly and the sub-components. The total weight is weighted by the effective mass, with the exclusion mass and coverage; the shell size is not equal to zero mass.
4. Minimum distance is clear for two examples and precise references; AABB distance is only sifted roughly. Distance 0 may be contact or penetrating, and cannot directly draw conclusions from intervention; geometrical skills are available when needed. The measurement fails without filling in 0, and the source model is not automatically updated or repaired to obtain values.

## Acceptance and delivery

Output measurements.csv and the number of measurement methods, units, coordinates, valid/failable objects. Sampling checks a decipherable object; unknown unit/density/pose separate columns. Reporting the measured values does not qualify for the absence of approved spacing criteria.
