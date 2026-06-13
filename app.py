import streamlit as st
import pandas as pd
import numpy as np
import openai
import json
from pydantic import BaseModel, Field
from typing import List

# --- 1. CONFIG & DATA PREPROCESSING ---
st.set_page_config(page_title="ChatOnSSET: National Planning Engine", layout="wide", page_icon="🛰️")

# Upgraded Option B: Pure narrative schema. Python strictly controls all numbers.
class OnSSETNarrative(BaseModel):
    executive_summary: str = Field(description="An authoritative, 2-sentence investment and electrification summary tailored for ministry planners. Synthesize only using the verified numbers provided in the context object. Plain text only. Do not use dollar signs, backticks, asterisks, or symbols.")
    strategic_policy_recommendation: str = Field(description="A brief, 1-sentence macro policy recommendation focusing on technology deployment scaling based on the active electrification scenario. Plain text only.")

# Required columns for the current deterministic V3 baseline.
# These are validated before any calculations are executed so demo failures are explicit.
REQUIRED_COLUMNS = [
    "FinalElecCode2030",
    "InvestmentCost2025",
    "InvestmentCost2030",
    "ElecStatusIn2025",
    "NewConnections2025",
    "NewConnections2030",
    "NumPeoplePerHH"
]

# Canonical question registry based on the initial OnSSET questions shared by the IEP team.
# This makes clear what is implemented now versus planned for the next sprint.
QUESTION_REGISTRY = {
    "investment_by_technology": {
        "status": "implemented",
        "scope": "national",
        "columns_used": [
            "FinalElecCode2030",
            "InvestmentCost2025",
            "InvestmentCost2030",
            "ElecStatusIn2025"
        ],
        "formula": "(InvestmentCost2025 * ElecStatusIn2025) + InvestmentCost2030",
        "notes": "Technology codes are split into grid densification, grid extension, SHS, and mini-grid."
    },
    "estimated_household_connections": {
        "status": "implemented",
        "scope": "national",
        "columns_used": [
            "NewConnections2025",
            "NewConnections2030",
            "ElecStatusIn2025",
            "NumPeoplePerHH"
        ],
        "formula": "((NewConnections2025 * ElecStatusIn2025) + NewConnections2030) / NumPeoplePerHH",
        "notes": "Household values are estimated from person-level connection columns."
    },
    "estimated_household_connections_by_technology": {
        "status": "implemented",
        "scope": "national",
        "columns_used": [
            "FinalElecCode2030",
            "NewConnections2025",
            "NewConnections2030",
            "ElecStatusIn2025",
            "NumPeoplePerHH"
        ],
        "formula": "Group estimated household connections by FinalElecCode2030 technology category.",
        "notes": "Uses the same household-estimation method as the national connection total."
    },
    "population_summary": {
        "status": "next",
        "scope": "national",
        "columns_needed": ["PopStartYear or equivalent", "Pop2030", "electrification status column"],
        "notes": "Column names need confirmation before implementation."
    },
    "capacity_by_technology": {
        "status": "next",
        "scope": "national",
        "columns_needed": ["FinalElecCode2030", "Tot_Cap"],
        "notes": "Need to validate whether Tot_Cap is the correct final capacity field."
    },
    "province_summary": {
        "status": "planned",
        "scope": "Admin1",
        "columns_needed": ["Admin1"],
        "notes": "Province-level filtering should be validated after national calculations."
    }
}

@st.cache_data
def load_scenario_and_process(file_path):
    # Load raw settlement-level dataset
    raw_df = pd.read_csv(file_path)

    missing_columns = [col for col in REQUIRED_COLUMNS if col not in raw_df.columns]
    if missing_columns:
        raise ValueError(
            "The active scenario file is missing required columns: "
            + ", ".join(missing_columns)
        )

    processed_df = raw_df.copy()
    
    # Safely handle missing values by filling them with 0
    for col in REQUIRED_COLUMNS:
        processed_df[col] = processed_df[col].fillna(0)

    # Vectorized connections logic (Andreas step-wise correction)
    processed_df['True_Connections_Individuals'] = (processed_df['NewConnections2025'] * processed_df['ElecStatusIn2025']) + processed_df['NewConnections2030']
    
    # Avoid division by zero using highly-optimized NumPy logic (Maintain float precision at row-level)
    safe_hh_denom = np.where(processed_df['NumPeoplePerHH'] == 0, np.inf, processed_df['NumPeoplePerHH'])
    processed_df['Estimated_Connections_HH'] = (processed_df['True_Connections_Individuals'] / safe_hh_denom).fillna(0)
    
    # Apply ElecStatusIn2025 filter to investment to resolve time-step overcounting risk
    processed_df['Total_Investment_USD'] = (processed_df['InvestmentCost2025'] * processed_df['ElecStatusIn2025']) + processed_df['InvestmentCost2030']
    
    return processed_df.copy()

