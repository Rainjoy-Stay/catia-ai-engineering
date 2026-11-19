# Local release maintenance and validation

November 12, 2026. The user authorized automatic GitHub synchronization after verified changes, archival of unused versions, validation of the latest release, and cleanup of redundant copies.

## Retained assets

- `release_build/CATIA_Offline_20261012/` contains the complete offline inspection baseline and required runtime.
- `model_understanding_workbench/`, `tools/`, and `.agents/skills/` contain active development and agent entry points.
- `AI_Engineering_Platform_Latest_20261013/` organizes native inspection cases and deliverables. Acceptance as a unified one-click product remains pending.
- `CATIA管路智能检查系统_Agent交付版_20260920/` remains in place because the configured Codex CATIA MCP and the running process refer to it.
- `CATIA管路智能检查系统_内网移植包_4.8.0_20260924/` contains tools and references used by the current screenshot skill.
- `CATIA管路智能检查系统_内网移植包_4.8.0_R30_详细执行与通用截图版_20260929/` remains in place because two current case and report scripts refer to fixed paths there.
- `release_build/CATIA_V5_AI_DROP_V4_5_DEV/` remains available because video packaging tools reference its historical artifacts.
- Original models, source data, reports, screenshots, videos, and existing `_archive` content were retained for their independent evidentiary or creative value.

## Archive

The archive root is `_archive/cleanup_20261112/`.

- The 4.7.0 release directory, September 20, 2026 curated directory, 4.4 development directory, and 4.4 trial package directory were moved out of active use. Their uncompressed `ZIP_STORED` archives were verified per file by SHA-256 before redundant extracted copies were removed.
- Six historical release and patch ZIP files from the root were moved under `packages/` with their original bytes preserved.
- `move-manifest.json` records original and archived locations. Every new ZIP has an `.index.json` with paths, byte counts, and hashes. `verification.json` records validation and `deletion-receipt.json` records the extracted directories removed.

To restore a package, extract its ZIP to the original directory in `move-manifest.json` and preserve all subpaths. Restore the original layout before running historical tools that contain fixed paths.

## Verification

- Python 3.12 x64, dependencies, and configuration checks passed. The server registered 149 MCP tools.
- The 550-case offline regression suite passed with four skips.
- All 6,035 release manifest file hashes matched.
- Model understanding passed 32 synthetic and mock COM tests and MCP protocol checks for four tools.
- The current UI started and returned HTTP 200. Geometry checks were not started.
- Live CATIA attachment was unavailable. On-machine model and licensing validation and R30 intranet acceptance remain pending.
- System Python lacked `mcp`. The model understanding protocol check passed using the bundled project runtime. The global Python installation was left intact.

Cleanup applied only to redundant extracted copies whose archives passed per-file validation. Unique historical content and active MCP environments were preserved.

## Future use

The local root launcher `打开最新版.cmd` opens the current UI. `验证最新版.cmd` repeats offline verification. GitHub's `local-launchers/` contains launchers for this local layout. A fresh source checkout requires a separately installed runtime.

After completing and verifying future changes, follow `AGENTS.md` to synchronize the private GitHub repository automatically. Models, ZIP archives, runtimes, and raw logs remain local.

The archive uses `ZIP_STORED` for faster processing and straightforward recovery. Disk savings are not guaranteed.

## Completion record

Four older directories containing 34,023 files were archived and verified. Four redundant extracted copies were removed, and six historical ZIPs were archived. The active MCP and referenced versions were retained. See `restore-index.json` in the archive directory for recovery and `cleanup-summary-20261112.json` for the summary. The current UI command entry point passed its `--help` check after cleanup.
