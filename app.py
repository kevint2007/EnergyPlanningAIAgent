import streamlit as st
import pandas as pd
import openai
import json
from pydantic import BaseModel, Field
from typing import List

# --- 1. CONFIG & DATA ---
st.set_page_config(page_title="ChatOnSSET: Sofia Region", layout="wide", page_icon="🛰️")

# Enforce a strict Pydantic model for hard determinism in final outputs
class OnSSETAnalysis(BaseModel):
    executive_summary: str = Field(description="An authoritative, 2-sentence investment and electrification summary tailored for ministry planners.")
    total_investment_usd: float = Field(description="The calculated total financial investment required for the current query selection.")
    technology_split_breakdown: str = Field(description="A clean sentence breakdown summarizing the cheapest tech mix percentages (e.g., Grid Extension vs. Hybrid Mini-Grid).")
    strategic_priority_site_ids: List[int] = Field(description="List of the exact integer site IDs identified as high-yield target points.")

@st.cache_data
def load_data():
    # Loading the Sofia-specific calibrated dataset
    return pd.read_csv('madagascar_sofia_calibrated.csv')

def convert_df(df_to_download):
    # Function for CSV Export Task
    return df_to_download.to_csv(index=False).encode('utf-8')

df = load_data()

# --- 2. THE BRAIN (Optimized for Regional Analysis) ---
def generate_portfolio(data, n=10):
    portfolio = data.sort_values(by='AgroLink_Score', ascending=False).head(n).copy()
    portfolio['id'] = portfolio['id'].astype(int) 
    return portfolio[['id', 'AgroLink_Score', 'PVHybridGenCapex2025', 'Pop2030', 'Y_deg', 'X_deg', 'Social_Anchor']]

def budget_search(data, limit):
    options = data[data['PVHybridGenCapex2025'] <= limit].copy()
    if options.empty: return None
    results = options.sort_values(by='AgroLink_Score', ascending=False).head(3).copy()
    results['id'] = results['id'].astype(int)
    return results[['id', 'AgroLink_Score', 'PVHybridGenCapex2025', 'Pop2025', 'Y_deg', 'X_deg', 'Social_Anchor']]

# --- 3. SYSTEM INSTRUCTIONS (Data Discovery Mode with Strict Geofence) ---
system_instruction = """
You are ChatOnSSET, the Senior Energy Access Advisor ONLY for the Sofia Region of Madagascar.
You provide decisive, data-driven investment strategies based on the GEP/OnSSET framework.

STRICT GEOGRAPHIC GEOFENCE:
- Your active database ONLY contains data for the Sofia Region of Madagascar.
- If a user asks about ANY other region or territory outside Sofia (e.g., Boeny, Sava, Diana, Analamanga, Menabe, etc.), you MUST immediately decline the analysis. 
- State clearly that ChatOnSSET V1 is strictly geofenced to the calibrated Sofia Electrification Plan, and you do not have parameters or live tools for outside territories.
- NEVER call your tools or apply Sofia site data (such as Site 125389) to queries about other regions.

DATA DISCOVERY MANDATE:
- For Sofia-specific queries, you have direct access to the dataset via your tools. 
- If the user asks for averages, regional scores, or totals within Sofia, you MUST call your tools to retrieve data before answering. 
- NEVER say "I don't have access" if the data can be retrieved. Fetch a portfolio of sites first, then calculate the answer.

STRICT TECHNICAL RULES:
1. ONLY use the 'id' numbers provided by the tool. Never guess an ID.
2. ONLY report 'Social Anchor: Yes' if the data shows 1. If it shows 0, report 'No'.
3. Be authoritative: If a site appears in multiple searches, call it a 'Strategic Priority.'
4. NEVER apologize for data limits or use the word 'hypothetical.'
5. Use **bold** for Site IDs (e.g., **Site 8483**).
6. Format all currency with commas (e.g., $1,500,000) and scores to 2 decimal places.
7. Start directly with the analysis. No small talk.
"""

# --- 4. SIDEBAR ---
with st.sidebar:
    st.title("🛰️ ChatOnSSET V1")
    st.subheader("Sofia Region, Madagascar")
    
    if st.button("🗑️ Clear Chat History"):
        st.session_state.messages = []
        st.rerun()
        
    st.divider()
    st.info("Status: Operational | Calibration: Sofia Region")
    st.markdown("---")
    st.caption("Developed for IEP Framework Analysis")

# --- 5. INITIALIZE CLIENT (Automated via Secrets) ---
client = openai.OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# --- 6. CHAT INTERFACE ---
if "messages" not in st.session_state:
    st.session_state.messages = []

