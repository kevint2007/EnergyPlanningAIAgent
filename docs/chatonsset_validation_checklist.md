# ChatOnSSET Validation Checklist

## Purpose

This checklist tracks the validation status of the current ChatOnSSET prototype before the July 1 asynchronous update. The goal is to show that core answers are generated from deterministic Python calculations, while the LLM is used only to explain structured outputs.

Core rule:

> Python calculates. The AI explains.

---

## Active Scenario

- Country: Mozambique
- Active scenario file: `mz-3-0_0_0_0_0_0.csv`
- App file: `app.py`
- Data mode: deterministic Python summaries
- LLM role: narrative formatting and explanation only

---

## Sprint Changes Completed

| Area | Status | Notes |
|---|---:|---|
| Policy-prescriptive language removed | Complete | Responses avoid implementation advice and policy prescription. |
| Investment-specific deterministic branch | Complete | Investment queries now return only investment results, not a full national report. |
| Connections-specific deterministic branch | Complete | Household connection queries now return targeted connection outputs. |
| Household connections by milestone year | Complete | Shows 2025 step and 2030 step household estimates. |
| Average cost per household connection | Complete | Calculates national and technology-specific average cost per household connection. |
| Methodology toggle | Complete | Methodology can be shown or hidden from standard responses. |
| Response mode selector | Complete | Adds Concise and Technical response modes. |
| Unsupported query guardrails | In progress | Existing guardrails work for some unsupported questions; should be tested more systematically. |
| Scenario selector | Not started | Planned next architecture step. |
| Document-based validation / RAG | Not started | Planned later, especially if official project documents are provided. |

---

## Core Calculation Validation

### 1. Investment by Technology

**Test question**

```text
What is the total capital expenditure required for each electrification technology by 2030?
```

**Expected behavior**

- Returns total modelled CAPEX.
- Returns technology-disaggregated CAPEX.
- Does not include unrelated population, capacity, mini-grid, or connection sections.
- Does not prescribe policy actions.

**Formula**

```text
(InvestmentCost2025 * ElecStatusIn2025) + InvestmentCost2030
```

**Columns used**

- `InvestmentCost2025`
- `InvestmentCost2030`
- `ElecStatusIn2025`
- `FinalElecCode2030`

**Validation status**

- [x] Tested in app
- [x] Deterministic branch triggered
- [x] Output is concise
- [x] Methodology available when toggle is on
- [ ] Cross-check totals manually against CSV / notebook output

---

### 2. Estimated Household Connections by 2030

**Test question**

```text
How many estimated household connections are achieved by 2030?
```

**Expected behavior**

- Returns total estimated household connections by 2030.
- Returns estimated household connections by milestone year.
- Returns estimated household connections by technology.
- Does not include unrelated national overview sections.

**Formula**

```text
Person-level new connections = (NewConnections2025 * ElecStatusIn2025) + NewConnections2030
Estimated household connections = Person-level new connections / NumPeoplePerHH
```

**Columns used**

- `NewConnections2025`
- `NewConnections2030`
- `ElecStatusIn2025`
- `NumPeoplePerHH`
- `FinalElecCode2030`

**Validated output**

```text
Total estimated household connections by 2030: 7,943,212 households
2025 step: 3,382,275 households
2030 step: 4,560,937 households
```

**Validation status**

- [x] Tested in app
- [x] Deterministic branch triggered
- [x] Milestone year split appears correctly
- [x] Technology breakdown appears correctly
- [ ] Cross-check totals manually against CSV / notebook output

---

### 3. Average Cost per Household Connection

**Test question**

```text
What is the average cost per household connection?
```

**Expected behavior**

- Returns national average cost per household connection.
- Returns technology-specific average cost per household connection.
- Uses deterministic Python metrics only.
- Does not fall back to LLM-generated numerical estimates.

**Formula**

```text
Average cost per household connection = Modelled investment / Estimated household connections
```

**Columns / derived fields used**

- `Total_Investment_USD`
- `Estimated_Connections_HH`
- `FinalElecCode2030`

**Validated output**

```text
National average cost per household connection: USD 652.34 per household connection
Grid Densification: USD 700.88 per household connection
Grid Extension: USD 949.06 per household connection
Mini-Grid Infrastructure: USD 1,489.12 per household connection
Standalone Solar Systems (SHS): USD 533.94 per household connection
```

**Validation status**

- [x] Tested in app
- [x] Deterministic branch triggered
- [x] Technology-specific averages appear
- [x] Output does not include broad national scenario dump
- [ ] Cross-check manually in notebook / spreadsheet

---

### 4. Population Summary

**Test question**

```text
What is the national population summary?
```

**Expected behavior**

- Returns base-year population.
- Returns 2030 population.
- Returns currently unelectrified population.
- Returns currently unelectrified population within 10 km of existing MV lines.

**Formula**

```text
Currently unelectrified population = PopStartYear - ElecPopCalib
Near-grid unelectrified population = currently unelectrified population where CurrentMVLineDist <= 10
```

**Columns used**

- `PopStartYear`
- `Pop2030`
- `ElecPopCalib`
- `CurrentMVLineDist`

**Validated output**

```text
Base-year population: 31,255,000 people
2030 population: 42,438,700 people
Currently unelectrified population: 21,188,039 people
Currently unelectrified population within 10 km of existing MV lines: 11,180,922 people
```