# --- 2. DETERMINISTIC CALCULATION FUNCTIONS (V3 CORE) ---
def calculate_national_summary(processed_df):
    """
    Executes fully deterministic calculations across the processed dataframe 
    to extract tech-disaggregated investment values and household estimates.
    """
    densification_codes = [1]
    extension_codes = [2]
    sa_codes = [3]      
    mg_codes = [5, 6, 7] 

    # Calculate individual technology vectors
    densification_val = float(processed_df[processed_df['FinalElecCode2030'].isin(densification_codes)]['Total_Investment_USD'].sum())
    extension_val = float(processed_df[processed_df['FinalElecCode2030'].isin(extension_codes)]['Total_Investment_USD'].sum())
    solar_val = float(processed_df[processed_df['FinalElecCode2030'].isin(sa_codes)]['Total_Investment_USD'].sum())
    mini_val = float(processed_df[processed_df['FinalElecCode2030'].isin(mg_codes)]['Total_Investment_USD'].sum())

    # Round ONLY after global summation to prevent truncation compounding issues
    total_connections_hh_calc = int(round(processed_df['Estimated_Connections_HH'].sum()))

    # Calculate estimated household connections by technology using the same groupings
    densification_hh = float(processed_df[processed_df['FinalElecCode2030'].isin(densification_codes)]['Estimated_Connections_HH'].sum())
    extension_hh = float(processed_df[processed_df['FinalElecCode2030'].isin(extension_codes)]['Estimated_Connections_HH'].sum())
    solar_hh = float(processed_df[processed_df['FinalElecCode2030'].isin(sa_codes)]['Estimated_Connections_HH'].sum())
    mini_hh = float(processed_df[processed_df['FinalElecCode2030'].isin(mg_codes)]['Estimated_Connections_HH'].sum())

    # Determine Dominant Technology dynamically
    tech_investments = {
        "Grid Densification": densification_val,
        "Grid Extension": extension_val,
        "Standalone Solar Systems": solar_val,
        "Mini-Grid Infrastructure": mini_val
    }
    dominant_tech = max(tech_investments, key=tech_investments.get)

    return {
        "grid_densification_investment_usd": densification_val,
        "grid_extension_investment_usd": extension_val,
        "mini_grid_investment_usd": mini_val,
        "standalone_solar_investment_usd": solar_val,
        "estimated_household_connections": total_connections_hh_calc,
        "estimated_household_connections_by_technology": {
            "grid_densification": int(round(densification_hh)),
            "grid_extension": int(round(extension_hh)),
            "standalone_solar": int(round(solar_hh)),
            "mini_grid": int(round(mini_hh))
        },
        "dominant_technology_by_capex": dominant_tech
    }

def convert_df(df_to_download):
    return df_to_download.to_csv(index=False).encode('utf-8')

# Global Initialization and Cache Execution
active_scenario_code = "mz-3-0_0_0_0_0_0"
try:
    df = load_scenario_and_process(f'data/{active_scenario_code}.csv')
    metrics = calculate_national_summary(df)
except FileNotFoundError:
    st.error(f"Please ensure {active_scenario_code}.csv is placed in your 'data/' folder.")
    st.stop()
except ValueError as exc:
    st.error(str(exc))
    st.stop()


