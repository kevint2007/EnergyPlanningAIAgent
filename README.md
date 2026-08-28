# ChatOnSSET: AI-Assisted Analytics for OnSSET Scenario Outputs

ChatOnSSET is a prototype application that helps users query GEP/OnSSET electrification planning scenario outputs in plain language.

The current version focuses on selected Mozambique scenario outputs. It uses deterministic Python calculations to answer supported analytical questions, while an LLM is used only to explain the results in clearer language.

Core principle:

**Python calculates. The AI explains.**

---

## Repository Note

This repository was originally based on the open-source OnSSET project structure. Some folders, notebooks, and files in this repository come from the downloaded OnSSET codebase and related modelling workflow.

My contribution is the ChatOnSSET prototype layer, including the Streamlit application, scenario selector, question registry, deterministic calculation modules, output-formatting improvements, testing documentation, and handoff/scaling notes.

This repository should therefore be read as a modified OnSSET-based project workspace, not as a newly authored replacement for the original OnSSET tool.

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

My main contributions in this repository include:

- `app.py`: Streamlit-based ChatOnSSET prototype for querying active GEP/OnSSET scenario files.
- Scenario selector for active Mozambique scenario outputs.
- Manual scenario metadata descriptions based on input-parameter differences.
- A deterministic question registry for supported analytical questions.
- Python calculation modules for investment, capacity, household connections, population summaries, mini-grid demand, SHS proximity to MV lines, least-cost SHS settlement analysis, and technology split questions.
- Output formatting for large values, including USD millions/billions, MWh/GWh, MW/GW, and cleaner rounding.
- Documentation for adding new question modules.
- Testing notes for supported questions across active scenarios.
- Scaling notes describing what would be required to expand beyond the current prototype.

---

## Key ChatOnSSET Files

| File / Folder | Purpose |
|---|---|
| `app.py` | Main ChatOnSSET Streamlit application |
| `data/scenario_metadata.csv` | Scenario labels and descriptions used by the app |
| `data/README.md` | Instructions for setting up public scenario data locally |
| `docs/question_registry_guide.md` | Explains how supported questions are added |
| `docs/test_questions.md` | Records tested question modules and expected behavior |
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

Running ChatOnSSET Locally

To run ChatOnSSET locally, you need:

Access to this GitHub repository.
A local Python environment.
The required GEP/OnSSET scenario output CSV files.
An OpenAI API key stored in Streamlit secrets.
1. Clone the repository
git clone https://github.com/kevint2007/EnergyPlanningAIAgent.git
cd EnergyPlanningAIAgent
2. Create or activate a Python environment

Using conda:

conda create -n chatonsset python=3.10
conda activate chatonsset

Install the main packages:

pip install streamlit pandas numpy openai pydantic

Depending on the environment, additional OnSSET-related dependencies may be needed if users plan to run the original OnSSET notebooks. For the ChatOnSSET Streamlit prototype, the main entry point is:

app.py
3. Add scenario CSV files

Place the required public GEP/OnSSET scenario output files inside the data/ folder.

The app uses:

data/scenario_metadata.csv

to display human-readable scenario names and descriptions.

4. Add OpenAI API key to Streamlit secrets

Create this folder and file if they do not already exist:

.streamlit/secrets.toml

Add:

OPENAI_API_KEY = "your-api-key-here"

Do not commit .streamlit/secrets.toml to GitHub.

5. Run the Streamlit app
streamlit run app.py

The app should open in a local browser window.

6. Select a scenario and ask a supported question

Once the app opens:

Select an active scenario from the sidebar.
Ask one of the supported analytical questions.

Example questions:

What is the national investment required by technology by 2030?

What is the additional annual demand to be supplied by mini-grids by 2030?

What is the technology split for settlements with 100-1000 households?

How many Solar Home Systems are to be deployed within 5 km of existing MV lines?
Current Limitations
The prototype currently focuses on selected Mozambique GEP/OnSSET scenario outputs.
Scenario descriptions are currently manually documented in scenario_metadata.csv.
The app does not provide policy recommendations or implementation prescriptions.
The LLM does not calculate numerical outputs; it explains values calculated by Python.
New analytical questions require explicit implementation in the question registry.
Local scenario CSV files are not included in this repository and must be set up separately.
The prototype is not yet a deployed multi-country production system.
