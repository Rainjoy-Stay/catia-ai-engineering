# CATIA Tubing and Model Geometry Inspection Specification


## Report screenshot code reference (2026-10-10)

This section is a description of the current screenshot code; the description of the old yellow/red colour, full image scan or central default box in this document is amended in the creation of the new report by this section. Other business requirements, historical facts and established reporting results remain as they are.

When it comes to the creation of the current model layout or report, read the [original code and revision portal](../inspection/project/tools/report_capture_reference_20260920/README.md). Three original paragraphs explain the overall view of the relevant neighbourhood, the isolated local view and the high-profile mark; the official generic cut-off and compass exclusion amendment codes are also kept in the same directory and can be used with the project.

Object A/B uses UI orange RGB (255,161,56) and CGGB (31,214,224) with a background of about 20% which is not transparent, with a view to finding the same layout. The compass, tree, toolbar and coordinates are explicitly excluded and only the target screen ROI is detected; the absence of a reliable pixel or mask impact target is subject to review without filling the central frame. Highlight frames do not interfere precisely with borders, and the original script fixes the Body number, the old colour threshold and the unified yellow value.

| Document Properties | Contents |
|---|---|
| Version | 2.2.0 |
| Status | V4.4 AI Lead Engineering Check Baseline |
| Publication date | 2026-09-09 |
| Phase of application | Local field measurements, intranet acceptances and formal rules import |
| Target platform | Intranet: CATIA V5 R30 (SystemConfiguration.Release=30); development certification: V5-6R2022 / Release 32; other versions separately |
| Change control | Subsequent changes are managed through version recording and controlled rule library |

> 2026-09-29 Revision: Intranet targets are explicitly harmonized by users as CATIA V5 R30 (Release 30); previous R18 targets are required to be invalidated. The software baseline 4.8.0. The current inspection/naming/interception/reporting rules can be found in Internet, which includes the " 00_internetAgent Progressive Implementation Manual " and six fascicles; the R30 targets confirm that they do not amount to the completion of R30 real machine inspections.

> Baseline statement: This document has been upgraded from 2026-09 to project SPEC v2.0. v2.0 for current V4.4 streamlined version: CATIA/geometric tool provides objective facts, AI Agent proactively plans inspections, selects tools, supplements evidence and determines design relationships; the rule engine is responsible for numerical thresholds and ultimately retroactive determinations. Output is JSON, Red Boxshot and Word, and does not generate PDF. Section 8.2 values are only the default values for prototype screening and do not constitute a basis for model design approval or seaworthiness.

## 1. Document Purpose

This SPEC defines a set of **air engine short-class tube layouts**, CATIA V5 `CATProduct` / `CATPart`, original Tubing Design data and the AI Agent model check rules and output requirements for neutral models such as STEP/STP, IGES/IGS for the identification of:

- (b) Hard interference between the pipe and the route, structure, equipment, entity or curve;
- Insufficient space for installation, operation, heating, vibration and maintenance;
- (b) Unjustified lines of turn, bend radius, straight sections, branches and connections;
- (b) Discontinuation of the connection between the central line, the interior, the wall thickness, the direction of the interface or the assembly;
- (b) Supporting the risks of set-up, manufacturing, assembly and maintenance;
- The CATIA model itself is ineffective, repetitive, suspended or data quality-related.

This SPEC is the system-level baseline for the vendor model entry inspection, covering both rigid and flexible tubes. The first stage allows for the use of simple validation models for debugging identification and geometric algorithms; prior to entry into the engineering application, the model-specific criteria, approved design manuals and representative short-class models are required to complete the rules and acceptances.

### 1.1 Expected system boundaries

- AI Agent connects and reads the current model in the context of the CATIA client;
- Automatic identification of product trees, Tubing Design pipes, sections, hoses, connectors, support, short-class structures and equipment;
- (a) Execute read-only geometry and rule-checks to generate structured results, red box evidence maps, rectification proposals and Word reports;
- The problem should be repositioned within CATIA according to the path, coordinates or selection set of the object;
- At this stage, automatic modification, automatic repair and unconfirmed preservation are prohibited;
- AI is responsible for understanding tasks, developing inspection plans, selecting tools, taking evidence over time around suspicious objects, judging design relationships, creating justifications and reporting; establishing stable facts such as geometrical kernel responsibility for distance, interference, angle, radius and continuity. AI may not tamper with tool measurements, nor may it draw conclusions based solely on amputations.

### 1.2 v2.0 Core architecture principles

The system must follow the principles of “prioritization of primary capacity, certainty rules, AI enhancements but not substitute for engineering calculations”:

1. ** CATIA DMU is a source of geometrical facts for assembly**: Clash, Contact, Clearance and Distinction between ordinary components should be called first and foremost by CATIA DMU Space Analysis; it should not be judged on the basis of a screenshot, bounding box or linguistic model only when original capacity is available.
2. ** Tubing Design is a source of traffic-synthetic fact**: pipe lines, Arrangement Run, connectors, specifications, Line ID, plumbing and directory properties should be read from the original object first.
3. ** Dedicated calculation to complete DMU items not covered**: central line curve radius, R/D, port continuity, internal contours, hose bends and rules compensation are calculated by firm pipe mode.
4. ** The rule engine is responsible for numerical boundaries**: DMU/geometric tool output objective facts, rules engine enforcement of controlled thresholds, formulae, scope of application and explicit approval of exemptions, and does not write design intent into a simple white list.
5. **AI is the subject of the relationship judgement rather than the dimension measurer**: AI does not create or overwhelm the measurement values itself by actively analysing the type, end, axis, nearest point, area of exposure, capping, assembly level and surrounding components to determine whether closeness is a reasonable design connection.
6. ** Pictures are used as evidence only**: screenshots are used for location and communication and do not participate in the final geometry determination.
7. ** Uncertainty must be exposed in a visible manner**: `REVIEW_REQUIRED` may not be automatically released in order to reduce alarms when insufficient evidence, conflict of evidence or lack of synonyms for a dumb model.
8. **Showcasing of normal connections and omissions**: the confirmed normal connections are kept in the JSON audit trail, but do not enter the list of issues and questions in Word report.

### 1.3 System Layers

```text
CATIA V5 R30 (target intranet deployment, Release 30)
                    ↓ Local COM / MCP
Geometry evidence and rule tools
  ├─ Full-assembly clash scanning and result extraction
  ├─ Tubing centerline, radius, angle, interface, and flow passage algorithms
  ├─ Object classification, candidate screening, incremental checks, and issue consolidation
  └─ Controlled JSON rule library

AI engineering inspection agent
  ├─ Task interpretation, tool selection, and iterative evidence collection
  ├─ Assessment of connection and assembly relationships
  └─ Confidence, key evidence, rationale, and review recommendations

Reporting and interaction
  ├─ Local Word and JSON outputs with locator-box screenshots
  ├─ Locate and capture objects in CATIA
  └─ Default company intranet model, with an approved enterprise AI gateway as an option
```

