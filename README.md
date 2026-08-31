# ChatOnSSET: AI-Assisted Analytics for OnSSET Scenario Outputs

ChatOnSSET is a prototype application that helps users query GEP/OnSSET electrification planning scenario outputs in plain language.

The current version focuses on selected Mozambique scenario outputs. It uses deterministic Python calculations to answer supported analytical questions, while an LLM is used only to explain the results in clearer language.

Core principle:

**Python calculates. The AI explains.**

---

## Repository Note

This repository was originally based on the open-source OnSSET project structure. Some folders, notebooks, and files in this repository come from the downloaded OnSSET codebase and related modelling workflow.

My main contribution is the ChatOnSSET prototype layer added on top of this existing OnSSET project structure. This includes the Streamlit application, scenario selector, scenario metadata, question registry, deterministic calculation modules, output-formatting improvements, documentation for adding new questions, and handoff/scaling notes.

This repository should therefore be read as a modified OnSSET-based project workspace, not as a newly authored replacement for the original OnSSET tool.

Most other folders relate to the inherited OnSSET project structure and are retained for context and compatibility.

---

## What ChatOnSSET Does

Energy-planning scenario outputs can be difficult to interpret quickly because they often come in large CSV files with many rows, columns, and modelled outputs.

ChatOnSSET provides a simple interface where a user can select an active scenario and ask supported questions such as:

- What is the national investment required by technology by 2030?
- What is the additional annual demand to be supplied by mini-grids by 2030?
- What is the technology split for settlements with 100–1000 households?
- How many Solar Home Systems are to be deployed within 5 km of existing MV lines?

For each supported question, the app performs a deterministic calculation on the active scenario file and then returns a readable explanation of the result.

---

## What I Added

My main contribution in this repository is the ChatOnSSET prototype layer added on top of the existing OnSSET project structure.

Key additions include:

- `app.py`: Streamlit-based ChatOnSSET prototype for querying active GEP/OnSSET scenario files.
- Scenario selector for active Mozambique scenario outputs.
- Manual scenario metadata descriptions based on input-parameter differences.
- A deterministic question registry for supported analytical questions.
- Python calculation modules for investment, capacity, household connections, population summaries, province/Admin1 summaries, mini-grid demand, SHS proximity to MV lines, least-cost SHS settlement analysis, and technology split questions.
- Output formatting for large values, including USD millions/billions, MWh/GWh, MW/GW, and cleaner rounding.
- Documentation for adding new question modules.
- Scaling notes describing what would be required to expand beyond the current prototype.

Most other folders relate to the inherited OnSSET project structure and are retained for context and compatibility.

---

## Key ChatOnSSET Files

| File / Folder | Purpose |
|---|---|
| `app.py` | Main ChatOnSSET Streamlit application |
| `data/scenario_metadata.csv` | Scenario labels and descriptions used by the app |
| `data/README.md` | Instructions for setting up public scenario data locally |
| `docs/question_registry_guide.md` | Explains how supported questions are added |
| `docs/scaling_notes.md` | Notes on what would be required to scale the prototype |

---

## Supported Question Modules

The current prototype supports deterministic calculations for questions such as:

- National investment required by technology by 2030
- Capacity required by technology
- Household connections by technology
- Population and electrification summaries
- Province/Admin1 summaries
- SHS within 5 km of existing MV lines
- Settlements with more than 100 households where SHS is least-cost
- Technology split for settlements with 100–1000 households
- Additional annual demand supplied by mini-grids by 2030

Each supported question is implemented through a question-registry process. This means the required columns, calculation logic, routing, and response template are explicitly defined in the codebase.

---

## Question Registry Principle

ChatOnSSET does not rely on the LLM to calculate numerical outputs.

For each supported question:

1. The user-facing question is defined.
2. Required scenario columns are identified.
3. Any derived columns are created using Python.
4. A deterministic calculation function is written.
5. Routing logic maps the user question to the correct calculation.
6. The result is displayed through a response template.
7. The LLM explains the calculated result in plain language.

This structure reduces the risk of hallucinated numbers and makes the prototype easier to test, audit, and extend.

---

## Data Setup

Large scenario CSV files are not included in this repository.

To run ChatOnSSET locally, place the required public GEP/OnSSET scenario output files in the `data/` folder. The app uses `data/scenario_metadata.csv` to display scenario labels and descriptions.

Example expected structure:

```text
EnergyPlanningAIAgent/
├── app.py
├── data/
│   ├── scenario_metadata.csv
│   ├── mz-3-0_0_0_0_0_0.csv
│   ├── mz-3-0_0_0_0_1_1.csv
│   └── mz-3-0_0_1_1_0_1.csv
├── docs/
└── README.md


```

See: data/README.md for additional data setup notes.

## Running ChatOnSSET Locally

To run ChatOnSSET locally, you need:

1. Access to this GitHub repository.
2. A local Python environment.
3. The required GEP/OnSSET scenario output CSV files.
4. An OpenAI API key stored in Streamlit secrets.

### 1. Clone the repository

```bash
git clone https://github.com/kevint2007/EnergyPlanningAIAgent.git
cd EnergyPlanningAIAgent
```

### 2. Create or activate a Python environment

Using conda:

```bash
conda create -n chatonsset python=3.10
conda activate chatonsset
```

Install the main packages:

```bash
pip install streamlit pandas numpy openai pydantic
```

Depending on the environment, additional OnSSET-related dependencies may be needed if users plan to run the original OnSSET notebooks. For the ChatOnSSET Streamlit prototype, the main entry point is:

```text
app.py
```

### 3. Add scenario CSV files

Place the required public GEP/OnSSET scenario output files inside the `data/` folder.

The app uses:

```text
data/scenario_metadata.csv
```

to display human-readable scenario names and descriptions.

### 4. Add OpenAI API key to Streamlit secrets

Create this folder and file if they do not already exist:

```text
.streamlit/secrets.toml
```

Add:

```toml
OPENAI_API_KEY = "your-api-key-here"
```

Do not commit `.streamlit/secrets.toml` to GitHub.

### 5. Run the Streamlit app

```bash
streamlit run app.py
```

The app should open in a local browser window.

### 6. Select a scenario and ask a supported question

Once the app opens:

1. Select an active scenario from the sidebar.
2. Ask one of the supported analytical questions.

Example questions:

```text
What is the national investment required by technology by 2030?

What is the additional annual demand to be supplied by mini-grids by 2030?

What is the technology split for settlements with 100-1000 households?

How many Solar Home Systems are to be deployed within 5 km of existing MV lines?
```

---

## Current Limitations

- The prototype currently focuses on selected Mozambique GEP/OnSSET scenario outputs.
- Scenario descriptions are currently manually documented in `scenario_metadata.csv`.
- The app does not provide policy recommendations or implementation prescriptions.
- The LLM does not calculate numerical outputs; it explains values calculated by Python.
- New analytical questions require explicit implementation in the question registry.
- Local scenario CSV files are not included in this repository and must be set up separately.
- The prototype is not yet a deployed multi-country production system.

---

## Scaling Considerations

Scaling ChatOnSSET beyond the current prototype would require:

- Standardized scenario metadata across more scenarios and countries.
- Validation of required columns across country output files.
- Expanded testing across scenario files.
- Additional question modules.
- Improved deployment architecture.
- Possible cloud or server hosting.
- Clearer user-facing documentation.
- Defined governance for supported calculations and limitations.

See:

```text
docs/scaling_notes.md
```

for more detail.

---

## Attribution

Initial ChatOnSSET prototype developed by Kevin Theivendran, with feedback from members of SEforALL’s Integrated Energy Planning team.

This repository builds on the open-source OnSSET project structure.

---

## Original OnSSET Project Background

OnSSET is the Open Source Spatial Electrification Tool. The original OnSSET workflow uses Python and Jupyter notebooks for geospatial electrification modelling.

The original workflow includes:

1. Creating settlement-level input files with GIS data.
2. Running calibration notebooks to calibrate start-year information.
3. Running scenario notebooks for electrification analysis.

This repository retains parts of the original OnSSET project structure because ChatOnSSET was developed as a prototype layer around OnSSET/GEP scenario outputs.

For the original OnSSET installation workflow, users should refer to the official OnSSET documentation and community resources.

---

## Original OnSSET Installation Context

The original OnSSET repository can be run using interactive Jupyter notebooks. In the original workflow, users first create the input file with GIS data extracted for each settlement, then run calibration and scenario notebooks.

The Original OnSSET notebooks include:

- `OnSSET_Calibration.ipynb`
- `OnSSET_Scenarios.ipynb`
- `OnSSET_Scenarios_MultipleTimeSteps.ipynb`

These files are retained in this repository as part of the inherited OnSSET project structure.

The main ChatOnSSET prototype entry point is:

```text
app.py
```
