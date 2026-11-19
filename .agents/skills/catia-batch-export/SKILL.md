---
name: catia-batch-export
description: Export selected CATIA documents as STEP, IGES, STL, or a supported drawing format. Verify output files, report failures, and preserve the source documents.
---

# Batch format export

Read the shared operating rules in [Everyday CATIA operations](../../../docs/CATIA_DAILY_OPERATIONS.md). Discover the structured CATIA tools registered in the current session and verify their contracts. Follow the available `catia-model-understanding` skill for model operations, or use the documented minimum read-only workflow if it is unavailable. Consult the current paired-view skill when the user requests images.

## Natural Language Entry

- “The parts that are currently open are directed to STEP to generate a list of documents.”
- "Exports the STL of the selected widgets, each file with a part number and version, and does not overwrite the old file."
- “Checks whether the assembly delivery documents are complete and the missing references are separately listed.”

## Implementation

1. Specify the source document/stree, format, output directory, name and assembly/single calibre; default new output directory, ban overwrite. Unsaved document allows the export of the current memory according to the range specified by the user, but indicates that the disk source is different from the memory state. Do not automatically save the original for export.
2. Checks format and document type, license, conversion options according to the registered export tool; it cannot be assumed that 3D documents can directly export the drawing PDF. The recording unit, STL discrete precision/options, and the source example retain assembly pose and cannot be clearly disclosed.
3. Re-exports the precise document that binds each target to avoid the recycling of the wrong active document. If you switch the active document, restore the original active document with the available structured operation. The file name removes the path separation, retention and case-crash; in case of collision, a short and traceable identifier is added, without renaming the source model.
4. Independent parts retain all instances to the file map when they are re-exported by definition; examples are exported to keep a pose or to specify local coordinates, and are not mixed. Each record result, size and SHA-256 is recorded; checking that the file exists and is not empty, and format/re-import authentication is performed only when the tool is supported and the scope is authorized. Non-empty files are not equal to conversion authentication.
5. catia_send_to_directory actually uses SaveAs, which may change document paths and references and not be exported as default no side effects; a target and impact list needs to be formed when packaged and then implemented within a clear delegation of authority.

## Acceptance and delivery

Deliver `exports.csv`, `source-to-export.json`, and a list of failed or skipped exports. State whether verification covered file bytes only or included reimport, and report solid and shell counts and units. Preserve the original working documents. Cancellation does not establish rollback of an in-flight COM operation.