CATIA models, geometry tools, and rule files should not rely on the Internet. AI should still save geometric facts and underlying scanning results that have been obtained when services are not available; any component relationship requiring design intent judgement should be downgraded to `REVIEW_REQUIRED` and should not be disguised as a full semantic check with templates or death lists.

## 2. Application

### 2.1 Subjects of support

- CATIA V5 assembly: `CATProduct`;
- Parts: `CATPart`;
- Parametric entities, importing entities, curves, geometry collections;
- (a) Direct, bend, bend, tricom, bronchial, insular, flange, valve, hose and support;
- Equipment, structural elements, gold nuggets, beams or other models configured as barriers.

### 2.2 Non-automatic determination of scope in the first edition

- (a) The strength, fatigue, vibration and stress suitability when the payload is not provided;
- No precise calculation of the temperature and thermal transport at the time of containment is provided;
- (b) Pressure-down, flow speed, gas erosion and discharge performance when no fluid parameters are provided;
- Media, materials, welding grade or process requirements that cannot be identified solely by their outer form;
- `Visual proximity' between curves, but no valid thickness, direction or semantic design data.

The above-mentioned items may be exported “for additional data” or “for manual/professional analysis” and may not be misreported as eligible.

## 3. Check Mode

The system should support:

1. ** Full mass inspection**: inspection of the whole product and of all suitable objects;
2. **Selected scope inspection**: check by component, pipe number, geometry set, Body or user selection set;
3. ** Change inspection**: only new or modified objects relative to the baseline are checked, as well as their immediate proximity;
4. ** Single inspection**: only rules specified for interference, spacing, bending, interfaces, support, etc.;
5. ** Batch-processing inspection**: a read-only inspection and summary of a specified catalogue or model list.

By default, read-only diagnostics are used and the source model cannot be automatically modified or saved.

## 4. Input Requirements

### 4.1 Model input

Each inspection shall record:

- Root product name, complete path, version/revision number and inspection time;
- CATIA version, unit and assembly position;
- Product tree, example name, zero part number, reference file and loading status;
- Body, geometry, curves, features, parameters, relationships and release elements;
- Objects that are suppressed, hidden, undefunct, invalid or unupdated;
- (b) Central, outer, inner or wall thickness, port, direction, line number and specification (if present in the model).

### 4.2 Operational inputs

The project shall provide or configure:

- Industry and applicable standards;
- (a) Pipeline type, medium, hazard class, pressure, design temperature and materials;
- b. Common diameter, outer diameter, wall thickness, permitted bend radius and method of manufacture;
- Static, dynamic, temperature-preservation, electrical, heat surface and maintenance space;
- Port allows for error, angle, gap and depth variance;
- Support maximum spacing, fixed points, point of direction and no-bub zone;
- Lists of persons allowed access, allowed penetration and exempted.

The short-seat project should also be imported or derived from fire/non-fire-protective areas, heat and temperature fields, rotor non-inclusive hazardous areas, motor-sweeping ring, vibrating-place transfer package, relative short-seat engine shift, temperature/fire-proofing thickness, combustible media properties, maximum work and proof pressure, and hatch opening and LRU unassembly.

When critical business input is missing, the system should use the project default and mark `ASSUMED`; when no valid default is available, mark `NOT_EVALUATED`.

## 5. Object Identification and Classification

The system should prioritize the use of CATIA structured data identification objects and not rely solely on screenshots or colours.

Identification of priority:

1. Native Tubing Design objects, directory properties, Line ID and connectors;
2. Centres, axes, ends, interface points and parameters issued;
3. Parametric characteristics and naming rules;
4. (b) Trawling and geometric extrapolation;
5. Artificial mapping.

Each object is classified at least as: `PIPE`, `ELBOW`, `TEE/BRANCH`, `REDUCER`, `FLANGE`, `VALVE`, `HOSE`, `SUPPORT`, `EQUIPMENT`, `STRUCTURE`, `SURFACE`, `UNKNOWN`.

The type derived from geometric inferences must record confidence; below the project threshold, only review items can be generated and failure conclusions cannot be made directly.

### 5.1 Diversion of primary and neutral format models

The system must first identify the type of input and then choose the evidence route:

- ** CATIA Native Model**: Priority is given to reading product trees, examples/part names, assembly levels, constraints, release elements, interfaces, parameters, attributes, Tubing Design objects, Line IDs and directory specifications; geometric evidence is used to validate semantics and not blindly trusted names.
- ** STEP/STP, IGES/IGS, etc.**: The lack of protopathic meanings should not lead to passing through the circuit. Components should first be divided by separable entity, connected domain or geometric body, using cylinder/convene/ring cross-section, pipe stability, long-range ratio, wall thickness, end-side, centreline continuity, direct tube and bending characterization pipelines and connections.
- **Mixed or uncertain model**: both original properties and geometric inferences are retained; when the two conflicts are investigated and conflicting evidence is exported by AI and manual review is not possible.

The standard data stream in neutral format is:

```text
Detect format → identify geometry and components → recognize tubing and connectors
→ Find nearby components → gather closest-point, end-face, axis, contact, penetration, and continuity evidence
→ Assess connection and design relationships with AI → apply clearance, interference, and bend-radius rules
→ JSON → locator-box screenshots → Word report
```

STEP/IGES curved radiuss shall be measured first from the column surface, circle, transect or recoverable central line; conservative geometric estimates may be given when the central line cannot be reliably restored, provided that the method and confidence level are indicated, the output of `REVIEW_REQUIRED` or `NOT_EVALUATED` is not directly omitted when there is insufficient evidence.

## 6. Inspection rules

### 6.1 Model health

| Rule ID | Check Contents | Default determination |
|---|---|---|
| MDL-001 | The reference file is missing or not loaded | FAIL |
| MDL-002 | Part/Produc Update failed, feature expired or expired | FAIL |
| MDL-003 | Repeat components, zero-sized entities, isolated geometry | Warn/FAIL, configured |
| MDL-004 | Anomalous unit or proportion | FAIL |
| MDL-005 | Missing piping key parameters, port or centreline | NOT_EVALUATED + WARN |
| MDL-006 | Multiple inconsistent versions of the same object | FAIL |

When model health failure occurs, the system can continue to perform meaningful examinations, but the report must indicate that the results may be incomplete.

### 6.2 Hard interference checks

The inspection combination includes at least:

- Pipeline - Pipeline;
- (b) Pipeline-equipment;
- (a) Pipelines - structure;
- Pipelines - support;
- (a) Pipeline-curvature;
- Other entities - entities, entities - curves (enabled by configuration).

The rules require:

- (a) The entity's common volume is determined to be hard interference when it is greater than the geometric difference;
- (b) Report the volume of interference, maximum penetration depth (when calculable), the location of interference and the complete path of both parties;
- (b) Distinguishing the intersection of material from the expected interface, the opening of the channel and the non-expected collision;
- Three connections, such as tributaries and valves, are subject to simultaneous inspection of external material relations and internal flow flow;
- Side/point exposure should be classified according to exposure tolerance and should not be miscalculated as volume interference;
- The normal design connection confirmed by the AI survey does not pose an interference problem; explicit approval for access/permeability remains subject to the binding of specific rules, object pairs and model versions and can be traced.

The short-seat inspection must be performed in at least the following states: the nominal assembly state, the condition of the body, such as the hatch/reverse, the state of the relative transfer of the engine to the short cabin, and the state of the maximum motor envelope of the hose. Only static CAD shall not be declared dynamic without interference.

#### 6.2.1 CATIA DMU Primary screening requirements

- Interference between ordinary CATProdut components should use the original CATIA Clash capability corresponding to `GetTechnologicalObject("Clashes")`;
- Full assembly inspections must be based on one-time `Between All Components` calculations, with CATIA internal screening of candidates and geometry;
- Prohibits external dual circulation of all parts, creating Clash on a pair basis as the default option for large assembly; the check-by-check is used only for object-specific review, unit testing or detailed positioning;
- Specified range check to use `Inside One Selection`, `Selection Against All` or `Between Two Selections`;
- Computation of configuration at least recorded: Computation Type, International Type, Clearance, precision/exposure and CATIA versions;
- Access to information on condition Type, Value, First Project, Second Project, status and available location must be read for CATIA returns;
- The report must distinguish between the original CATIA Confilt Value and the system-generated “penetrating depth” field. If the two are not proven to be equivalent, the original value should be retained and the method of extraction marked;
- The temporary Clash/Distance/Group object created during the check must be cleaned in `finally` and the user selection set and activity document restored;
- No source model containing temporary check objects should be saved; check `ERROR` in case of clean-up failure and send a clear message to the user;
- An empirical B-Rep/ Grid backup algorithm may be used when the original DMU licence or automated interface is not available, provided that the result marks the method of calculation, precision and limitations and does not impersonate the original DMU result.

#### 6.2.2 AI-led conflict and close relationship surveys

The conflict/proximity candidate returned by the original Clash or other geometric tools must have been investigated before the engineering problem could arise:

1. (a) The path to the full component example, which cannot only use the name of the leaf node that may be repeated;
2. Identification of the type of object and the system/pipeline to which it belongs;
3. (b) Exclude empty parts, no-owner shape expressions and uncalculated components, and separate data quality issues;
4. (b) Identification and association of Run and its physical tube, avoiding conflict between the same route and itself;
5. By AI to make relationship assumptions based on available evidence and to continue to call for evidence as required at distance, end, axis, transect, adjacent area, assembly path or means of interception;
6. AI Consolidated direct connection, intermediate connection, support/installation relationship, geometric continuity and signs of unusual penetration, output relationship conclusions, reasons, confidence and key evidence;
7. Relationship conclusions can only be `PASS_NORMAL_CONNECTION`, `CHECK_CLEARANCE` or `REVIEW_REQUIRED`; no static "connection waiver list" may be used as an alternative to investigations;
8. (b) Implement the control minimum spacing/interference rule for `CHECK_CLEARANCE`; reserve candidates for `REVIEW_REQUIRED` and submit them for manual review;
9. Merge duplicates of the same object, the same area and the same cause;
10. The output of the original DMU result, AI relationship judgement and rule determination shall be retained for audit purposes.

A two-stage tool is recommended: `prepare` to create candidate and evidence gaps, AI to investigate independently, and `finalize` to verify the results of the quoted measurements and consolidate the results. If AI does not obtain new evidence, it should not use the same tool unnecessarily again.

### 6.3 Spacing

The spacing must measure the shortest real geometry distance, not the final conclusion. The box should be used only for candidate-to-peer screening.

Configure different thresholds by object relationship:

- Pipelines — net routing distance;
- Pipeline - structure/equipment net spacing;
- Pipeline - thermal surface, electrical or sporting net spacing;
- (a) Operation of the perimeter of the flanges, valves, filters, instrumentation and deassembly space;
- Net spacing of the insulation, coating and protective gear installed;
- Motion, vibration, heat-sweeping, net distance from the surrounding object.

Each candidate makes a relationship judgement and then a numerical determination:

1. `PASS_NORMAL_CONNECTION`: There is sufficient evidence of a normal connection, assembly contact or reasonable connection, and a space check passed; the record is kept in JSON audit data but does not appear on Word List of Issues and Detailed Pages.
2. `CHECK_CLEARANCE`: No reasonable connection has been found and PASS/WARN/FAIL continues to be determined at the actual minimum distance and rule threshold.
3. `REVIEW_REQUIRED`: Insufficient information, conflicting evidence or insufficient AI confidence, not automatically passed, review of the author's work.

The design interface for the direct interface, with the expected net distance normally 0; recognition of normal connection does not require a "0 space" in the question report. If the two subjects are connected by gaskets, welds, seals, or intermediate connectors, there may be a positive distance between the subjects from the middle thickness, and the measurement value may not be tampered with for presentation purposes to 0, but it is likewise not reported as a normal space problem.

For the `CHECK_CLEARANCE` candidate who needs to continue the check, the numerical rating is:

- `d < 0`: Hard interference;
- `0 ≤ d < C_fail`：FAIL；
- `C_fail ≤ d < C_warn`：WARN；
- `d ≥ C_warn`：PASS。

Of which `d` In order to consider the net range after compensation such as temperature protection, sports packages, etc. `C_fail` and `C_warn` Defines by the rules configuration table.

### 6.4 Centerline and interface consistency

- The central line of the adjacent line, the bend, the triangulation, the French and the equipment mouths shall be continuous;
- An interface location deviation shall not exceed `Tol_position`;
- The axis angle of the interface shall not exceed `Tol_angle`, except for the design corner;
- (b) The interface should be opposite and the relationship is correct;
- (a) The interior is connected and cannot be accidentally blocked by a piped wall, valve or adjacent Body;
- Changes in outer diameter, inner diameter/wall thickness and specifications should be effected by a legitimate anatomy or a transition permitted by the rules;
- French matching inspection specifications, calibres, sealed surfaces, direction, spacing and bolt operating space;
- Open, unconnected and duplicate links should be reported separately.

### 6.5 Turn angle and bend radius

Each turn shall identify the entry axis, the exit axis, the angle, the centre line radius and the cut point.

- (b) The angle of turn should be within the range of the project allowed to be assembled or within the range of the continuous line allowed;
- (a) A curve radius of `R_actual` for the central line of the field shall not be less than `R_min`;
- `R_actual / D_ref ≥ K_min` should be satisfied if it is controlled by a pipe run multiple;
- (b) A minimum direct segment to meet the requirements for manufacture, welding, packaging, testing or docking should be present before and after the bend;
- (a) Continuous reverse bends, space complex bends and small-range acute curves to mark manufacturing/assembly review;
- The estimation of the centre line radius based on the outer contour is not allowed; the output of `NOT_EVALUATED` cannot be reliably identified;
- The hose should check the minimum dynamic/static bend radius, reverse, close-to-wire and motion, without applying rigid tube rules.

### 6.6 Tubing route assessment

The automatic rules include:

- (b) Unnecessary reversals, short knots, continuous small turns or excessive bends;
- (b) Very short direct sections, difficult to weld or uncapable sections;
- (c) The direction of the bronchial, the three-way form and the direction of the alien are not consistent with the rules of configuration;
- (b) Crossing maintenance corridors, unpacking, personnel passages or restricted areas;
- Low-point aqueous fluids, high-point aerogas risk (gravity direction required and medium properties);
- (b) Unreasonable location of the drainage, ventilation or drainage secondary roads;
- (b) Forced misalignment of the equipment and risk of pre-assembly stress;
- (a) No consideration of the insulation, French dismantling, valve operation, instrument reading or tool space;
- The direction and degree of slopes do not conform to the rules for pipes with slope requirements.

The “reasonableness” should be the source of the trigger rule and evidence and must not be based solely on subjective conclusions.

The special rules for short-seat also include:

- (a) Separation/shield of combustible liquid pipelines from ignition sources, thermal surfaces, vent routes and potential direction of spraying;
- Completeness of firewall crossing, fire zone boundary, break valve position and fire-protection grade properties;
- (a) Whether a bursting or needle leaking spray cone is capable of impacting on thermal surface, electrical equipment, gas/ventilation vents or other critical systems;
- Whether the emission pathways of leaked liquids following the break-up of the pipe will form a sap or spread to other regions;
- Whether there is a risk of co-resistance in rotor non-inclusivity, fallout of fan blades or other high-energy debris hazard areas;
- Whether, under relative motion, motor vibrations, thermal expansion of aircraft boxes and hangings, rigid tubes are forced to be moved and the hoses are sufficient and unreverted;
- Whether incompatible or functional redundant circuits are excessively common and whether single-point incidents can damage multiple-road systems at the same time.

### 6.7 Supporting and restraining

- The distance of the first support device, the bend, the valve or the centralized load;
- Whether the adjacent support space exceeds the upper limit by caliber, material, medium and direction;
- (b) Whether there are supporting deficiencies in vertical sections, long arms, valves and heavy attachments;
- Whether the degree of freedom supported by fixed, directed and smoothing conflicts with the intention of the heat shift;
- Whether the support is correctly exposed to, suspended or penetratored to the outer surface of the tube or to the outer surface of the temperature protection;
- Supporting interference with adjacent structures or equipment;
- When payloads and heat analyses are not provided, only geometry and rules checks are performed and no structural strength is claimed.

### 6.8 Wall thickness, physical and curvature

- The outer diameter, inner diameter and wall thickness of the tube shall be consistent with the specifications and shall be continuous along the section;
- The wall thickness should meet `t_actual ≥ t_min` and the local mutation report;
- (b) Double walls, residual seals, slabs or non-flowing entities shall not be present at the end of the tube, at the tributary and at the intersection;
- Curvatures should be checked for gaps, overlaps, self-transactions, abnormality, unclosed borders and micro-faces;
- (b) The cross-section participation in the examination should indicate whether it represents the physical boundary, the envelope or the reference surface;
- In the case of imported non-historical entities, the searchable, but traceable, parameters should be recorded.

### 6.9 Manufacturability, assembly, and maintenance

- The minimum distance between welds, between welds and bend points or attachments;
- (b) Garmenting, decorating, welding, wrench, bolt extraction and non-destructive detection space;
- Whether the sub-assembly is loaded in a feasible direction and whether the geometric locking is in place;
- Whether French, valves, filter cores, instrumentation and replacements have a detachable path;
- Whether the length and weight of the module/sub-section exceed the limits of transport, suspension or installation;
- Whether closed sections or final welds, which must be adjusted on-site, are identified;
- Output risk tips when no manufacturing process parameters are available, and no commitment to process qualification is made.

## 7. Geometric calculations and tolerance differences

- All values are converted to project units in a uniform manner and the use of mm and degree is recommended internally;
- Geometrical variance `Tol_geom` Exposure differential `Tol_contact` Location difference `Tol_position` And the angle is different. `Tol_angle` Separate configuration;
- Candidates accelerate the availability of space indexes or bounding boxes, and final distance and interference must be based on precise geometry;
- (b) Large assembly should support the calculation of increments based on spatial partitions, pipelines, components or variations;
- The same subject, the same location and the problems arising from the same cause should be combined to avoid repeating the alarm;
- The values should be set at the margin of the margin using a consistent inter-segregation/open-space rule, and the original values should be shown in the report.

## 8. Rulesheet

Each rule contains, at a minimum:

| Fields | Annotations |
|---|---|
| Rule_ID | Unique Number |
| Name | Rule name |
| Enabled | Enable |
| Scope | Application of product, pipe, object type or attribute conditions |
| Severity | INFO/WARN/FAIL |
| Threshold | References to thresholds, formulae or standard tables |
| Unit | Units |
| Standard | Standard numbers, versions and articles |
| Exception | Conditions for exemption |
| Evidence | Measurements and transects/views of requested output |
| Owner | Rule-Responsibility |

It is recommended that all thresholds be based on external JSON/CSV/Excel configuration and not die in the inspection process.

### 8.1 Rule change access and coverage of this check

The package must contain a master rule profile that allows manual direct editing, field description and illustrative examples; JSON, for an authoritative running-time format, can be accompanied by a Markdown/table description view. Each report must be at the front of the report with a list of the rules, sources, versions, units, scope of application and any temporary coverage of the actual entry into force.

AI must understand and implement the following three types of rules:

- ** Long-term change**: “The minimum bend radius of this check shall later be changed to 10 cm.” AI shall convert units, position the rule ID, display variations, update the master rule file and keep the version records after confirmation by the user.
- ** This coverage only**: “This curved radius is one quarter of a D inspection.” AI is only included in this operating snapshot, non-polluting long-term rules, and is clearly marked as interim coverage on the first page of the report.
- ** Documentary examination**: “Check as required by this document.” AI should read the specifications/forms/documents provided by the user, extract candidate rules, clauses, units, scope of application and conflict items; the vague content is marked to be confirmed and the value cannot be assumed.

A rule priority, unit conversion, conflict resolution and revision audit must be verified by a certain configuration layer. AI can explain and propose a rule map, but it cannot quietly reformulate the approved rule.

### 8.2 Provisional pilot thresholds (not a compliance basis)

The following values are used only for simple model validation, algorithmic interlinking and problem ranking, and do not constitute design approvals for the aviation model or conclusions of seaworthiness.

| Parameters | Provisional FAIL | WARN/Target | Annotations |
|---|---:|---:|---|
| General route — Geostationary physical net range | `< 6 mm` | `6–12 mm` | Deducted temperature protection, public transport and port transfer; default for small-space test |
| Pipelines - Valid Clear Ranges | `< 6 mm` | `6–12 mm` | Except for connector and approved co-location |
| Pipeline - Sport Convey Effective Spacing | `< 12 mm` | `12–25 mm` | Only the real sports envelope can be officially determined. |
| Pipeline - Ungraded heat source effective net range | `< 25 mm` | `25–50 mm` | Screening only; formal rules must be determined by temperature, radiation, air flow and shielding |
| Minimal curve radius of the hard tube centre line | `< 3D` | `3D–4D` | `D` temporary removal tube exterior; material/process/specification table priority |
| Rigid tube interface position deviation | `> 0.5 mm` | `0.25–0.5 mm` | Use only to check model docking, not substitute for assembly spread analysis |
| Rigid tube interface axis deviation | `> 0.5°` | `0.25–0.5°` | Except for design turn and soft connection. |
| Stereostatic curve radius | `< 8D` | `8D–10D` | Conservative screening value when no data on hose manufacturers |
| Flex dynamic bend radius | `< 12D` | `12D–15D` | Formalization of the need for specific hose data sheets |
| Straight after the hose. | `< 2D` | `2D–4D` | And check the bends and reverses near the interface. |
| The geometry of the route is different. | `0.05 mm` | — | Calculating the tolerance difference, which does not equal the space allowed for the design |
| Exposure classification tolerance | `0.10 mm` | — | To distinguish numerical noise, exposure and penetration |

Support spacing does not set a fixed default value across a caliber. If a standard table is missing, the rules should be used to output `NOT_EVALUATED`, which only check visible suspensions, support penetrating, support non-contact, long-strength and heavy attachments without adjacent support. The convulsion radius of the hose must give preference to directory or zero part number associated manufacturer data.

### 8.3 Threshold priority

1. Model specific design specifications, approved drawings and conformity documents;
2. (b) Customer/master manufacturer supplier regulation and directory of piped routes;
3. Specific versions of SAE/ISO/industry standards approved by the project;
4. Approved engineering analysis, testing or similarity data;
5. The provisional threshold for this SPEC to run on a trial basis.

The lower level does not cover the upper level. Each automatic decision must record the level, document version and article that is actually used.

## 9. Result status and severity

- `PASS`: Complete inspection and meet the rules;
- `WARN`: Approaching limit values, existence of engineering risk or need for review;
- `FAIL`: Violation of explicit rules;
- `NOT_EVALUATED`: Lack of data, inability of object to identify or algorithm not applicable;
- `EXEMPTED`: exclusions based on authorized exemptions;
- `ERROR`: Failed to model, program or calculate.

The component relationship survey has three additional prestates: `PASS_NORMAL_CONNECTION`, `CHECK_CLEARANCE`, `REVIEW_REQUIRED`. They describe whether “the ordinary spacing determination should continue” and do not replace the final rule state. `REVIEW_REQUIRED` is shown in the external report by the review item and cannot be converted to PASS.

Recommendations on severity:

- S1: Information/optimization recommendations;
- S2: General issues, confirmed by the designer;
- S3: Significant problems affecting manufacture, assembly or maintenance;
- S4: Critical issues, hard interference, traffic jams, faulty interfaces or breach of security spacing.

## 10. Output Requirements

### 10.1 Records of individual issues

At least for each question:

- Only Issue ID, rule ID, status and severity;
- Root product, complete component path, example name, zero part number, body/identity/face identification;
- Object A, Object B and their classification;
- (b) The coordinates of the problem position, the direction of the measurement and the nearest point;
- (a) The measured values, limits, units, margin and the tolerance margin used;
- (a) Trigger causes, standard clauses, presumptions of confidence and assumptions;
- Recommended direction and no automatic replacement for engineering design decisions;
- (b) At least two locational maps of meaningful perspectives or a set of CATIA selections;
- Immunity, cause, valid version and time of approval, if applicable.

### 10.2 Summary Report

The report shall include:

- Check scope, exclusion, configuration and model versions;
- Number of problems by pipeline, component, rule, severity;
- List of FAIL/WARN/NOT_EVALUATED;
- List of unloaded, unidentifiable and uninspected objects;
- (a) Standard coverage, target coverage and checking for errors in implementation;
- Additional, resolved, continuing and changing issues compared to the previous baseline;
- General conclusion: Adopted, conditionally adopted, non-adopted or undecided.

Regulate output: Word Reader Report + JSON Machine Readable Authority Results + with Red Boxshot + CATIA Positioning/Selecting Information. CSV can be exported as an optional summary; this project does not generate PDF.

### 10.3 Word Report Layout and Harmonization Template

Each question sheet should include: question number and conclusion; CATIA product tree integrity path; rules and sources; measured/limit values; rectification proposal; and at least two maps: a context overview; a local view. Use a lead, arrow, semi-transparent highlight or size label to indicate the subject; colours agreed to be red FAIL, orange Warn, blue. NOT_EVALUATED Green is confirmed. The cut-off chart must be tied to a structured problem record and cannot be replaced by an unrecoverable cut-off chart.

A single Word reporting template must be maintained in the package. The template is copied and filled in each time it is generated, without any direct deterioration of the master. The reporting order is at least as follows: the rules in force for this time, the model and scope of the inspection, the implementation environment and tools, the overall conclusion, the statistical summary, the list of issues, the details of the questions, the non-assessment/manual review items, the methodological limitations and the audit information.

The CATIA internal locator package should save the object's example path, Part/Body/Feature name, pop-stabilization mark (when available), problem coordinates, camera orientation and selection set. If the pop-up sign lapses after the model has been updated, it should be degraded to rematch the component's path plus coordinates adjacent area and alert the user to confirm.

## 11. Exemptions and misreporting management

- Exemptions must be targeted at clear rules, object pairs and model versions;
- The relevant exemption is defaulted and reassessed after a change in geometry or version;
- (b) Allow connections, excess assembly, welding and design openings to be investigated by AI in combination with semantic and geometric evidence; the exemption granted may still be used as strong evidence, but the list of component types may not be used as an automatic release conclusion;
- (b) No partial misrepresentation may be concealed by widening the global margin;
- Repeated misstatements are translated into auditable rule revisions that do not allow for silent neglect.

## 12. Performance and reliability

- The inspection process shall not modify, update and save or overwhelm the source file;
- Failure of individual rules must not result in the loss of all inspection results;
- Support for interruption, recovery and repetitivity;
- The same model, the version of the rule and the computational environment should have consistent results;
- Full assembly, hard interference, no external intervention. `N×(N-1)/2` Second CATIA COM call; default should be a native DMU `Between All` Computation and extraction of results;
- Non-overall Clash rules, such as insufficient distance, hot zone and maintenance space, should be screened first for object classification, spatial partition, DMU candidate results or AABB/BVH wide phase before accurate calculation;
- Support for the reduction of the size of sub-assembly, space area, system, Line ID, object type and user selection set;
- Supports incremental inspection: eligible historical results can be reused when the geometric version of the component, position matrix, rule version and associated properties remain unchanged;
- Cache must not conceal unsaved locations or geometric changes in CATIA sessions; the Cache key must contain geometric fingerprints of the status of the session or probative value;
- Target performance baseline: 100 active components should be fully equipped Clash within 60 seconds; 1,000 effective components should be completed within 10 minutes. This value is the project acceptance target and should eventually be calibrated according to the company workstation, model complexity and licence environment;
- Individual inspection missions should provide progress, the current phase, the number of conflicts completed, the cancellation and the time-out mechanism;
- The memory use exceeding the configuration ceiling shall be performed by a downgrading of subassembly/space blocks and shall not result in a collapse of CATIA or user sessions;
- All logs should record models, rules, software versions, start/end times and abnormal stacks.

### 12.1 Large-assembly inspection pipeline

```text
Check model health
    ↓