**Validation status**

- [x] Tested in app
- [x] Deterministic branch triggered
- [x] Uses partial-electrification adjustment
- [ ] Cross-check against official/project population references if available

---

### 5. Capacity by Technology

**Test question**

```text
What is the total capacity required by technology?
```

**Expected behavior**

- Returns total new capacity.
- Returns capacity by technology.
- Uses the same time-step logic as investment.

**Formula**

```text
(NewCapacity2025 * ElecStatusIn2025) + NewCapacity2030
```

**Columns used**

- `NewCapacity2025`
- `NewCapacity2030`
- `ElecStatusIn2025`
- `FinalElecCode2030`

**Validated output**

```text
Total new capacity: 1,417.70 MW
Grid Densification: 655.04 MW
Grid Extension: 270.70 MW
Mini-Grid Infrastructure: 31.13 MW
Standalone Solar Systems (SHS): 460.82 MW
```

**Validation status**

- [x] Tested in app
- [x] Deterministic branch triggered
- [ ] Cross-check manually against CSV / notebook output

---

### 6. Mini-Grid Settlement-Cluster Count

**Test question**

```text
How many mini-grids need to be built?
```

**Expected behavior**

- Returns mini-grid settlement-cluster count.
- Returns average capacity per mini-grid cluster.
- Returns average estimated households per mini-grid cluster.
- Includes caution that this is a settlement-cluster count, not necessarily final engineered project count.

**Formula**

```text
Count settlement clusters where FinalElecCode2030 is in [5, 6, 7]
```

**Columns / derived fields used**

- `FinalElecCode2030`
- `Total_New_Capacity_kW`
- `Estimated_Connections_HH`

**Validated output**

```text
Mini-grid settlement-cluster count: 2,521
Average capacity per mini-grid cluster: 12.35 kW
Average estimated households per mini-grid cluster: 34 households
```

**Validation status**

- [x] Tested in app
- [x] Deterministic branch triggered
- [x] Includes interpretation caution
- [ ] Confirm whether cluster count is the correct user-facing wording

---

### 7. Province-Level Summary

**Example test question**

```text
What is the summary for Nampula?
```

**Expected behavior**

- Detects a valid `Admin1` province.
- Filters scenario data to that province.
- Reuses deterministic summary calculations.
- Returns investment, connections, population, capacity, and mini-grid metrics for that province only.

**Columns used**

- `Admin1`
- plus all relevant national calculation columns

**Validation status**

- [x] Province detection implemented
- [x] Province-level deterministic summary implemented
- [ ] Test several provinces
- [ ] Confirm province spelling / accent handling
- [ ] Cross-check at least one province manually

---

### 8. Methodology Toggle

**Test**

- Toggle off: standard answers should hide methodology.
- Toggle on: standard answers should show methodology.
- Direct methodology questions should still return calculation methods.

**Validation status**

- [x] Toggle appears in sidebar
- [x] Toggle off hides methodology in normal answers
- [x] Toggle on shows methodology in normal answers
- [x] Direct methodology question still works

---

### 9. Response Mode Selector

**Test**

- Concise mode: result-focused answer.
- Technical mode: includes technical scope metadata.

**Expected technical scope fields**

- Question module
- Scenario file
- Calculation source
- Columns used

**Validation status**

- [x] Selector appears in sidebar
- [x] Concise mode works
- [x] Technical mode adds technical scope
- [ ] Apply technical scope consistently across all deterministic branches

---

### 10. Unsupported Query Guardrails

**Example test questions**

```text
Compare this scenario to the ambitious scenario.
```

```text
How many km of new grid lines are required?
```

```text
What should the government prioritize?
```

**Expected behavior**

- Multi-scenario comparison should say it is not yet enabled.
- Grid-line length should say it is not yet enabled.
- Policy-prescriptive questions should avoid recommending government actions.
- The app should state the enabled calculation scope.

**Validation status**

- [x] Multi-scenario guardrail implemented
- [x] Grid-line length guardrail implemented
- [x] Policy-prescriptive language reduced
- [ ] Add stronger explicit guardrail for direct policy recommendation questions
- [ ] Test more unsupported question phrasings

---

## Remaining Validation Priorities

Before sharing the July 1 asynchronous update:

1. Run each core shortcut once:
   - Investment
   - Connections
   - Population
   - Capacity
   - Mini-Grids

2. Test these typed questions:
   - `What is the average cost per household connection?`
   - `How are household connections calculated?`
   - `Compare this scenario to another scenario.`
   - `How many km of grid lines are required?`
   - `What should the government prioritize?`

3. Take screenshots or record a short Loom showing:
   - Concise response
   - Technical response
   - Methodology toggle
   - Guardrail response

4. Note any unresolved items:
   - Scenario selector not yet implemented
   - Document-based validation not yet implemented
   - Grid-line length not yet enabled
   - Multi-scenario comparison not yet enabled

---

## Summary for Async Update

Since the June 22 call, the prototype has been updated to make responses more concise, less prescriptive, and easier to validate. The main improvements are deterministic branches for investment, household connections, and average cost per household connection; milestone-year connection outputs; a methodology toggle; and a response mode selector. The next development priorities are stronger validation against official/project documents, broader question coverage, and a scenario-selection architecture.
