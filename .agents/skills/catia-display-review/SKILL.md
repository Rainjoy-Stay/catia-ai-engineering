---
name: catia-display-review
description: Select, isolate, hide, or adjust transparency temporarily, then restore and verify the original display state.
---

# Locate and isolate CATIA objects

Read the shared operating rules in [Everyday CATIA operations](../../../docs/CATIA_DAILY_OPERATIONS.md). Discover the structured CATIA tools registered in the current session and verify their contracts. Follow the available `catia-model-understanding` skill for model operations, or use the documented minimum read-only workflow if it is unavailable. Consult the current paired-view skill when the user requests images.

## Natural Language Entry

- "This part of the positioning structure tree is shown only temporarily."
- "Let me see this tube in the box, and then restore it."
- “Leave these results individually and list the same subjects for me to distinguish.”

## Implementation

1. Parsing the only document, example path and objective, confirming that the selection/show changes will satisfy the need; positioning does not activate the parts editing. Recording the current active document, selection, target visibility/colour/transparency, affected background objects and cameras.
2. The minimum temporary change is performed using the registered selection and display tool; isolation is required to know the original state of all objects that will be hidden.
3. Displays the logical restoration of the change to the original value by object, without setting the whole as a single visible or uniform colour. The user expressly requests that the display be kept and recorded as required, without saving the model to sustain the display.
4. The user needs to report the graph to the catia-native-dual-view: the whole model Fit All In, which is large and large, keeps only the target for the second Fit All In, and defaults in the same direction. The mask does not see the object that does not represent it, and the screenshot does not support geometry.

## Acceptance and delivery

Checks the number of paths and targets actually selected, indicating which states have been restored and which have not been restored. If the original operation fails, the safely executed recovery is completed.
