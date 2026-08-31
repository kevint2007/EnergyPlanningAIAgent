\# ChatOnSSET Scaling Notes



\## Purpose



This document outlines what would be required to scale ChatOnSSET beyond the current Mozambique-focused prototype.



The current prototype is designed as a local Streamlit application for exploring selected GEP/OnSSET scenario outputs. It is not yet a deployed multi-country production system.



The core design principle is:



\*\*Python calculates. The AI explains.\*\*



Numerical outputs are calculated through deterministic Python functions. The LLM is used only to explain calculated results in clearer language.



---



\## Current Prototype Scope



The current prototype supports selected Mozambique GEP/OnSSET scenario outputs.



It currently includes:



\- a Streamlit chat interface,

\- an active scenario selector,

\- manually documented scenario labels and notes,

\- deterministic calculation modules,

\- a question registry for supported analytical questions,

\- output formatting for large values,

\- optional methodology/technical traceability notes.



The current app focuses on helping users ask supported questions about investment, capacity, household connections, population summaries, province/Admin1 summaries, mini-grid demand, SHS proximity to MV lines, and technology split outputs.



---



\## Scaling to More Scenarios



Scaling to more scenarios within the same country would require:



\- adding additional scenario CSV files to the `data/` folder,

\- ensuring each file follows the expected GEP/OnSSET output structure,

\- expanding `data/scenario\_metadata.csv` with clear scenario labels and notes,

\- confirming that scenario codes follow a consistent naming convention,

\- testing every supported question module across every active scenario,

\- confirming that required columns exist consistently across all scenario files.



The current scenario descriptions are manually documented. For a larger scenario set, it may be useful to add a scenario-comparison feature that reads input-parameter files and identifies which assumptions changed between scenarios.



However, automatically generated scenario labels should still be reviewed carefully. The app should not rely on the LLM to invent scenario descriptions.



---



\## Scaling to More Countries



Scaling to more countries would require:



\- validating country-specific GEP/OnSSET output file structures,

\- confirming that required columns are available across country datasets,

\- updating the scenario-discovery logic to support country selection,

\- adding country-level metadata,

\- testing province/Admin1 naming conventions,

\- validating whether technology-code mappings remain consistent across countries,

\- checking whether the same question modules make sense for each country context.



Country expansion should happen after the Mozambique prototype is stable and tested.



---



\## Adding New Questions



New analytical questions should be added through the question-registry process.



The recommended process is:



1\. Define the user-facing question.

2\. Identify required raw columns.

3\. Add missing raw columns to `REQUIRED\_COLUMNS`.

4\. Create derived columns if needed.

5\. Add a registry entry in `QUESTION\_REGISTRY`.

6\. Write a deterministic Python calculation function.

7\. Add routing logic so the app recognizes the question.

8\. Add a response template.

9\. Test across active scenarios.

10\. Document assumptions, units, and caveats.



This keeps the tool controlled and auditable. New questions should not be answered by allowing the LLM to calculate directly from the CSV.



---



\## Deployment and Hosting Options



The current prototype runs locally through Streamlit.



Possible future deployment paths include:



\- local internal use,

\- private Streamlit deployment,

\- cloud-hosted prototype,

\- server-hosted internal tool,

\- integration into a larger GEP/OnSSET workflow.



A hosted version would require decisions on:



\- authentication,

\- data access,

\- API key management,

\- data storage,

\- cost controls,

\- maintenance responsibility,

\- user permissions,

\- whether the tool is internal-only or externally accessible.



If deployed in the cloud, the app should avoid exposing API keys, private scenario files, or unsupported outputs.



---



\## Risks and Limitations



Current limitations include:



\- the prototype is not yet a deployed production system,

\- scenario descriptions are currently manually documented,

\- new questions require explicit implementation,

\- unsupported questions are not answered through deterministic logic,

\- large scenario files are not included in the repository,

\- the app does not provide policy recommendations or implementation prescriptions,

\- technology outputs are modelled scenario results, not final implementation decisions,

\- settlement-cluster counts should not automatically be interpreted as final engineered project counts.



---



\## Summary



ChatOnSSET can potentially scale beyond the current Mozambique prototype, but scaling would require more than adding files to the `data/` folder. It would require standardized metadata, consistent scenario outputs, expanded testing, controlled question expansion, and clearer deployment decisions.



The most important design principle should remain:



\*\*Python calculates. The AI explains.\*\*