Read the product tree, semantics, and placement
    ↓
Exclude empty or disabled objects and record explicitly approved exemptions
    ↓
Run one CATIA DMU Between All clash check
    ↓
Extract, classify, and deduplicate clash and proximity candidates
    ↓
Gather evidence iteratively and assess candidate design relationships with AI
    ↓
Archive normal connections outside the issue list, apply thresholds to nonconnections, and route uncertainty to manual review
    ↓
Locate, capture, consolidate issues, and report
```

The system should record the time-consuming stages separately so that performance bottlenecks can be distinguished from CATIA calculations, COM data extraction, rule enforcement, cut-off or reporting generation.

## 13. Acceptance tests

The receiving and inspection data set contains at least:

1. (b) Standard pipelines without problems;
2. (b) Physical interference of known penetrators;
3. Examples of borders that happen on both sides of the spacing threshold;
4. (a) Cross-references allowing connection to contact and unexpected collisions;
5. (a) An interface that is faulty, reverse, disconnected and blocked;
6. (a) A qualifying and unqualified bend radius, corner and straight segments;
7. Three examples of unreached cavity through the bronchial wall to the supervisor;
8. (b) Examples of instances where support is lacking, hyperspace, support for suspension or penetrating;
9. Examples of temperature protection, sports packages and inadequate space maintenance;
10. Importing entities, curves, missing references and invalids;
11. Examples of cases where exemptions have been granted and the exemptions have lapsed following changes in models;
12. Examples of high-assembly performance, incremental checks and repeated implementation consistency.
13. 100/1,000 Primary Between All performance test at component scale and verification that COM calls were not made on a log-on basis;
14. CATIA Native Clash results compared to artificial DMU results;
15. Run-fault filters for expected relationships, such as physics tubes, French matching, installation contacts, etc.
16. (a) Model reading, inspection, rule enforcement and basic reporting testing after complete disconnection from the Internet;
17. Temporary Clash/Distance/Group object clean-up, selected set restoration and source model not saved for validation.

For each rule, there must be examples of formal, contrived and differential boundaries.

## 14. Application of the principles of border and CATIA integration

- Use CATIA structured objects, pouncers, measure and assemble trees as a factual source;
- Record the model list/baseline before inspection and do not change the source model state after inspection;
- Numerical Tubing Design data should be clearly distinguished from normal parameterization geometry;
- (b) When there is no synonym for a primary tube, a geometric inference may be used, provided that the origin and confidence are marked;
- (a) The cut-off chart is only evidence and cannot be a substitute for structured measurements;
- Additional automatic fixes should be followed by a separate SPEC and a preview, minimum reversibility, updated validation, pre- and post-list comparison and user confirmation process.

### 14.1 Agent Implementation Process

1. Connect CATIA, listing documents, confirming and activating the target model by name, type and path;
2. Identify input types such as CATIA or STEP/STP, IGES/IGS, and save read-only baseline;
3. Native models read assembly, binding, attributes and Tubing Design syntax; dumb model implementation entity classification, route/connector identification and confidence assessment;
4. (a) Contain the main rule and this coverage to produce an immutable snapshot of this rule;
5. (a) Call the `prepare` type tool for initial collection of model health, candidate pairing, interference, spacing and route geometric facts;
6. AI reviews evidentiary gaps and uses clear measurement, scaling-up, neighbourhood, assembly and viewing tools around suspect components autonomously until they are sufficient or are determined to be undecidable;
7. AI Output relationship judgement, rationale, confidence and key evidence; `finalize` validates quoted facts, enforces threshold rules, deweights and solidifies results;
8. (a) To give an itemized/unassessed condition for the curved radius, R/D, interface continuity, pipe spacing, support and other activated rules and not to jump silently because the model is not original;
9. Generate context maps and detail view for questions and review items, and produce red-boxed labels;
10. Generate JSON and Word by a uniform template; normal connections are reserved only in the JSON audit and no problem pages are entered;
11. User review results and decision to accept, return or establish a time-limited exemption;
12. The whole process does not modify or save the source model. Any future change proposal is only recommended text.

### 14.2 Minimum model properties requirements

In order for Agent to be raised from “visible geometry” to “enable for engineering determination”, the supplier model should provide at least: Line ID, medium, rigid/soft class, outer diameter, wall thickness or inner diameter, material/specification, design temperature, work pressure, fire-protection grade, direction, port and connector, type of support, and fire zone and heat source/motion package references. In the absence of these attributes, the report must include data integrity gaps.

## 15. Legislation and standard baselines

### 15.1 Airworthiness and safety requirements

- [EASA CS-25.1181-25.1203](https://www.easa.europa.eu/en/document-library/easy-access-rules/online-publications/easy-access-rules-large-aeroplanes-cs-25): Capture requirements for designated fire zones, combustible liquid components, firewalls, fluid ventilation and shutdowns for short-seat use. CS 25.1183 requires that flammable liquid pipelines/annexes in the fire zone have the corresponding fire resistance and are equipped or shielded to prevent leaking liquids from being ignited; CS 25.1187 requires effective effluents and ventilation.
- CS 25.1185 gives an explicit requirement for a gap between the tank/reserver and the firewall or shield of at least 13 mm of net air; this value applies only to the subject of the clause and cannot be extended to the general spacing of all pipes.
- AMC 25.1189 states that the risk of a fire is exacerbated by the formation of a leak from high-pressure fine holes and requires an analysis of the volume of emissions following the break-up by each combustible liquid system and by each fire protection area. Agent can check geometric pathways and attribute integrity, but cannot substitute for fire safety analysis.
- ISO 2685 may be used as a source of fire-resilient test methods for the specified fire zone equipment; model checks can only verify that the required grade attributes, areas and evidence are complete and cannot be extrapolated from the CAD shape to qualify for tests.

If the project uses the FAA basis for authentication, a corresponding 14 CFR Part 25 article map should be established; if the engine is checked instead of a short-seat installation, the model application for Part 33/CS-E should be supplemented. The basis for final certification is approved by the model airworthiness team and Agent does not choose.

### 15.2 Candidate tubing standards

- [SAE ARP994C](https://saemobilus.sae.org/standards/arp994b-design-tubing-installations-aerospace-hydraulic-systems): Aviation hydraulic tubes, hoses and interface design selection exercises covering topics such as placement, support, stress and soft compensation; the official latest version of the procurement is followed by the entry of a specific value sheet.
- [SAE AS18802](https://saemobilus.sae.org/standards/as18802-fuel-oil-lines-aircraft-installation): Aircraft fuel and ski pipeline installation requirements, but their public scope expressly excludes the pipelines provided with the engine as part of the engine, which must be used in order to determine the boundaries of the supplier model.
- [SAE AIR 5386A](https://saemobilus.sae.org/standards/air5386a-hose-hose-assembly-selection-installation-inspection-maintenance-guidelines-listing): Index of guidelines for the selection, installation, inspection and maintenance of air hoses and hose components.
- SAE AIR 5426: Guidance on the selection, installation, inspection and maintenance of the interface and interface components.
- SAE AS683E: installation program for fluid connectors and twists; geometry Agent can check the type, space and properties of the interface, which still needs to be constructed/assembled with data closed loops.

This SPEC currently uses only a public scope description, and does not pretend the terms or values in its payment body. The project should purchase the applicable version, which is confirmed by the design, seaworthiness and standardization staff, and then forwards the approved values to the controlled rules house.

### 15.3 Standard-based decision-making

The standard is not “as many as possible”. Each rule must establish a retroactive chain of `法规目标 → 符合性方法/行业标准 → 型号设计规则 → Agent 可计算条件`. The requirement of CAD proof should not be translated into a pseudo-geometric rule.

## 16. Parameters to be confirmed (TBD)

1. (a) The base for the certification of the target aircraft: CAAC/FAA/EASA, and the level of specific amendments;
2. Model boundary of the supplier: installation of a pipe, engine hull, or interface between the two in the short module;
3. Line ID classification, list of media, temperature/pressure level and fire-protection level dictionary;
4. Main manufacturer/client standard, supplier DQMR and procured SAE/ISO standard version;
5. Data on fire protection areas, heat sources, rotor hazard areas, institutional movements and relative transfer of engines;
6. Formal spacing, curved radius, diameter, interface and supporting rules by object and area;
7. CATIA Tubing Design name, directory, connector, specification and attribute agreement;
8. Simple validation of expected results of models and subsequent representative qualified/unqualified models;
9. Reporting template, language, signing process, exemption from liability and access to PLM/QMS;
10. Model size, target running time, sensitive data segregation and audit retention period.

## 17. Intranet and offline deployment requirements

### 17.1 Deployment targets

The system must support the deployment to the company’s Windows intranet workstation.

- Connecting to local CATIA V5;
- (b) Read CATProducing/CATPart/Tubing Design;
- Perform DMU Clash, Distinction and pipe certainty checks;
- Loading of the locally controlled repository;
- Run intranet AI investigation decision loops and generate local JSON, Word and red box screenshots;
- Maintain audit logs and recapable location data.

Natural language AI capabilities are divided into symbiotic layers:

| Deployment pattern | Geometry and Rules Checking | Natural language interpretation | Data Outgoing |
|---|---|---|---|
| intranet pure offline (no model) | Geometric facts and numerical rules are available; relationship judgement downgrade review | Templateed Text | None |
| Intranet Large Model (Target Mode) | Full closed circle. | Corporate intranet deployed and approved large model proactive survey and judgement | No company, intranet. |
| Enterprise AI Gateway | Full closed circle. | Active survey and judgement of approved cloud/host models | Allow sending only approved data fields |

The default target for this project is the “corporate intranet large model” model. AI's non-availability or failure to call must not interrupt the geometric and numerical rules that are in place, but all relationship judgements that rely on design intent must be downgraded to `REVIEW_REQUIRED` and identify capability gaps in the report.

### 17.1.1 Corporation intranet large model adaptation

- The AI layer must be accessed through an independent `LLM Adapter` interface, and no specific manufacturer, model name or SDK should be written to the CATIA core;
- Supports at least the HTTP/HTTPS reasoning interface provided by the company; if the interface is compatible with OpenAI API, the public address is prohibited as the default value for the intranet version by configuration toggle Base URL, model name, rights and overtime;
- (a) Supporting the extension of adapters for non-OpenAI compatible interfaces, including the corporate unified AI gateway, the privatization reasoning platform or the internal Agent platform;
- Accuracy information must be read from company-approved certificate services, environmental configurations or controlled key files and may not be written into codes, rule files, logs and reports;
- Model call input should give priority to structured inspection results, rule clauses, component desensitization markers and necessary context, and should not default on the transmission of complete CAD files or unrelated model trees;
- Intranet and version control should be used for alerts, glossarys, reporting templates and knowledge base;
- If RAG is used, the search source is restricted to approved corporate norms, model codes, standard summaries, historical repositorys and clean-up cases, and document versions and reference clips are recorded;
- Each AI output must be traceable to: model version, hint version, knowledge base version, input Issue ID and generation time;
- A large Intranet model can generate inspection plans, tool call decisions, object/relationship classification, design reasonableness judgement, interpretation and rectification advice; it should not cover measured values given by CATIA/geometric tools, controlled rule thresholds or `finalize` (a) The results of the consistency verification;
- When the AI output is in conflict with the certainty result, the CATIA original result and the controlled rules are determined and `AI_CONFLICT` is recorded;
- AI may not call CATIA to modify, save, delete, publish or submit PLM without approval.

### 17.1.2 Intranet Large model capability acceptance

Intranet large model access at least validates:

1. (b) The understanding and interpretation of the object range of the Chinese project directive;
2. Structured Clash/measured results accurately repeated without altering values and units;
3. (a) Rules-based ID, severity and root cause clustering;
4. (a) The generation of retroactive rectification recommendations based on approval of the knowledge base;
5. Automatically generate summary reports, issue notes and vendor feedback texts;
6. Injection, ultra vires operation and protection against disclosure of sensitive information;
7. (a) Service overtime, restricted flow, automatic downgrading when models are not available;
8. A key factual consistency test for the same structured input.
9. Five types of relationship determination test for normal straight-link, pipe-link, non-connected perigee, abnormal penetration and insufficient evidence;
10. AI is able to select the appropriate instrument to supplement the evidence in the first round and to stop the cycle in the absence of additional evidence;
11. STEP/IGES is able to rely on geometric evidence or to pass a conservative manual review when it lacks name and discipline.

AI Quality indicators include, at a minimum, the maintenance rate of factual values, the correct rate of rule references, the rate of unfounded conclusions, the rate of acceptance of corrective recommendations and the workload of manual reviews; formal thresholds are approved by the corporate project team.

### 17.2 Environment and dependency

- Intranet targets CATIA V5 R30 (Release 30); confirm the range of support upon completion of the compatibility check for the target machine. Other CATIA V5 Releaase independently validates it against the compatible matrix; the current development version does not constitute the target machine requirement, and specific Service Pack/HotFix and licences must be included in the receipt and inspection;
- Python, pywin32, MCP services and reporting depend on the availability of offline installation packages, version locks and document validation values;
- Python must match CATIA COM digits;
- Tubing Design, DMU Space Analysis and related catalogue licences must be detected separately during self-inspection;
- CATIA Catalog, Tubing Standard, Specialisations and Design Rules Paths must be configured and cannot write a dead developer path;
- Supporting company intranet file servers, controlled temporary catalogues, Chinese path and a read-only supplier model catalogue;
- The installation procedure shall not require administrator authority unless the company's deployment programme has been explicitly approved.

### 17.3 Data security

- Default not to send CATPart, CATProduct, screenshot, complete assembly tree, zero part number or coordinates to the public network;
- When using the Enterprise AI gateway, send only a summary of the results of the rules, with the name of the dissensitized component and the project identifier according to the company's strategy;
- All outgoing fields, target addresses, call times and response status must be audited;
- Local temporary STL, screenshot, Clash export and reporting intermediate files should be located in the controlled directory and automatically cleaned as configured;
- (a) The system should not automate the CATIA structured interface and company security controls through desktop screenshots or keyboards;
- The source model is always read-only unless an automatic repair of SPEC is approved separately in the future.

### 17.4 Commence self-inspection

Check at least on startup of intranet version:

1. CATIA processes, versions, digits and activity documents;
2. COM/MCP connectivity;
3. (a) Auto-interfaces for Project Structure, SPA/DMU, Tubing Design;
4. The required licences and directories;
5. (a) Rule library versions, signatures and required fields;
6. Read-and-write permission for temporary directories, report catalogues and log catalogues;
7. Offline reporting is dependent;
8. AI service status, only as options, does not affect core check startup.

## 18. v2.0 Minimum deliverables

V2.0 Achieving must be satisfied at the same time:

1. (a) The current activity CATProduct structured identification and baseline;
2. CATIA DMU `Between All` Single full assembly Clash scan;
3. (a) Original Clash review of assigned components;
4. (a) Arrengement Run-Run and Run-Entities for certainty checks;
5. (b) Pyropathic, nodal, length, bend angle, bend radius and R/D checks;
6. (a) Empty parts, orphan shape expression and unloaded reference identification;
7. AI-led `prepare → 调查取证 → finalize` relationship judgement framework, not dependent on the static component exemption list;
8. (a) Geometric diversion, route identification, proximity survey for STEP/STP, IGES/IGS, and carrying out inspections of the convulsible convex radius/R/D;
9. JSON rules configuration, natural language/file rules entry and PASS/WARN/FAIL/ NOT_EVALUATED / EXEMPTED/ERROR and three state of relationship;
10. (b) Evidence maps of at least two perspectives, copies of red box labels, CATIA positioning information and the Word template report;
11. The normal design connection is auditable in JSON but does not enter the Word list of issues or questions;
12. The whole process does not save the source model and the temporary DMU object is completely cleaned;
13. (a) Operatable core closed loops in completely de-netted states;
14. Standard test models can repeat the same measurement facts; AI relationship conclusions must be changed in such a way as to retain a version of the model/tip/evidence for audit purposes.

The following are not v2.0 declarations of completion: automatic modification of models, automatic submission of PLMs, alternative seaworthiness approvals, declared strength/thermal safety clearance in the absence of payloads and temperature boundaries.

## 19. Exception handling and recovery

| Unusual | The action that must be taken. |
|---|---|
| Could not determine model format or active document | Discontinue formal determination, list candidate documents and evidence, and require user confirmation of target; no speculation to save |
| CATIA/DMU tools or licences not available | Record failure and impact ranges; validated back-up algorithms may be used, provided that the method and accuracy are indicated |
| STEP/IGES components cannot be reliably divided | Keep geometry and candidate relationships, output `REVIEW_REQUIRED`, not declare no problem |
| Insufficient confidence recognition of piped or curved radiuss | Continue to attempt cross-section, cylindrical/circle surface, central line and adjacent area evidence; still insufficient `NOT_EVALUATED/REVIEW_REQUIRED` |
| AI Conflict of judgement with geometric facts | `AI_CONFLICT` is recorded, based on the measurement of facts, and Finalize is forbidden to pass automatically |
| AI Timeout, Unusable or Invalid Output | Preservation of current evidence, retrying up to configuration; downgrading of relationship semantic items manual review and continuation of the project for certainty |
| Lack of rule files, unknown units or multiple norm conflicts | No guess thresholds; display of conflicts and priorities, requirement of confirmation or use of clearly marked test running rules |
| Could not close temporary folder: %s | Result tag `ERROR` to remind users to check sessions; no source model is saved |
| Failed to create screenshot or red box | Retain structured problems but marking evidence is incomplete and the report should not pretend that the picture has been generated |
| Word Generation Failed | Retain JSON, original graphs, tabulations and logs and can retry the reporting phase separately without repeating geometry checks |

## 20. Implementation and acceptance status

- The current realized baseline is at `release_build/CATIA_V5_AI_DROP_V4_4_DEV` for local testing to continue, leaving the final release package unsealed.
- There are currently 31 CATIA MCP read-only tools, self-checking, structured JSON, Red Box Evidence Charts, Word Report, rule snapshots and AI Relationship Survey interfaces available.
- The local process validation of the current development environment cannot replace the intranet inspection; it will not be signed until the connection, tool capacity, reporting dependence, and representative model regression tests are completed on the real CATIA V5 R30 (Release 30) target. R18 is no longer the goal of this project intranet.
- The provisional rules for items are still not model approval rules; the formal rules must be reruned after they have been imported and the current rules in effect are shown on the front page of the report.
- STEP/IGES free curvature centre line restoration and complex floppy recognition are continuing improvements; where reliable measurements are not possible, they must be reviewed in a visible manner and must not be omitted silently.