user_query = None

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if not st.session_state.messages:
    st.markdown("### 👋 Welcome to ChatOnSSET V1")
    st.markdown(
        "I am your specialized **Decision Support Interface** calibrated for the Sofia Integrated Electrification Plan. "
        "I abstract away complex GIS engineering to turn messy rows of spreadsheet data into instant, authoritative policy insights."
    )
    st.markdown(
        "💡 **You can type any custom question in plain English in the chat bar below, "
        "or click one of these foundational analytical capabilities to run an automated simulation instantly:**"
    )
    
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("📊 Budget Comparisons", use_container_width=True):
            user_query = (
                "Perform a comparative analysis of 3 high-impact sites for a $500,000 budget vs. a $2,500,000 budget. "
                "For each tier, verify the presence of Social Anchors and calculate the average AgroLink Score. "
                "Provide a brief strategic recommendation on which budget offers the best scalability for solar-powered irrigation in the Sofia Region."
            )
    with col2:
        if st.button("🛰️ Investment Clusters", use_container_width=True):
            user_query = (
                "Perform a regional overview of the Sofia Region. What is the average AgroLink score across the top 10 sites, "
                "and where are the primary investment clusters located?"
            )
    with col3:
        if st.button("📋 Dataset Core Metrics", use_container_width=True):
            user_query = (
                "What specific metrics and data points are tracked within the Sofia dataset? "
                "Briefly explain what parameters like AgroLink Score and Social Anchors mean to a non-technical investor."
            )
    st.divider()

if chat_prompt := st.chat_input("Analyze Sofia regional impact..."):
    user_query = chat_prompt

# --- 7. AGENT EXECUTION LOOP ---
if user_query:
    st.session_state.messages.append({"role": "user", "content": user_query})
    with st.chat_message("user"):
        st.markdown(user_query)

    with st.chat_message("assistant"):
        response = client.chat.completions.create(
            model="gpt-5.4-mini",
            messages=[{"role": "system", "content": system_instruction}, {"role": "user", "content": user_query}],
            tools=[
                {"type": "function", "function": {"name": "budget_search", "description": "Finds sites under a specific USD budget.", "parameters": {"type": "object", "properties": {"limit": {"type": "number"}}, "required": ["limit"]}}},
                {"type": "function", "function": {"name": "generate_portfolio", "description": "Finds top impact sites for regional analysis.", "parameters": {"type": "object", "properties": {"n": {"type": "integer"}}}}}
            ]
        )
        
        msg = response.choices[0].message
        
        if msg.tool_calls:
            tool_messages = [{"role": "system", "content": system_instruction}, {"role": "user", "content": user_query}, msg]
            all_found_data = [] 
            
            for tool_call in msg.tool_calls:
                args = json.loads(tool_call.function.arguments)
                
                if tool_call.function.name == "budget_search":
                    res = budget_search(df, args['limit'])
                else:
                    res = generate_portfolio(df, args.get('n', 10))
                
                if res is not None:
                    all_found_data.append(res)
                    tool_messages.append({"role": "tool", "content": res.to_json(), "tool_call_id": tool_call.id})
                else:
                    tool_messages.append({"role": "tool", "content": "None", "tool_call_id": tool_call.id})
            
            # CRITICAL FIX: Enforce deterministic output formats with `.parse()`
            final = client.beta.chat.completions.parse(
                model="gpt-5.4-mini", 
                messages=tool_messages,
                response_format=OnSSETAnalysis
            )
            
            structured_data = final.choices[0].message.parsed
            
            # Map object attributes uniformly to clean up raw prompt leaks completely
            answer = f"""### 📋 Executive Analysis
{structured_data.executive_summary}

* **Total Required Capital Expenditure (CAPEX):** ${structured_data.total_investment_usd:,.2f}
* **Optimal Technology Split:** {structured_data.technology_split_breakdown}
* **Identified Strategic Site IDs:** {', '.join([f'**Site {uid}**' for uid in structured_data.strategic_priority_site_ids])}
"""

            st.markdown(answer)
            st.session_state.messages.append({"role": "assistant", "content": answer})
            
            # --- RENDER STRATEGIC DASHBOARD ---
            if all_found_data:
                combined_df = pd.concat(all_found_data).drop_duplicates(subset='id')
                
                if "budget" in user_query.lower() or "$" in user_query:
                    display_df = combined_df[combined_df['PVHybridGenCapex2025'] <= combined_df['PVHybridGenCapex2025'].mean() * 1.5]
                else:
                    display_df = combined_df.head(4)
                
                if display_df.empty: display_df = combined_df.head(4)

                st.divider()
                st.subheader("📊 Strategic Site Analysis")
                cols = st.columns(len(display_df.head(4)))
                
                for i, (index, row) in enumerate(display_df.head(4).iterrows()):
                    with cols[i]:
                        st.metric(label=f"Site {int(row['id'])}", value=f"{row['AgroLink_Score']:.2f}")
                        st.write(f"**CAPEX:** ${row['PVHybridGenCapex2025']:,.0f}")
                        if row.get('Social_Anchor') == 1:
                            st.success("🏥 Anchor")

                # Export & Mapping
                st.download_button(label="💾 Export Portfolio (CSV)", data=convert_df(display_df), file_name='sofia_portfolio_export.csv', mime='text/csv')
                st.markdown("#### 🗺️ Geographic Distribution of Identified Sites")
                st.map(display_df.rename(columns={'Y_deg': 'lat', 'X_deg': 'lon'}))
        else:
            answer_non_tool = msg.content
            st.markdown(answer_non_tool)
            st.session_state.messages.append({"role": "assistant", "content": answer_non_tool})