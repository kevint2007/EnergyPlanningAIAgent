import streamlit as st
import pandas as pd
import openai
import json
from pydantic import BaseModel, Field
from typing import List

# --- 1. CONFIG & DATA ---
st.set_page_config(page_title="GridPath: National Planning Engine", layout="wide", page_icon="🛰️")

# Upgraded structured Pydantic model focused on required technology disaggregation metrics
class OnSSETAnalysis(BaseModel):
    executive_summary: str = Field(description="An authoritative, 2-sentence investment and electrification summary tailored for ministry planners. Plain text only. Do not use dollar signs, backticks, or symbols.")
    grid_extension_investment_usd: float = Field(description="Total capital investment required for grid extensions across the timeline.")
    mini_grid_investment_usd: float = Field(description="Total capital investment required for mini-grid infrastructure deployment.")
    standalone_solar_investment_usd: float = Field(description="Total capital investment required for standalone solar home systems.")
    total_new_connections: int = Field(description="The total number of new target household or population connections achieved across all technologies by 2030.")
    strategic_policy_recommendation: str = Field(description="A brief, 1-sentence macro policy recommendation focusing on technology deployment scaling based on the active climate scenario. Plain text only.")

@st.cache_data
def load_data(scenario_code):
    # Dynamically loads the pre-aggregated country-level summary file based on sidebar selection
    return pd.read_csv(f'data/{scenario_code}_summary.csv')

def convert_df(df_to_download):
    return df_to_download.to_csv(index=False).encode('utf-8')

# --- 2. THE BRAIN (Streamlined National Summary Matrix Reader) ---
def get_national_metrics(data):
    """
    Extracts the global country-level overview vectors from the pre-compiled summary matrix 
    to pass clean context right into the LLM context window.
    """
    df_copy = data.copy()
    return df_copy.to_json(orient='records')

# --- 3. SYSTEM INSTRUCTIONS (National Scale Mozambique Engine) ---
system_instruction = """
You are GridPath, the Senior National Energy Access Advisor for the Government of Mozambique.
You provide decisive, country-wide investment strategies based on the GEP/OnSSET climate framework data summaries.

STRICT GEOGRAPHIC BOUNDARY:
- Your active database contains the national electrification model runs for the entire country of Mozambique.
- If a user asks about individual micro-regions from previous pilots (like Sofia or Madagascar) or uncalibrated external territories, immediately decline. State clearly that GridPath has scaled to the Mozambique National Electrification Plan.

DATA INSIGHT MANDATE:
- Focus heavily on technology disaggregation as requested by ministry parameters.
- Look directly at the provided MOZAMBIQUE NATIONAL SUMMARY DATA MATRIX. Identify which technology has the absolute highest investment value.
- You must report concrete numbers for three core pathways: Grid Extension, Mini-Grids, and Standalone Solar Systems.
- Answer targeted questions systematically: investment required per technology, capacity targets, and connections achieved.

STRICT TECHNICAL RULES:
1. Format all large currency totals using plain text words or commas (e.g., 1,500,000 USD).
2. NEVER apologize for data scope limitations. Be authoritative.
3. Start directly with the strategic analysis. No small talk or greetings.
4. STYLING RULE: Write in clean, normal prose sentences. Do not include markdown bold markers (**), backticks (`), or dollar sign ($) characters inside your text fields. 
5. CRITICAL MATRICES RULE: Look at the actual numbers in the data matrix. Do not write out numbers as long text words. Use normal digits and short text descriptors (e.g., write '1.96 Billion USD' instead of 'one billion nine hundred million'). Explicitly state which technology pathway has the largest capital allocation based on the exact quantitative numbers in the file.
"""

