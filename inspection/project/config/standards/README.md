# 可编辑工程标准

本目录保存独立于程序代码的工程标准参数。修改 JSON 后重新运行检查即可生效，不需要修改 Python 或重装 MCP。

## HB 4-55-2002 导管弯曲半径

文件：`HB_4-55-2002_bend_radius.json`

常用可调字段：

- `minimum_bend_radius_ratio_r_over_d`：最低允许的中心线弯曲半径比，当前为 2.0。
- `standard_radius_ratios_r_over_d`：标准半径系列。
- `preferred_bend_radius_ratios_r_over_d`：推荐优选半径系列。
- `high_pressure_recommendation.pressure_above_mpa`：高压建议触发值。
- `high_pressure_recommendation.recommended_minimum_ratio_r_over_d`：高压建议半径比。
- `nominal_diameters_mm`：可直接按本标准评价的公称外径系列。

活动规则通过 `rules-active.json` 中的 `routing.bend_radius_profile_file` 选择标准文件。
如需临时覆盖最低半径比，可设置：

```json
"bend_radius_overrides": {
  "minimum_ratio_r_over_d": 2.5
}
```

保持为 `null` 时使用标准文件中的值。高压 4DN 当前按建议性要求输出 `WARN`，不会当作强制不合格。
