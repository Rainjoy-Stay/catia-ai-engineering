# Project screenshots and reports

Use `.agents/skills/catia-native-dual-view/SKILL.md` for CATIA screenshots, paired interference views, and report illustrations.

Make both images the same size. Show the complete model and fit it in the overview. In the detail view, hide every object outside the interference pair and fit the pair. Keep the same orientation by default. These user-approved requirements take precedence over older guidance that called for neighborhood overviews, unequal image sizes, or different orientations.

Use `catia-spatial-inspection-report` for geometry inspection and the available `catia-model-understanding` skill for model operations. Geometry verdicts and authorization to modify or save models remain governed by their respective workflows.

Use `.agents/skills/catia-native-inspection-word/SKILL.md` for the end-to-end workflow from inventorying open STEP or CATPart documents and reconstructing an in-place inspection assembly through native DMU/GSD/SPA checks, paired screenshots, and a portrait A4 Word report. That skill coordinates the individual workflows and preserves their verdict criteria and operating constraints.

# Everyday CATIA operations in natural language

Follow `docs/CATIA_DAILY_OPERATIONS.md` to select the relevant `.agents/skills/catia-*/SKILL.md` for product tree and BOM export, revision comparison, model provenance, feature and duplicate-part search, measurement summaries, temporary display isolation, batch export, and metadata preflight. Check the available tools and their coverage before running a workflow. Complete cross-revision matching, provenance through the receipt chain, and exact shape equivalence require dedicated evidence or tooling.

# Automatic GitHub synchronization

After completing and verifying code, skill, or documentation changes, automatically synchronize them to the repository at `https://github.com/Rainjoy-Stay/catia-ai-engineering`. The user has authorized this without further confirmation. Exclude models, receipt records, actual case data, runtimes, caches, and secrets before uploading. Preserve third-party license notices and the documented validation limits. If a push is blocked, report the blocker and the actual upload status.