# --- 4. SIDEBAR & INTERACTIVE PATHWAYS ---
with st.sidebar:
    st.title("🛰️ GridPath")
    st.subheader("National Decision Support")
    
    if st.button("🗑️ Clear Chat History"):
        st.session_state.messages = []
        st.rerun()
        
    st.divider()
    
    scenario_map = {
        "Reference Climate Scenario (0_0)": "mz-3-0_0_0_0_0_0",
        "Ambitious Climate Scenario (0_1)": "mz-3-0_1_0_0_0_0",
        "Maximized Climate Scenario (0_2)": "mz-3-0_0_0_0_0_1"
    }
    
    selected_scenario_name = st.selectbox(
        "Select GEP Model Scenario",
        options=list(scenario_map.keys())
    )
    active_scenario_code = scenario_map[selected_scenario_name]
    
    st.divider()
    st.info(f"Status: Operational\nScenario: {active_scenario_code}")
    st.caption("Developed for National IEP Framework Scaling")

# Load data dynamically based on the sidebar control input
df = load_data(active_scenario_code)

# --- 5. INITIALIZE CLIENT (Automated via Secrets) ---
client = openai.OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# --- 6. CHAT INTERFACE & FIXED LAYOUT ---
if "messages" not in st.session_state:
    st.session_state.messages = []

# Persistent Header Layout
st.markdown("### 👋 Welcome to GridPath National")
st.markdown(
    "I am your specialized **Decision Support Interface** scaled for the Mozambique National Electrification Strategy."
)

# --- PROGRAMMATIC PANDAS BASELINES & TRUE MILESTONE STACKING ---
# Ensure row header names are cleanly set as the lookup index for reliable row extraction
calc_df = df.copy()
calc_df.columns = [c.strip() for c in calc_df.columns]
calc_df.set_index(calc_df.columns[0], inplace=True)

# 1. Stacking Cumulative Investment Metrics (2025 + 2030 Columns)
grid_val = float(calc_df.loc['4.Investment_Grid', '2025'] + calc_df.loc['4.Investment_Grid', '2030'])
solar_val = float(calc_df.loc['4.Investment_SA_PV', '2025'] + calc_df.loc['4.Investment_SA_PV', '2030'])

# Mini-Grids combine Hydro and Solar/PV Hybrid pathways programmatically
mg_hydro_inv = float(calc_df.loc['4.Investment_MG_Hydro', '2025'] + calc_df.loc['4.Investment_MG_Hydro', '2030'])
mg_pv_inv = float(calc_df.loc['4.Investment_MG_PV_Hybrid', '2025'] + calc_df.loc['4.Investment_MG_PV_Hybrid', '2030'])
mini_val = mg_hydro_inv + mg_pv_inv

# 2. Stacking Cumulative New Consumer Connections Metrics (2025 + 2030 Columns)
grid_conns = int(calc_df.loc['2.New_Connections_Grid', '2025'] + calc_df.loc['2.New_Connections_Grid', '2030'])
solar_conns = int(calc_df.loc['2.New_Connections_SA_PV', '2025'] + calc_df.loc['2.New_Connections_SA_PV', '2030'])
mg_hydro_conns = int(calc_df.loc['2.New_Connections_MG_Hydro', '2025'] + calc_df.loc['2.New_Connections_MG_Hydro', '2030'])
mg_pv_conns = int(calc_df.loc['2.New_Connections_MG_PV_Hybrid', '2025'] + calc_df.loc['2.New_Connections_MG_PV_Hybrid', '2030'])

total_connections_calc = grid_conns + solar_conns + mg_hydro_conns + mg_pv_conns

# Evaluate true dominant technology footprint programmatically based on the active array data
if solar_val > grid_val and solar_val > mini_val:
    dominant_tech = "Standalone Solar Systems"
elif grid_val > solar_val and grid_val > mini_val:
    dominant_tech = "Grid Extension"
else:
    dominant_tech = "Mini-Grid Infrastructure"

# FIXED: Metric cards pinned to the top of the interface so they remain anchored during state changes
st.subheader("🛰️ National Scenario Matrix KPI Overview")
c1, c2, c3 = st.columns(3)
with c1:
    st.metric(label="Grid Extension Capital", value=f"M${grid_val / 1_000_000:.1f}")
with c2:
    st.metric(label="Mini-Grid Capital", value=f"M${mini_val / 1_000_000:.1f}")
with c3:
    st.metric(label="Standalone Solar Capital", value=f"M${solar_val / 1_000_000:.1f}")
st.divider()