# --- 3. SYSTEM INSTRUCTIONS ---
system_instruction = """
You are ChatOnSSET, the Senior National Energy Access Advisor for the Government of Mozambique.
You provide decisive, country-wide investment strategies based on verified summaries of settlement-level GEP/OnSSET electrification planning scenario outputs.

DATA DICTIONARY MAPPING:
- `id`: Unique Identifier per settlement cluster.
- `Admin1`: Admin level 1 name (Province or Region).
- `Pop2030`: Projected population of the settlement at the end year of the analysis (2030).
- `FinalElecCode2030`: Final selected electrification technology. 
    * Code 1 = Grid-Densification
    * Code 2 = Grid-Extension
    * Code 3 = Standalone Solar PV (SHS)
    * Code 5, 6, or 7 = Mini-Grid

STRICT TECHNICAL RULES:
1. Format all large currency totals using plain text words or commas (e.g., 1,500,000 USD).
2. If a query is outside the enabled deterministic calculation scope, state that the query is not yet enabled and suggest the closest supported output.
3. Start directly with the strategic analysis. No small talk or greetings.
4. STYLING RULE: Write in clean, normal prose sentences. Do not include markdown bold markers (**), backticks (`), or dollar sign ($) characters inside your text fields. 
5. CRITICAL MATRICES RULE: Look at the actual numbers in the data matrix. Do not write out numbers as long text words. Use normal digits and short text descriptors.
6. SUB-NATIONAL GUARDRAIL: Province-level outputs are not yet enabled in this version. Do not calculate province-level totals unless the Python layer provides a validated province-specific result object.
"""


# --- 4. SIDEBAR ---
with st.sidebar:
    st.title("🛰️ ChatOnSSET")
    st.subheader("National Decision Support")
    
    if st.button("🗑️ Clear Chat History"):
        st.session_state.messages = []
        st.rerun()
        
    st.divider()
    st.info(f"Status: Operational\nTest Scenario: {active_scenario_code}\nData Mode: Deterministic Object Vector")
    st.caption("Developed for National IEP Framework Scaling")


# --- 5. INITIALIZE OPENAI CLIENT ---
client = openai.OpenAI(api_key=st.secrets["OPENAI_API_KEY"])


# --- 6. CHAT INTERFACE & FIXED LAYOUT ---
if "messages" not in st.session_state:
    st.session_state.messages = []

st.markdown("### 👋 Welcome to ChatOnSSET National")
st.markdown(
    "I am your specialized **Decision Support Interface** scaled for the Mozambique National Electrification Strategy."
)

# Render Metric Cards securely from the pure Python metrics output
st.subheader("🛰️ National Scenario Matrix KPI Overview")
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.metric(label="Grid Densification CAPEX", value=f"M${metrics['grid_densification_investment_usd'] / 1_000_000:.1f}")
with c2:
    st.metric(label="Grid Extension CAPEX", value=f"M${metrics['grid_extension_investment_usd'] / 1_000_000:.1f}")
with c3:
    st.metric(label="Mini-Grid CAPEX", value=f"M${metrics['mini_grid_investment_usd'] / 1_000_000:.1f}")
with c4:
    st.metric(label="Standalone Solar CAPEX", value=f"M${metrics['standalone_solar_investment_usd'] / 1_000_000:.1f}")

# Fix 3: Methodological Traceability Notes Expander Component
with st.expander("📊 Calculation Methodology & Traceability Notes"):
    st.markdown("""
    * **Investment Formula:** `(InvestmentCost2025 * ElecStatusIn2025) + InvestmentCost2030` *(Note: Applied time-step validation filter to mitigate 2025 overcounting risk).*
    * **Connection Formula:** `(NewConnections2025 * ElecStatusIn2025) + NewConnections2030`
    * **Household Connections Caveat:** Household metrics are estimates derived by dividing person-level new connections by `NumPeoplePerHH` at row precision before global summation. These calculations are subject to validation against the official GEP/OnSSET household-connection reference outputs.
    """)
    st.markdown("#### Current Question Registry")
    st.json(QUESTION_REGISTRY)
st.divider()

# Fix 5: Clearer, realistic greeting context phrasing
st.markdown("💡 **Click one of these shortcuts to query the active national scenario output:**")
col1, col2, col3 = st.columns(3)
user_query = None

with col1:
    if st.button("📊 National Technology Mix", use_container_width=True, key="btn_tech_mix"):
        user_query = (
            "Provide a complete national comparative analysis of the required investment splits and targets "
            "across Grid Densification, Grid Extension, Mini-Grids, and Standalone Solar pathways under the current active scenario profile."
        )
