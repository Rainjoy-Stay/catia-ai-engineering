# Editable Engineering Standards

This directory saves standard project parameters that are independent of the program code. Changes to JSON are effective by reruning the check and do not require changes to Python or reloading the MCP.

## HB 4-55-2002 Curve radius of catheter

Documents: `HB_4-55-2002_bend_radius.json`

Common truncable fields:

- `minimum_bend_radius_ratio_r_over_d`: The minimum allowed centre line bend radius is currently 2.0.
- `standard_radius_ratios_r_over_d`: Standard Radius Series.
- `preferred_bend_radius_ratios_r_over_d`: Recommended a preferred radius series.
- `high_pressure_recommendation.pressure_above_mpa`: high pressure suggested trigger value.
- `high_pressure_recommendation.recommended_minimum_ratio_r_over_d`: High pressure recommended radius ratio.
- `nominal_diameters_mm`: A common exterior series that can be evaluated directly in accordance with this standard.

Activity rules select standard files by `routing.bend_radius_profile_file` of `rules-active.json`.
If the lowest radius ratio is to be temporarily covered, the following can be set:

```json
"bend_radius_overrides": {
  "minimum_ratio_r_over_d": 2.5
}
```

Maintains the value of the standard file for `null`. High pressure 4DN is currently exporting `WARN` as recommended, which is not considered mandatory.