st.markdown("💡 **Click one of these macro analytical capability shortcuts to run a country simulation instantly:**")
col1, col2, col3 = st.columns(3)
user_query = None

with col1:
    if st.button("📊 National Technology Mix", use_container_width=True, key="btn_tech_mix"):
        user_query = (
            "Provide a complete national comparative analysis of the required investment splits and targets "
            "across Grid Extension, Mini-Grids, and Standalone Solar pathways under the current active scenario profile."
        )
with col2:
    if st.button("⚡ Investment per Technology", use_container_width=True, key="btn_inv_tech"):
        user_query = (
            "What is the total capital expenditure required for each electrification technology by 2030, "
            "and what is the strategic policy recommendation for deployment?"
        )
with col3:
    if st.button("📋 Connections & Capacity", use_container_width=True, key="btn_conn_cap"):
        user_query = (
            "Summarize the total number of new consumer connections achieved by the model runs "
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
        
        is_small_talk = any(word in greetings_set for word in cleaned_query_words) or user_query.lower() in ["how can you help", "what do you do", "test"]
        
        if is_small_talk:
            greeting_response = """I am GridPath, your Senior National Energy Access Advisor for Mozambique. 

I can help you evaluate multi-scenario investment metrics and connection targets across three primary electrification pathways:
* **Grid Extension Portfolios**
* **Mini-Grid Infrastructure**
* **Standalone Solar Systems**

Please click one of the macro capability buttons above or enter an analytical question below to run a country simulation instantly."""
            
            st.markdown(greeting_response)
            st.session_state.messages.append({"role": "assistant", "content": greeting_response})
            
        else:
            dynamic_instruction = system_instruction + f"\nCURRENT ACTIVE MODEL PATHWAY: {selected_scenario_name} ({active_scenario_code})"
            summary_context = get_national_metrics(df)
            
            final = client.beta.chat.completions.parse(
                model="gpt-4o-mini", 
                messages=[
                    {"role": "system", "content": dynamic_instruction},
                    {"role": "system", "content": f"MOZAMBIQUE NATIONAL SUMMARY DATA MATRIX: {summary_context}"},
                    {"role": "system", "content": f"""HARD QUANTITATIVE TRUTH CONSTRAINTS:
- Absolute Grid Extension Investment: {grid_val:,.2f} USD
- Absolute Mini-Grid Investment: {mini_val:,.2f} USD
- Absolute Standalone Solar Investment: {solar_val:,.2f} USD
- True Grand Total Connections Achieved: {total_connections_calc:,} Households
- The technology pathway with the absolute highest financial requirement is: {dominant_tech}. 

Your written text analysis and executive summaries MUST explicitly reflect these hard calculations. You are forbidden from claiming Grid Extension has the highest financial allocation when the numbers state {dominant_tech} is higher."""},
                    {"role": "user", "content": user_query}
                ],
                response_format=OnSSETAnalysis
            )
            
            structured_data = final.choices[0].message.parsed
            
            clean_summary = structured_data.executive_summary.replace('`', '').replace('−', '-')
            clean_policy = structured_data.strategic_policy_recommendation.replace('`', '').replace('−', '-')
            
            # Formatted Markdown Response Block
            answer = f"""### 📋 National Executive Analysis
{clean_summary}

#### ⚡ Technology-Disaggregated Capital Requirements (CAPEX)
* **Grid Extension Portfolio:** USD {grid_val:,.2f}
* **Mini-Grid Infrastructure:** USD {mini_val:,.2f}
* **Standalone Solar Systems:** USD {solar_val:,.2f}

#### 📊 Macro Scalability Metrics
* **Total Targeted National Connections (2030):** {total_connections_calc:,} Households
* **Strategic Policy Guidance:** {clean_policy}
"""

            st.markdown(answer)
            st.session_state.messages.append({"role": "assistant", "content": answer})
            
            # Dataframe Export Option
            st.download_button(
                label="💾 Export National Summary Portfolio (CSV)", 
                data=convert_df(df), 
                file_name=f'{active_scenario_code}_national_export.csv', 
                mime='text/csv'
            )