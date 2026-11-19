---
name: catia-search-duplicates
description: Find CATIA objects by name, part number, feature type, or parameter. Use volume, area, and geometry evidence to screen duplicate candidates.
---

# Feature search and duplicate candidates

Read the shared operating rules in [Everyday CATIA operations](../../../docs/CATIA_DAILY_OPERATIONS.md). Discover the structured CATIA tools registered in the current session and verify their contracts. Follow the available `catia-model-understanding` skill for model operations, or use the documented minimum read-only workflow if it is unavailable. Consult the current paired-view skill when the user requests images.

## Natural Language Entry

- "Find out all parts of the name with the rack, list the path and locate them."
- "Search holes of 8 mm diameter and round angles with a radius of less than 2 mm."
- “Specific identical items by volume and surface area, distinguishing between duplicates of the same item and analogues of different documents.”

## Implementation

1. Distinguishing name/ part number search, feature/parameter retrieval, re-use case count, geometry candidate four tasks. First check the structure, then read the features or measurements by the candidate reference; the same validated definition is measured only once and maps the example back. Large models use sections, progress and budgets to cut off clear reports.
2. The name/type search can be searched using the registered catia_search_elements or snapshot. The CATIA Search syntax must be verified with actual support, with a cross-reference and quote in the transliteration input; the natural language is not collaged into an unlimited range of queries. The selection set is maintained before the search, and is restored after completion; the location is selected only for the only object that has been decrypted.
3. Characteristic results include documents, parent packagings, case paths, precise feature names, types, parameters and units. Review the semantics of the actual parameters; the cylindrical surface is not a perforation, and the B-Rep model may not be native Hole/Fillet. Unreaded Body/HybridBody range column gaps cannot be reported as "The whole model does not exist ".
4. Geometric signatures are defined in the local coordinates system to record, at a minimum, closure, volume mm3, surface area mm2, measurement range/method/ error. Unknown units, zero volume open shells, invalid mass values, NN and reading failure exclude physical size groups and separate area candidates. Quality depends on material/density and cannot directly replace geometric signatures.
5. Use abs(a-b) < = atol + rtol*max (abs(a), abs(b)) in pairs of judgements, with a difference in size and size. Users can use clearly marked screening tolerances when not given, not as a project acceptance standard. The sub-breeding only accelerates the search and must be checked and reviewed in pairs; do not claim A → C because of A → B, B → C.
6. Output groups with CANDIDATE_SAME_SIGNATURE, which raise the conclusions with precise shape comparison/biverse geometry, popping and characterization evidence. AAB size is affected by rotation and is not used for rigid exclusion without alignment; mirrors, left and right, materials and versions still need to be distinguished. Candidates are maintained without a precise comparison tool and are not written "same".

## Acceptance and delivery

Deliver `search-results.csv`, `signature-candidates.csv`, and `coverage.json`. Label each pair `SHARED_DEFINITION`, `SAME_FILE_BYTES`, `CANDIDATE_SAME_SIGNATURE`, or `GEOMETRY_VERIFIED` and include the evidence. Interchangeability requires separate engineering evidence. Keep merge, replacement, deletion, and relinking outside the automatic workflow.
