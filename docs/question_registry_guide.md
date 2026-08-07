\# ChatOnSSET Question Registry Guide



\## Purpose



ChatOnSSET uses a fixed deterministic question registry to define which analytical questions are supported by the prototype.



The core principle is:



\*\*Python calculates. The LLM explains.\*\*



The app should not rely on the LLM to calculate numerical outputs. Every supported quantitative question should be answered using deterministic Python logic applied to the active GEP/OnSSET scenario file.



---



\## Current Question Registry Structure



The main registry lives in `app.py` as:



```python

QUESTION\_REGISTRY = {

&nbsp;   ...

}

```



Each registry entry documents:



\- `status`: whether the question is implemented, planned, or needs clarification

\- `scope`: whether the question is national, province/Admin1, or scenario-level

\- `columns\_used`: the columns required for the calculation

\- `formula`: the deterministic formula, filter, or grouping logic

\- `notes`: interpretation caveats or implementation details



The registry is used for transparency and methodology display. It helps future developers understand which questions are supported and how each answer is calculated.



---



\## Core Implementation Pattern



Each supported question usually requires five components:



1\. Required columns in `REQUIRED\_COLUMNS`

2\. A registry entry in `QUESTION\_REGISTRY`

3\. A deterministic Python calculation function

4\. Keyword-routing logic in the chat loop

5\. A response template with methodology and technical scope notes



---



\## Step 1: Define the User Question



Start with a clear analytical question.



Example:



```text

How many Solar Home Systems are to be deployed within 5 km of existing MV lines?

```



The question should be specific enough to translate into column filters, groupings, or aggregations.



---



\## Step 2: Identify Required Columns



Before coding a new question, identify the required raw columns in the scenario CSV.



Example:



```text

FinalElecCode2030

CurrentMVLineDist

NewConnections2030

NumPeoplePerHH

```



Because the app loads scenario CSVs using:



```python

pd.read\_csv(file\_path, usecols=REQUIRED\_COLUMNS)

```



any raw column needed for a new question must be added to `REQUIRED\_COLUMNS`.



If a column is not listed in `REQUIRED\_COLUMNS`, it will not be loaded into the app.



---



\## Step 3: Add Derived Columns if Needed



Some questions require derived columns created during preprocessing.



Current examples:



```text

Estimated\_Connections\_HH

Estimated\_Connections\_HH\_2025

Estimated\_Connections\_HH\_2030

Estimated\_Households\_2030

Net\_Additional\_EnergyPerSettlement\_2025\_2030

Positive\_Additional\_EnergyPerSettlement\_2025\_2030

```



Derived columns should be created inside `load\_scenario\_and\_process()` so every question module uses a consistent processed dataframe.



---



\## Step 4: Add a Registry Entry



Each new question should have a clear registry entry.



Example:



```python

"shs\_within\_5km\_mv": {

&nbsp;   "status": "implemented",

&nbsp;   "scope": "national",

&nbsp;   "columns\_used": \[

&nbsp;       "FinalElecCode2030",

&nbsp;       "CurrentMVLineDist",

&nbsp;       "Estimated\_Connections\_HH"

&nbsp;   ],

&nbsp;   "formula": "Filter settlement clusters where FinalElecCode2030 == 3 and CurrentMVLineDist <= 5.",

&nbsp;   "notes": "Reports settlement-cluster count and estimated SHS household connections within 5 km of existing MV lines."

}

```



The registry entry should be understandable to someone who did not write the original code.



---



\## Step 5: Write the Deterministic Calculation Function



Each question should have a calculation function that takes `processed\_df` as input and returns a structured dictionary.



Example pattern:



```python

def calculate\_example\_question(processed\_df):

&nbsp;   filtered\_df = processed\_df\[

&nbsp;       condition\_here

&nbsp;   ].copy()



&nbsp;   return {

&nbsp;       "metric\_name": value

&nbsp;   }

```



The function should not return prose. It should return structured values that the response template can display.



---



\## Step 6: Add Routing Logic



The app needs to detect when the user is asking the supported question.



Example:



```python

is\_shs\_within\_mv\_query = (

&nbsp;   ("solar home" in query\_lower or "shs" in query\_lower or "standalone solar" in query\_lower)

&nbsp;   and ("5 km" in query\_lower or "5km" in query\_lower or "within 5" in query\_lower)

&nbsp;   and ("mv" in query\_lower or "medium voltage" in query\_lower)

)

```



Routing should be strict enough to avoid accidental matches, but flexible enough to support natural wording.



---



\## Step 7: Add a Response Template



The response template should include:



\- direct result

\- short analytical label

\- methodology section

\- technical scope note if Technical mode is selected



Example structure:



```markdown

\### Question Result Title



\#### National Result

\* Metric 1

\* Metric 2

\* Metric 3



\#### Methodology

Explain the deterministic filter or formula used.

```



The response should avoid unsupported policy recommendations or implementation prescriptions.



---



\# Current Implemented Andreas Questions



\## 1. SHS Within 5 km of Existing MV Lines



Question:



```text

How many Solar Home Systems are to be deployed within 5 km of existing MV lines?

```



Module:



```text

shs\_within\_5km\_mv

```



Columns used:



```text

FinalElecCode2030

CurrentMVLineDist

Estimated\_Connections\_HH

Estimated\_Connections\_HH\_2030

```



Logic:



```text

FinalElecCode2030 == 3

CurrentMVLineDist <= 5

```



Outputs:



```text

SHS settlement-cluster count

estimated SHS household connections

estimated 2030-step SHS household connections

average distance to existing MV line

```



Notes:



This question uses `FinalElecCode2030` because it asks how many SHS are to be deployed in the final 2030 scenario assignment.



---



\## 2. Large Settlements Where SHS Is Least-Cost



Question:



```text

How many settlements with more than 100 households have SHS as the least-cost technology?

```



Module:



```text

large\_settlements\_shs\_least\_cost

```



Columns used:



```text

MinimumOverallCode2030

Pop2030

NumPeoplePerHH

Estimated\_Households\_2030

```



Logic:



```text

MinimumOverallCode2030 == 3

Estimated\_Households\_2030 > 100

```



Outputs:



```text

settlement-cluster count

estimated 2030 households represented

average estimated households per cluster

```



Notes:



This question uses `MinimumOverallCode2030`, not `FinalElecCode2030`, because the question asks for the least-cost technology.



---



\## 3. Technology Split for Settlements With 100–1000 Households



Question:



```text

What is the technology split for settlements with 100-1000 households?

```



Module:



```text

technology\_split\_settlement\_size

```



Columns used:



```text

FinalElecCode2030

Pop2030

NumPeoplePerHH

Estimated\_Households\_2030

```



Logic:



```text

100 <= Estimated\_Households\_2030 <= 1000

Group by user-facing FinalElecCode2030 technology category

```



Outputs:



```text

settlement-cluster count in the fixed cohort

estimated 2030 households in the cohort

technology split by cluster count

technology split by household count

percentage shares

```



Notes:



Mini-grid subcodes 5, 6, and 7 should be collapsed into one user-facing category:



```text

Mini-Grid Infrastructure

```



The cohort is defined by estimated 2030 household count, so the number of settlements in the cohort may remain constant across scenarios while the technology split changes.



---



\## 4. Additional Annual Demand Supplied by Mini-Grids by 2030



Question:



```text

What is the additional annual demand to be supplied by mini-grids by 2030?

```



Module:



```text

mini\_grid\_annual\_demand

```



Columns used:



```text

FinalElecCode2030

EnergyPerSettlement2025

EnergyPerSettlement2030

```



Logic:



```text

FinalElecCode2030 in \[5, 6, 7]

```



Calculations:



```text

Total annual demand in 2025 = sum(EnergyPerSettlement2025)

Total annual demand in 2030 = sum(EnergyPerSettlement2030)

Net additional annual demand = sum(EnergyPerSettlement2030) - sum(EnergyPerSettlement2025)

Positive incremental annual demand = sum of positive row-level increases only

```



Unit:



```text

kWh/year

```



Outputs:



```text

mini-grid settlement-cluster count

total annual demand in 2025

total annual demand in 2030

net additional annual demand from 2025 to 2030

positive incremental annual demand before offsetting local decreases

```



Notes:



The net additional annual demand is the main answer. The positive incremental value is a technical diagnostic because some settlement rows can decrease between periods.



---



\# Technology Code Mapping



The current user-facing technology mapping is:



```text

1 = Grid Densification

2 = Grid Extension

3 = Standalone Solar Systems (SHS)

5 = Mini-Grid Infrastructure

6 = Mini-Grid Infrastructure

7 = Mini-Grid Infrastructure

```



Mini-grid subcodes are collapsed for user-facing summaries unless a future question specifically asks for mini-grid subtype detail.



---



\# Final Technology vs Least-Cost Technology



Use `FinalElecCode2030` when the question asks about the final assigned technology in the active scenario.



Use `MinimumOverallCode2030` when the question explicitly asks about the least-cost technology.



Examples:



```text

"How many SHS are to be deployed?"

Use FinalElecCode2030.



"How many settlements have SHS as the least-cost technology?"

Use MinimumOverallCode2030.

```



---



\# Guardrail Rules



If a question requires a column that is missing, unclear, or not validated, the app should not guess.



Return a clear response such as:



```text

This question is not yet enabled because the required column or unit needs confirmation.

```



The app should avoid:



\- unsupported policy recommendations

\- technology-prioritization advice

\- implementation prescriptions

\- invented calculations

\- LLM-generated numbers



---



\# Testing Checklist for New Questions



Every new question should be tested across all active scenarios:



```text

Baseline / Unconstrained Grid Scenario

Grid-Constrained Scenario

Carbon Price + Low PV Cost Scenario

```



For each question, record:



```text

question wording

expected module

required columns

scenario tested

observed result

status

notes or caveats

```



A question should not be considered implemented until it works across all active scenario files.



---



\# Common Mistakes to Avoid



1\. Forgetting to add new raw columns to `REQUIRED\_COLUMNS`

2\. Letting the LLM calculate values instead of Python

3\. Using `FinalElecCode2030` when the question asks for least-cost technology

4\. Failing to collapse mini-grid subcodes 5, 6, and 7 in user-facing summaries

5\. Reporting units before confirming them from documentation

6\. Treating settlement-cluster counts as final engineered project counts

7\. Adding broad keyword routing that accidentally captures unrelated questions



---



\# Summary



To add a new ChatOnSSET question:



1\. Define the analytical question.

2\. Identify required columns.

3\. Add missing raw columns to `REQUIRED\_COLUMNS`.

4\. Create any required derived columns in `load\_scenario\_and\_process()`.

5\. Add a registry entry.

6\. Write a deterministic calculation function.

7\. Add routing logic.

8\. Add a response template.

9\. Test across all active scenarios.

10\. Document any assumptions, units, and caveats.

