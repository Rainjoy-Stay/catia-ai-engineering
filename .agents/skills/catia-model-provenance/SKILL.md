---
name: catia-model-provenance
description: Collect CATIA files, references, metadata, and authorized receipt records. Distinguish observed facts from inferences and identify gaps in the receipt chain.
---

# Model provenance and receipt chain

Read the shared operating rules in [Everyday CATIA operations](../../../docs/CATIA_DAILY_OPERATIONS.md). Discover the structured CATIA tools registered in the current session and verify their contracts. Follow the available `catia-model-understanding` skill for model operations, or use the documented minimum read-only workflow if it is unavailable. Consult the current paired-view skill when the user requests images.

## Natural Language Entry

- "Check out where the numbers come from, sort out the reception and conversion chains."
- "Play the model file and the pass sheet to generate an archived retrospective list."
- "to determine whether these parts are original CATIA or STEP imports and give evidence."

## Implementation

1. First collects information about the current document type, complete path, unsaved status, external references, readable product properties and formats. File size/ change time/ Hash is valid only for the disk bytes read this time; geometry cannot inherit the disk Hash as the current content fingerprint in memory. Mark FILE_CHANGED_DURING_READ when reading back-to-back file size or time change.
2. The evidence is divided into FILE_FACT (path/hash/format), MODEL_METADATA (original attribute/citation), RECEIPT_RECORD (transmit/receipt registration/authorization of mail or PLM records) and INFERENCE. Record each factual source, reading method, time, applicable object and whether it is manually confirmed; keep the original coding and the time zone unknown.
3. When a user requests a receiving chain, search for an existing passer, version record, PLM identifier and import/transform audit in an authorized directory and connected system. Read only a query, do not send a letter, do not change the sharing, do not send a model or list to an external AI because of a task. Write UNKNOWN when there is no record, cannot create a file at the time of receipt or identify the author field as a supplier.
4. Creates a chain of evidence based upon evidence — type of event, front-and-back hash/identify, time and evidence. Uncertain side is UNVERIFIED. The same hash only proves the same byte, does not prove who sent it or who legally owned it.
5. Original editable features, import B-Rep, results unconnected, hybrid models reported separately by readable features. Individual Import/STEP names are not sufficient to determine the entire source of the model; applications/authors in the head of the STEP file are only stated. Geometrics like a manufacturer do not constitute evidence of the source.

## Acceptance and delivery

Deliver `provenance.json`, `artifact-index.csv`, receipt-chain gaps, and archival recommendations. Preserve the source files and avoid writing provenance fields back to the model. State evidence levels and gaps without assigning unsupported percentages. If receipt records are missing, report the observed file facts and leave the receipt chain unconfirmed.
