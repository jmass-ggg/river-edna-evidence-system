# FreshWater — eDNA Evidence Investigator
## Complete Project Description, Architecture and Workflow

### 1. Project Overview

**Project name:** FreshWater — eDNA Evidence Investigator

**Domain:** Environmental monitoring, freshwater ecology, environmental DNA (eDNA), hydrology, decision-support systems and One Health.

**Purpose:** Help environmental researchers investigate uncertain species detections in freshwater ecosystems, identify plausible upstream sources and determine where to collect the next water sample to reduce uncertainty.

FreshWater is a scientific decision-support platform designed to turn uncertain environmental DNA observations into actionable freshwater monitoring decisions.

Traditional eDNA monitoring allows scientists to detect biological organisms by collecting water samples and analyzing the genetic material they contain. However, detecting a species' DNA does not necessarily establish where the organism lives.

DNA may have traveled downstream, some sampling replicates may be positive while others are negative, and environmental conditions may affect the detection.

These uncertainties make it difficult for researchers to determine where a species may be located, what the evidence actually supports and where to investigate next.

FreshWater addresses this problem by combining eDNA observations, river-network hydrology, ecological information and environmental context.

Rather than simply reporting a species detection, the platform investigates the evidence and helps researchers plan a more informative follow-up sampling strategy.

**The central question the project answers is:**

*We detected DNA from a particular species in this river. How reliable is the observation, where could the DNA have originated, and where should we sample next to distinguish between the possible explanations?*

---

### 2. The Real-World Problem

Freshwater monitoring is essential for understanding biodiversity, identifying ecological changes and supporting environmental management.

Urban freshwater systems face additional pressures from urban development, runoff, habitat modification, pollution and other human activities.

Researchers can use eDNA to monitor these ecosystems, but several problems remain.

**Problem 1: Uncertain detections**

A water sample might return two positive eDNA replicates and one negative replicate.

This creates uncertainty about the consistency of the observation. Researchers need to determine what the results support and which explanations remain possible.

**Problem 2: Unknown source location**

DNA collected at one river location may have originated farther upstream.

A positive detection at a downstream station does not necessarily mean that the species is present at that exact location.

**Problem 3: Inefficient follow-up sampling**

Researchers have limited budgets, equipment, time and field personnel.

Collecting samples from many arbitrary locations can be expensive and may fail to resolve the original uncertainty.

**Problem 4: Fragmented environmental evidence**

Relevant information may be distributed across eDNA datasets, river-network data, biodiversity databases, environmental measurements and urban land-use information.

Researchers need a way to examine this information together without confusing contextual evidence with confirmed biological observations.

**Problem 5: Limited decision support**

Monitoring systems often focus on displaying observations rather than helping researchers decide which field investigation to conduct next.

FreshWater is designed to address these five problems.

---

### 3. Target Users

The platform is intended for:

- Freshwater ecologists and eDNA researchers investigating species detections.
- Environmental monitoring agencies assessing rivers and urban waterways.
- Biodiversity conservation teams monitoring sensitive or invasive species.
- Water-resource managers planning monitoring campaigns.
- Research institutions examining ecological and environmental change.

Its primary user is a researcher or monitoring professional who needs to interpret an uncertain observation and plan a scientifically defensible follow-up investigation.

---

### 4. What the System Takes as Input

FreshWater combines primary sampling observations with supporting geographical and environmental data.

**Input A: eDNA observations**

The primary input is an eDNA sampling record containing information such as:

| Field | Example |
|---|---|
| Target species | Species X |
| Sampling location | Site A |
| River | Wigger River |
| Coordinates | Latitude and longitude |
| Sampling date | Date of collection |
| Replicate 1 | Positive |
| Replicate 2 | Positive |
| Replicate 3 | Negative |
| Detection metadata | Available laboratory or assay information |

Where available, the system can also receive replicate-level measurements, laboratory controls, assay information, detection limits and other relevant quality metadata.

The observations may be entered manually or imported from a structured dataset.

**Input B: River-network and hydrological data**

The system requires geographical information describing the river network.

For the demonstration case, it uses HydroRIVERS data, which contains river-reach geometry and connectivity information.

Relevant attributes include:

- River-reach identifiers.
- Geographic coordinates and river geometry.
- Upstream and downstream connectivity.
- River lengths.
- Available drainage-area and discharge estimates.

These data allow the system to determine which river reaches are upstream of the original sampling location and how different tributaries connect.

