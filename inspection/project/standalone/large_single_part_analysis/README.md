# Large single CATPart Accuracy Check


## Description of the report's amplification codes (2026-10-10)

This section is a description of the current screenshot code; the description of the old yellow/red colour, full image scan or central default box in this document is amended in the creation of the new report by this section. Other business requirements, historical facts and established reporting results remain as they are.

When it comes to the creation of the current model layout or report, read the [original code and revision portal](../../tools/report_capture_reference_20260920/README.md). Three original paragraphs explain the overall view of the relevant neighbourhood, the isolated local view and the high-profile mark; the official generic cut-off and compass exclusion amendment codes are also kept in the same directory and can be used with the project.

Object A/B uses UI orange RGB (255,161,56) and CGGB (31,214,224) with a background of about 20% which is not transparent, with a view to finding the same layout. The compass, tree, toolbar and coordinates are explicitly excluded and only the target screen ROI is detected; the absence of a reliable pixel or mask impact target is subject to review without filling the central frame. Highlight frames do not interfere precisely with borders, and the original script fixes the Body number, the old colour threshold and the unified yellow value.

Independent core module, multi-Body large CATPart, created after the import of STEP/IGES. The caller provides OCT precision B-Rep climate and backends; the module does not connect CATIA, does not export files, does not modify models, and does not use a grid for adjudication.

Process: Filter the Sweep-and-Prune rough screen of an independent Solid → AABB only for the calculation of the minimum distance and common volume of OCCT output internal-penetration, contact, low net spacing, and dry-covering doors. Open Shell, Surface and invalid B-Rep are listed as REVIEW and cannot be mixed into Solid common volume conclusions.

`INTERNAL_SOLID_INTERFERENCE` is confirmed by positive common volume; zero distance but no common volume is `SOLID_CONTACT`; candidate cut or precise calculation anomaly will cause `coverage_complete=false`. All outputs are fixed to include `mesh_used=false` and `source_modified=false`.

The directory is maintained as the core for independent testing; the main project adaptation layer is responsible for the export of the original CATIA file or temporary read-only STEP to obtain the OCT climate and for converting the results into a unified search, JSON and Word.

The adaptation has been completed by the main project: `--large-single-part-source` Directly read original STEP/IGES; `--large-single-part-active` Through CATIA `ExportData` Create a temporary STEP, which is then executed by the Separatist Sub-Process. The portal transmits a live load, thick sift, and accurate candidate progress, limiting the total running time by the rule; successful, unusual, or extra-time terminates the subprocess and clears the temporary directory. Failure results in the creation of structured ERRO reports. The process will also verify the source Saved status, the number of Bodys and the number of solids that are exported, and closes the integrity door if the number is not consistent.

The one-key entrance activates the CATIA bullet window guard at the same time. The guard will only automatically confirm the " Duplicate Document Identification" information box, which accurately matches text and buttons; keep, overwhelm, delete, update diagnosis and all unknown bullet windows unclicked, and write disposal records into the `catia-dialogs.jsonl` and structured audit fields of this operating directory.