with col2:
    if st.button("⚡ Investment per Technology", use_container_width=True, key="btn_inv_tech"):
        user_query = (
            "What is the total capital expenditure required for each electrification technology by 2030, "
            "and what is the strategic policy recommendation for deployment?"
        )
with col3:
    # Fix 4: Renamed from Capacity shortcut to reflect accurate deterministic metrics
    if st.button("📋 Connections Summary", use_container_width=True, key="btn_conn_cap"):
        user_query = (
            "Summarize the total number of new consumer household connections achieved by the model runs "
            "and evaluate the technology-disaggregated investment trends."
        )
st.divider()

# Render persistent conversation stream
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if chat_prompt := st.chat_input("Analyze Mozambique national impact..."):
    user_query = chat_prompt


# --- 7. AGENT EXECUTION LOOP ---
if user_query:
    st.session_state.messages.append({"role": "user", "content": user_query})
    with st.chat_message("user"):
        st.write(user_query)

    with st.chat_message("assistant"):
        cleaned_query_words = user_query.lower().strip().split()
        greetings_set = {"hi", "hello", "hey", "greetings", "howdy"}
        
        query_lower = user_query.lower()
        is_small_talk = any(word in greetings_set for word in cleaned_query_words) or query_lower in ["how can you help", "what do you do", "test"]

        methodology_keywords = [
            "formula",
            "methodology",
            "method",
            "calculate",
            "calculation",
            "how are you calculating",
            "how do you calculate",
            "connection formula",
            "household formula"
        ]

        mozambique_provinces = [
            "nampula",
            "niassa",
            "zambezia",
            "zambézia",
            "tete",
            "manica",
            "sofala",
            "inhambane",
            "gaza",
            "maputo",
            "cabo delgado"
        ]

        capacity_keywords = [
            "capacity",
            "kw",
            "kilowatt",
            "renewable capacity",
            "generation capacity"
        ]

        multi_scenario_keywords = [
            "compare scenarios",
            "scenario comparison",
            "ambitious scenario",
            "maximized scenario",
            "maximise scenario",
            "maximize scenario",
            "other scenario",
            "between scenarios"
        ]

        mini_grid_count_keywords = [
            "how many mini-grids",
            "number of mini-grids",
            "mini-grid count",
            "minigrid count",
            "mini grids need to be built",
            "mini-grids need to be built"
        ]

        grid_line_keywords = [
            "grid lines",
            "grid line",
            "new grid lines",
            "kilometers",
            "kilometres",
            "km of"
        ]

        is_methodology_query = any(keyword in query_lower for keyword in methodology_keywords)
        is_province_query = any(province in query_lower for province in mozambique_provinces) or "province" in query_lower or "admin1" in query_lower
        is_capacity_query = any(keyword in query_lower for keyword in capacity_keywords)
        is_multi_scenario_query = any(keyword in query_lower for keyword in multi_scenario_keywords)
        is_mini_grid_count_query = any(keyword in query_lower for keyword in mini_grid_count_keywords)
        is_grid_line_query = any(keyword in query_lower for keyword in grid_line_keywords)
        
        if is_small_talk:
            # Fix 5: Removed multi-scenario phrasing to align perfectly with the active dataset scope
            greeting_response = """I am ChatOnSSET, your Senior National Energy Access Advisor for Mozambique. 

I can help you evaluate investment metrics and connection targets for the active electrification scenario across four primary pathways:
* **Grid Densification**
* **Grid Extension**
* **Mini-Grid Infrastructure**
* **Standalone Solar Systems**

Please click one of the shortcuts above or enter an analytical question below to query the active scenario output."""
            
            st.markdown(greeting_response)
            st.session_state.messages.append({"role": "assistant", "content": greeting_response})

        elif is_methodology_query:
            methodology_response = f"""### 📊 Calculation Methodology

#### Household connection formula
Estimated household connections are calculated in two steps:

1. **Person-level new connections**
`(NewConnections2025 * ElecStatusIn2025) + NewConnections2030`

2. **Estimated household connections**
`Person-level new connections / NumPeoplePerHH`

For the active scenario, this gives:

* **Estimated Household Connections (2030):** {metrics['estimated_household_connections']:,} Households

#### Household connections by technology
* **Grid Densification:** {metrics['estimated_household_connections_by_technology']['grid_densification']:,} Households
* **Grid Extension:** {metrics['estimated_household_connections_by_technology']['grid_extension']:,} Households
* **Mini-Grid Infrastructure:** {metrics['estimated_household_connections_by_technology']['mini_grid']:,} Households
* **Standalone Solar Systems (SHS):** {metrics['estimated_household_connections_by_technology']['standalone_solar']:,} Households

#### Investment formula
`(InvestmentCost2025 * ElecStatusIn2025) + InvestmentCost2030`

#### Caveat
The `NewConnections2025` and `NewConnections2030` columns are interpreted as person-level new connections. Household values are estimated using `NumPeoplePerHH` and should be validated against the official GEP/OnSSET reference outputs.
"""
            st.markdown(methodology_response)
            st.session_state.messages.append({"role": "assistant", "content": methodology_response})

        elif is_province_query:
            province_response = """### Province-Level Query Not Yet Enabled

Province-level outputs are planned for the next deterministic calculation layer, but they are not enabled in this version.

The current version supports national-level outputs for:
* investment by technology
* estimated household connections
* estimated household connections by technology

The next sprint can extend the same calculation engine to `Admin1` province filtering once the IEP team confirms the relevant formulas and column conventions.
"""
            st.markdown(province_response)
            st.session_state.messages.append({"role": "assistant", "content": province_response})

        elif is_capacity_query:
            capacity_response = """### Capacity Query Not Yet Enabled

Capacity-by-technology outputs are listed as the next deterministic calculation group, but they are not enabled in this version.

The next implementation step is to validate whether `Tot_Cap` is the correct capacity field to aggregate for the active OnSSET/GEP result file and whether any time-step filtering is required.

The current version supports national-level investment and estimated household-connection outputs by technology.
"""
            st.markdown(capacity_response)
            st.session_state.messages.append({"role": "assistant", "content": capacity_response})

        elif is_multi_scenario_query:
            scenario_response = """### Multi-Scenario Comparison Not Yet Enabled

This version is currently locked to one active Mozambique electrification scenario: `mz-3-0_0_0_0_0_0`.

Multi-scenario comparison is planned for a later version after the deterministic formulas are validated for the active scenario. The current version can answer national investment and estimated household-connection questions for the active scenario only.
"""
            st.markdown(scenario_response)
            st.session_state.messages.append({"role": "assistant", "content": scenario_response})

        elif is_mini_grid_count_query:
            minigrid_response = """### Mini-Grid Count Not Yet Enabled

Mini-grid project counts are planned for the next deterministic calculation layer, but they are not enabled in this version.

Before implementation, the IEP team should confirm whether each settlement cluster assigned to mini-grid technology codes 5, 6, or 7 should be counted as one mini-grid project, or whether a separate project-count convention should be used.

The current version supports national-level investment and estimated household-connection outputs by technology.
"""
            st.markdown(minigrid_response)
            st.session_state.messages.append({"role": "assistant", "content": minigrid_response})

        elif is_grid_line_query:
            grid_line_response = """### Grid-Line Length Query Not Yet Enabled

Grid-line length outputs are not enabled in this version.

The next implementation step is to confirm which result-file column should be used for kilometers of new grid lines and whether it applies only to grid-extension sites or also to other grid-related categories.

The current version supports national-level investment and estimated household-connection outputs by technology.
"""
            st.markdown(grid_line_response)
            st.session_state.messages.append({"role": "assistant", "content": grid_line_response})
            
        else:
            # Construct a traceably secure metadata payload object
            result_context = {
                "scenario": active_scenario_code,
                "scope": "national",
                "calculation_type": "investment_and_estimated_household_connections_by_technology",
                "columns_used": [
                    "FinalElecCode2030",
                    "InvestmentCost2025",
                    "InvestmentCost2030",
                    "ElecStatusIn2025",
                    "NewConnections2025",
                    "NewConnections2030",
                    "NumPeoplePerHH"
                ],
                "formulas": {
                    "investment_usd": "(InvestmentCost2025 * ElecStatusIn2025) + InvestmentCost2030",
                    "individual_connections": "(NewConnections2025 * ElecStatusIn2025) + NewConnections2030",
                    "estimated_household_connections": "individual_connections / NumPeoplePerHH",
                    "estimated_household_connections_by_technology": "Group estimated household connections by FinalElecCode2030 technology category"
                },
                "results": {
                    "grid_densification_investment_usd": metrics["grid_densification_investment_usd"],
                    "grid_extension_investment_usd": metrics["grid_extension_investment_usd"],
                    "mini_grid_investment_usd": metrics["mini_grid_investment_usd"],
                    "standalone_solar_investment_usd": metrics["standalone_solar_investment_usd"],
                    "estimated_household_connections": metrics["estimated_household_connections"],
                    "estimated_household_connections_by_technology": metrics["estimated_household_connections_by_technology"],
                    "dominant_technology_by_capex": metrics["dominant_technology_by_capex"]
                }
            }
            
            final = client.beta.chat.completions.parse(
                model="gpt-5.4-mini", 
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "system", "content": f"DETERMINISTIC VERIFIED CONTEXT OBJECT: {json.dumps(result_context)}"},
                    {"role": "system", "content": f"""HARD QUANTITATIVE TRUTH CONSTRAINTS:
- Absolute Grid Densification Investment: {metrics['grid_densification_investment_usd']:,.2f} USD
- Absolute Grid Extension Investment: {metrics['grid_extension_investment_usd']:,.2f} USD
- Absolute Mini-Grid Investment: {metrics['mini_grid_investment_usd']:,.2f} USD
- Absolute Standalone Solar Investment: {metrics['standalone_solar_investment_usd']:,.2f} USD
- Estimated Household Connections: {metrics['estimated_household_connections']:,} Households
- Estimated Household Connections by Technology: {json.dumps(metrics['estimated_household_connections_by_technology'])}
- Dominant Capital Cost Technology: {metrics['dominant_technology_by_capex']}.

Your written text analysis and narrative descriptions MUST align strictly with this object profile. Do not restate formulas or structural definitions, focus purely on interpreting the values."""},
                    {"role": "user", "content": user_query}
                ],
                # Fix 1 & 2: Shifted completely to narrative schema enforcement
                response_format=OnSSETNarrative
            )
            
            structured_data = final.choices[0].message.parsed
            
            clean_summary = structured_data.executive_summary.replace('`', '').replace('−', '-')
            clean_policy = structured_data.strategic_policy_recommendation.replace('`', '').replace('−', '-')
            
            # Formatted Clean Text Response mirroring Python metrics exactly
            answer = f"""### 📋 National Executive Analysis
{clean_summary}

#### ⚡ Technology-Disaggregated Capital Requirements (CAPEX)
* **Grid Densification Portfolio:** USD {metrics['grid_densification_investment_usd']:,.2f}
* **Grid Extension Portfolio:** USD {metrics['grid_extension_investment_usd']:,.2f}
* **Mini-Grid Infrastructure:** USD {metrics['mini_grid_investment_usd']:,.2f}
* **Standalone Solar Systems (SHS):** USD {metrics['standalone_solar_investment_usd']:,.2f}

#### 📊 Macro Scalability Metrics
* **Estimated Household Connections (2030):** {metrics['estimated_household_connections']:,} Households

#### 🏠 Estimated Household Connections by Technology
* **Grid Densification:** {metrics['estimated_household_connections_by_technology']['grid_densification']:,} Households
* **Grid Extension:** {metrics['estimated_household_connections_by_technology']['grid_extension']:,} Households
* **Mini-Grid Infrastructure:** {metrics['estimated_household_connections_by_technology']['mini_grid']:,} Households
* **Standalone Solar Systems (SHS):** {metrics['estimated_household_connections_by_technology']['standalone_solar']:,} Households

#### 🧭 Policy Interpretation
* **Strategic Policy Guidance:** {clean_policy}
"""

            st.markdown(answer)
            st.session_state.messages.append({"role": "assistant", "content": answer})
            
            # Dataframe Export Option
            st.download_button(
                label="💾 Export National Scenario Portfolio (CSV)", 
                data=convert_df(df), 
                file_name=f'{active_scenario_code}_national_export.csv', 
                mime='text/csv'
            )