**Input C: Ecological and biodiversity information**

Where available, the system can incorporate supporting ecological information, including:

- GBIF species-occurrence records.
- Historical observations of the target species.
- Species distribution and habitat information.
- Other relevant field observations.

These sources provide ecological context, but an occurrence record alone does not establish that a species is currently present at an eDNA sampling location.

**Input D: Urban and environmental context**

The system can incorporate environmental information relevant to freshwater monitoring, including:

- Urban and natural land-use information.
- Temperature.
- Rainfall.
- Available environmental measurements.
- Relevant urban pressure indicators.

Where reliable data exist, additional information about stormwater, wastewater or other environmental stressors can be incorporated.

Environmental datasets must retain their sources, dates, spatial resolution and quality metadata. Missing information should be clearly identified rather than estimated without justification.

---

### 5. How the System Processes the Information

The system follows a scientific investigation workflow with five main stages.

#### Stage 1: Evidence assessment

FreshWater first examines the original eDNA observations.

It checks the sampling information, replicate results and any available quality metadata.

For example:

- Replicate 1: Positive.
- Replicate 2: Positive.
- Replicate 3: Negative.

The system recognizes that the results are inconsistent and that further investigation may be necessary.

It distinguishes what was observed from what can reasonably be inferred.

The evidence assessment should communicate whether the observations are supported, uncertain or conflicting, along with the reasons for that assessment.

The platform must not assign an invented numerical probability or treat the number of positive replicates as a complete measure of scientific confidence.

When information is insufficient, it should explicitly report that the relevant aspect of the evidence remains unassessed.

**Output of Stage 1:** An evidence summary describing the observation, its limitations and the uncertainty that requires investigation.

#### Stage 2: Hydrological investigation

The system identifies the original sampling location, Site A, and connects it to the river network.

It then uses river connectivity to identify reaches that are genuinely upstream of Site A.

It must use actual river-network topology rather than simply selecting nearby geographical locations.

For the Wigger demonstration, the investigation uses HydroRIVERS reach identifiers and their upstream/downstream relationships.

The system constructs an upstream river graph and identifies plausible source zones.

These zones may include separate tributaries and upstream river sections that could contribute DNA to the downstream sampling location.

For example:

- Z1: One upstream river section.
- Z2: A second upstream tributary.
- Z3: A third upstream tributary.

The interface should visualize these zones and show how they connect to Site A.

The system can also calculate river-network distances and identify relevant tributary junctions.

Hydrological connectivity establishes whether a source is geographically plausible according to the river network. It does not independently prove that DNA originated there.

**Output of Stage 2:** A verified upstream river network, plausible source zones and their hydrological relationships to Site A.

#### Stage 3: Investigate competing explanations

After establishing the river network, FreshWater examines the explanations consistent with the available observations.

For example:

- Hypothesis 1: The DNA originated in upstream zone Z1.
- Hypothesis 2: The DNA originated in upstream zone Z2.
- Hypothesis 3: The DNA originated in upstream zone Z3.
- Hypothesis 4: The observation reflects a local source, contamination or another explanation that requires investigation.

The system evaluates these hypotheses using the available evidence.

It considers hydrological connectivity, the original eDNA observations, available ecological records and relevant environmental context.

Each source must be interpreted according to what it can actually establish.

For example, a connected upstream tributary may be a hydrologically plausible source. A historical species record may provide ecological context. Neither observation independently proves that the species is currently present in that tributary.

The platform should distinguish among:

- Evidence supporting an explanation.
- Evidence conflicting with an explanation.
- Information that is neutral or insufficient.
- Explanations that cannot currently be assessed.

Only scientifically justified assessment rules should produce categorical evidence-strength classifications.

If an evidence source has not been validated for a particular inference, its classification must remain unassessed.

**Output of Stage 3:** A structured comparison of competing explanations, their supporting or conflicting evidence, unresolved uncertainties and relevant limitations.

#### Stage 4: Recommend the next sampling location

This is the main decision-support component of FreshWater.

The system determines which additional sampling location could help distinguish between the competing explanations.

For example, if Site A is downstream of two tributaries, the original positive observation might be consistent with a source in either tributary.

The system could identify the following candidate locations:

**Site B:** A sampling point in the first tributary, upstream of its convergence with the second tributary.

**Site C:** A sampling point in the second tributary, upstream of the convergence.

**Site D:** An alternative main-stem location that may provide additional information or help verify downstream transport.

The system evaluates these candidates using their position in the river network and the competing hypotheses they can distinguish.

For example, sampling separately at B and C may provide useful information about which tributary contributes DNA to the downstream sampling point.

The decision must account for the fact that a positive or negative result does not provide absolute certainty. Detection variability, DNA transport, sampling conditions and other explanations remain relevant.

The system must not automatically recommend a site merely because it is upstream, close to the original station or associated with a visually prominent zone.

A recommendation is justified only when an explicit decision rule establishes that it can meaningfully distinguish the relevant explanations.

If several candidates cannot be distinguished using the available information, the system should report the unresolved choice. If none provides sufficient discriminatory value, it should abstain from recommending a specific location.

Where justified, the sampling plan can also describe suitable replication, timing considerations and the observations needed to evaluate each hypothesis.

**Output of Stage 4:** A scientifically justified sampling recommendation, or an explicit statement explaining why a unique recommendation cannot currently be made.

#### Stage 5: Urban freshwater and One Health interpretation

FreshWater connects the investigation to its broader environmental significance.

The system considers relevant urban and ecological context to help researchers understand why the investigation matters.

For example, a monitoring location may be near an urbanized catchment, a biologically important habitat or a waterway used by nearby communities.

Depending on the target species and the available evidence, resolving its presence and distribution may support:

- Biodiversity conservation.
- Monitoring of invasive or sensitive species.
- Investigations of ecological change.
- More targeted monitoring of urban waterways.
- Planning of subsequent environmental assessments.

The One Health component communicates how the monitoring decision may relate to ecosystem health, animal populations and human communities.

It must distinguish a potential environmental implication from a directly demonstrated health or ecological impact.

A species detection alone must not be interpreted as proof of pollution, disease risk, population abundance or an immediate threat to human health.

**Output of Stage 5:** A concise explanation of the ecological and One Health relevance of the investigation, the decision it supports and any further evidence needed.

---

### 6. What the System Produces

After processing the inputs, FreshWater presents its findings through an interactive scientific workspace.

The main outputs are:

**Output 1: Evidence summary**

A concise explanation of the original observation.

It should communicate:

- What species was detected.
- Where and when the sample was collected.
- What the replicate results show.
- What the evidence supports.
- What remains uncertain.

**Output 2: Interactive river map**

A geographical visualization displaying:

- The original sampling location, Site A.
- The verified upstream river network.
- Plausible source zones Z1, Z2 and Z3.
- Relevant tributaries and their connections.
- Candidate sampling locations B, C and D.
- The selected next sampling location, when a recommendation is justified.

Users should be able to select locations and inspect their associated data.

**Output 3: Source investigation**

A structured explanation of the possible upstream sources, including hydrological plausibility, relevant evidence, competing explanations and unresolved questions.

**Output 4: Sampling recommendation**

A practical field recommendation explaining:

- Where to sample next.
- Why that location was selected.
- Which competing explanations the sample could distinguish.
- What positive and negative results would mean.
- Which uncertainties would remain afterward.

If the information does not justify a specific recommendation, the system should explain why.

**Output 5: Environmental and One Health context**

A concise explanation of how the investigation relates to freshwater biodiversity, environmental monitoring, urban pressures or relevant community concerns.

**Output 6: Investigation report**

A report that researchers can use to review or communicate the investigation.

It should contain the original observations, data provenance, evidence assessment, hydrological findings, competing hypotheses, sampling decision, scientific assumptions and limitations.

---

### 7. Complete Example of How the Project Works

Consider a researcher investigating Species X in the Wigger River in Switzerland.

**Step 1: Initial observation**

The researcher collects water at Site A and obtains three eDNA replicate results:

- Positive.
- Positive.
- Negative.

The researcher wants to understand the observation and identify an informative follow-up sampling location.

**Step 2: Upload the data**

The researcher enters or imports the sampling record, including the species, coordinates, date and replicate observations.

The platform associates Site A with the river network.

**Step 3: Assess the evidence**

FreshWater examines the replicate results and available quality information.

It identifies what can be concluded from the existing observation and explains the remaining uncertainty.

**Step 4: Investigate the river**

The hydrological engine identifies the connected upstream reaches and constructs the upstream river network.

It identifies source zones Z1, Z2 and Z3.

**Step 5: Compare explanations**

The system investigates whether each source zone is hydrologically plausible and evaluates any relevant supporting ecological or environmental information.

It records the evidence and limitations associated with each explanation.

**Step 6: Evaluate additional sampling**

The platform identifies candidate sites B, C and D on the real river network.

It evaluates whether observations at these locations could distinguish between competing source explanations.

For instance, separate samples collected upstream of a tributary convergence could help determine which tributary contributes the detected DNA.

**Step 7: Present the decision**

If the decision criteria justify a particular site, the platform presents the recommendation and explains its reasoning.

Otherwise, it reports the unresolved choice or abstains.

**Step 8: Communicate environmental relevance**

The platform displays any supported ecological and urban context, along with the implications for subsequent monitoring.

The final result is an evidence-based investigation and a practical plan for reducing uncertainty.

---

### 8. Scientific Demonstration and Scalability

The initial scientific demonstration is based on the Wigger River in Switzerland.

It uses a real river network to investigate upstream connectivity, source zones and candidate sampling locations.

Historical eDNA research, including the Carraro Wigger study, is relevant to the intended scientific-validation workflow.

The architecture should not be limited to the Wigger River. It should separate the general investigation methods from the datasets and assumptions specific to the demonstration.

The long-term objective is to support investigations in other freshwater systems when suitable river-network data, sampling observations and the necessary scientific assumptions are available.

The platform must distinguish between functionality that has been implemented, methods validated using real observations and proposed capabilities that still require development or scientific evaluation.

---

### 9. Core Product and Scientific Principles

The platform must follow these principles:

1. **Evidence before conclusions:** Report what the observations actually establish and make uncertainty explicit.

2. **Real hydrological connectivity:** Use verified river-network relationships rather than arbitrary geographical proximity.

3. **Transparent scientific reasoning:** Every assessment and recommendation should have an understandable justification.

4. **No invented confidence:** Do not assign arbitrary numerical certainty or unvalidated evidence-strength classifications.

5. **Meaningful sampling decisions:** Recommend additional sampling only when it can help resolve a relevant uncertainty.

6. **Clear separation of evidence and context:** Ecological and environmental information should not be presented as direct evidence when it only provides context.

7. **Explicit limitations:** Missing data, uncertain assumptions and unresolved explanations must remain visible.

8. **Human oversight:** The platform supports scientific decision-making; it does not replace the judgment of environmental researchers.

---

### 10. Product Experience and Interface Requirements

FreshWater should look and behave like a professional scientific monitoring platform rather than a generic analytics dashboard.

Its interface should prioritize four questions:

1. What was detected?
2. What does the evidence establish, and what remains uncertain?
3. Where are the plausible upstream sources?
4. What should the researcher investigate or sample next, and why?

The river map should be the central visual element of the investigation workspace.

Evidence assessments, source explanations and sampling recommendations should appear in a clear information hierarchy that allows researchers to understand the findings without navigating through unnecessary visual elements.

The design should be minimal, professional, scientifically credible and accessible. It should use consistent geographical colors, readable typography and clear explanations.

Charts, statistics, status indicators and other visual elements should appear only when they communicate information relevant to the investigation.

The application should never make its conclusions appear more certain than the underlying scientific evidence justifies.

---

### 11. What Makes the Project Distinctive

FreshWater is not simply an eDNA detection dashboard, a species-distribution map or a general river-monitoring application.

Its focus is the transition from **an uncertain observation to a defensible next investigation**.

It connects five capabilities within one workflow:

- Evidence assessment to identify what is known and uncertain.
- Hydrological analysis to establish plausible upstream sources.
- Hypothesis comparison to examine competing explanations.
- Sampling decision support to identify informative follow-up measurements.
- Environmental and One Health interpretation to explain the wider relevance of the monitoring decision.

The central contribution is not simply collecting more environmental data. It is helping researchers determine which additional evidence would be most useful.

### 12. Final Project Summary

FreshWater — eDNA Evidence Investigator is a scientific decision-support platform that helps researchers investigate uncertain freshwater species detections.

It takes eDNA observations, sampling metadata, river-network information and available ecological and environmental context as inputs.

It assesses the observations, constructs the connected upstream river network, identifies plausible source zones, compares competing explanations and evaluates potential follow-up sampling locations.

It produces an interactive investigation map, a transparent evidence summary, a source investigation, a justified sampling recommendation when possible, and an explanation of the ecological and One Health relevance.

**Its ultimate objective is to help freshwater monitoring teams move from uncertain eDNA detections to more targeted, transparent and scientifically defensible field investigations.**
