import streamlit as st
import pandas as pd
import numpy as np
import openai
import json
import unicodedata
from pydantic import BaseModel, Field

# --- 1. CONFIG & DATA PREPROCESSING ---
st.set_page_config(
    page_title="ChatOnSSET: National Planning Engine",
    layout="wide",
    page_icon="🛰️"
)

# Python controls numbers. The LLM only writes narrative interpretation.
class OnSSETNarrative(BaseModel):
    executive_summary: str = Field(
        description=(
            "A clear, 2-sentence analytical summary tailored for energy planners. "
            "Use only the modelled numbers provided in the context object. Plain text only. "
            "Do not use dollar signs, backticks, asterisks, or unsupported symbols."
        )
    )
    scenario_observation: str = Field(
        description=(
            "A cautious, 1-sentence analytical observation based only on the modelled scenario results. "
            "Do not prescribe policy actions or implementation decisions. "
            "Do not say a technology should be prioritized solely because it has the highest CAPEX, "
            "highest connection count, highest capacity, or highest mini-grid count. Plain text only."
        )
    )


# Required columns for current deterministic V4 baseline.
REQUIRED_COLUMNS = [
    "FinalElecCode2030",
    "InvestmentCost2025",
    "InvestmentCost2030",
    "ElecStatusIn2025",
    "NewConnections2025",
    "NewConnections2030",
    "NumPeoplePerHH",
    "PopStartYear",
    "Pop2030",
    "ElecPopCalib",
    "CurrentMVLineDist",
    "NewCapacity2025",
    "NewCapacity2030",
    "Admin1"
]


# Current module registry.
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
        "notes": "Household values are estimated from person-level connection columns. Year-specific household estimates are calculated separately for 2025 and 2030 milestones."
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
        "status": "implemented",
        "scope": "national",
        "columns_used": [
            "PopStartYear",
            "Pop2030",
            "ElecPopCalib",
            "CurrentMVLineDist"
        ],
        "formula": (
            "Base population = sum(PopStartYear); 2030 population = sum(Pop2030); "
            "currently unelectrified population = sum(PopStartYear - ElecPopCalib); "
            "near-grid unelectrified population filters CurrentMVLineDist <= 10."
        ),
        "notes": "Uses ElecPopCalib to account for partially electrified settlements at the start of analysis."
    },
    "capacity_by_technology": {
        "status": "implemented",
        "scope": "national",
        "columns_used": [
            "FinalElecCode2030",
            "NewCapacity2025",
            "NewCapacity2030",
            "ElecStatusIn2025"
        ],
        "formula": "(NewCapacity2025 * ElecStatusIn2025) + NewCapacity2030, grouped by FinalElecCode2030.",
        "notes": "Uses the same time-step logic as investment for consistency."
    },
    "mini_grid_count": {
        "status": "implemented",
        "scope": "national",
        "columns_used": [
            "FinalElecCode2030",
            "Total_New_Capacity_kW",
            "Estimated_Connections_HH"
        ],
        "formula": "Count settlement clusters where FinalElecCode2030 is in [5, 6, 7].",
        "notes": "This is interpreted as a settlement-cluster mini-grid count, not necessarily a final engineered project count."
    },
    "province_summary": {
        "status": "implemented",
        "scope": "Admin1",
        "columns_used": ["Admin1"],
        "formula": "Filter the processed dataframe by Admin1, then reuse the same deterministic summary engine used for national calculations.",
        "notes": "Province summaries support investment, estimated household connections, population, capacity, and mini-grid settlement-cluster count."
    },
    "grid_line_km": {
        "status": "planned",
        "scope": "national and Admin1",
        "columns_needed": ["NewGridExtensionDist2025", "NewGridExtensionDist2030"],
        "notes": "Grid-line distance columns still need output-format confirmation."
    }
}


@st.cache_data
def load_scenario_and_process(file_path):
    raw_df = pd.read_csv(file_path)

    missing_columns = [col for col in REQUIRED_COLUMNS if col not in raw_df.columns]
    if missing_columns:
        raise ValueError(
            "The active scenario file is missing required columns: "
            + ", ".join(missing_columns)
        )

    processed_df = raw_df.copy()

    for col in REQUIRED_COLUMNS:
        if col == "Admin1":
            processed_df[col] = processed_df[col].fillna("Unknown").astype(str)
        else:
            processed_df[col] = processed_df[col].fillna(0)

    # Andreas clarification: currently unelectrified population should account for partial electrification.
    processed_df["Unelectrified_Pop_Start"] = (
        processed_df["PopStartYear"] - processed_df["ElecPopCalib"]
    ).clip(lower=0)

    # Person-level new connections.
    processed_df["True_Connections_Individuals"] = (
        processed_df["NewConnections2025"] * processed_df["ElecStatusIn2025"]
    ) + processed_df["NewConnections2030"]

    # Household estimate from person-level new connections.
    safe_hh_denom = np.where(
        processed_df["NumPeoplePerHH"] == 0,
        np.inf,
        processed_df["NumPeoplePerHH"]
    )
    processed_df["Estimated_Connections_HH"] = (
        processed_df["True_Connections_Individuals"] / safe_hh_denom
    ).fillna(0)

    # Household connections by milestone year.
    processed_df["Connections_Individuals_2025"] = (
        processed_df["NewConnections2025"] * processed_df["ElecStatusIn2025"]
    )
    processed_df["Connections_Individuals_2030"] = processed_df["NewConnections2030"]

    processed_df["Estimated_Connections_HH_2025"] = (
        processed_df["Connections_Individuals_2025"] / safe_hh_denom
    ).fillna(0)
    processed_df["Estimated_Connections_HH_2030"] = (
        processed_df["Connections_Individuals_2030"] / safe_hh_denom
    ).fillna(0)

    # Investment formula confirmed as acceptable for consistency.
    processed_df["Total_Investment_USD"] = (
        processed_df["InvestmentCost2025"] * processed_df["ElecStatusIn2025"]
    ) + processed_df["InvestmentCost2030"]

    # Capacity formula using the same validated time-step logic.
    processed_df["Total_New_Capacity_kW"] = (
        processed_df["NewCapacity2025"] * processed_df["ElecStatusIn2025"]
    ) + processed_df["NewCapacity2030"]

    return processed_df.copy()


# --- 2. DETERMINISTIC CALCULATION FUNCTIONS ---
def calculate_national_summary(processed_df):
    densification_codes = [1]
    extension_codes = [2]
    sa_codes = [3]
    mg_codes = [5, 6, 7]

    densification_df = processed_df[processed_df["FinalElecCode2030"].isin(densification_codes)]
    extension_df = processed_df[processed_df["FinalElecCode2030"].isin(extension_codes)]
    solar_df = processed_df[processed_df["FinalElecCode2030"].isin(sa_codes)]
    mini_df = processed_df[processed_df["FinalElecCode2030"].isin(mg_codes)]

    # Investment by technology.
    densification_val = float(densification_df["Total_Investment_USD"].sum())
    extension_val = float(extension_df["Total_Investment_USD"].sum())
    solar_val = float(solar_df["Total_Investment_USD"].sum())
    mini_val = float(mini_df["Total_Investment_USD"].sum())

    # Household connections.
    total_connections_hh_calc = int(round(processed_df["Estimated_Connections_HH"].sum()))
    connections_hh_2025 = int(round(processed_df["Estimated_Connections_HH_2025"].sum()))
    connections_hh_2030 = int(round(processed_df["Estimated_Connections_HH_2030"].sum()))

    densification_hh = float(densification_df["Estimated_Connections_HH"].sum())
    extension_hh = float(extension_df["Estimated_Connections_HH"].sum())
    solar_hh = float(solar_df["Estimated_Connections_HH"].sum())
    mini_hh = float(mini_df["Estimated_Connections_HH"].sum())

    # Population.
    base_population = float(processed_df["PopStartYear"].sum())
    target_population_2030 = float(processed_df["Pop2030"].sum())
    unelectrified_population_start = float(processed_df["Unelectrified_Pop_Start"].sum())
    unelectrified_within_10km_mv = float(
        processed_df[processed_df["CurrentMVLineDist"] <= 10]["Unelectrified_Pop_Start"].sum()
    )

    # Capacity by technology.
    densification_capacity_kw = float(densification_df["Total_New_Capacity_kW"].sum())
    extension_capacity_kw = float(extension_df["Total_New_Capacity_kW"].sum())
    solar_capacity_kw = float(solar_df["Total_New_Capacity_kW"].sum())
    mini_capacity_kw = float(mini_df["Total_New_Capacity_kW"].sum())

    total_new_capacity_kw = (
        densification_capacity_kw
        + extension_capacity_kw
        + solar_capacity_kw
        + mini_capacity_kw
    )

    # Mini-grid count.
    mini_grid_cluster_count = int(len(mini_df))

    if mini_grid_cluster_count > 0:
        average_mini_grid_capacity_kw = float(mini_df["Total_New_Capacity_kW"].mean())
        average_mini_grid_households = int(round(mini_df["Estimated_Connections_HH"].mean()))
    else:
        average_mini_grid_capacity_kw = 0.0
        average_mini_grid_households = 0

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
        "estimated_household_connections_by_year": {
            "2025": connections_hh_2025,
            "2030": connections_hh_2030
        },
        "estimated_household_connections_by_technology": {
            "grid_densification": int(round(densification_hh)),
            "grid_extension": int(round(extension_hh)),
            "standalone_solar": int(round(solar_hh)),
            "mini_grid": int(round(mini_hh))
        },
        "population_summary": {
            "base_population": int(round(base_population)),
            "target_population_2030": int(round(target_population_2030)),
            "unelectrified_population_start": int(round(unelectrified_population_start)),
            "unelectrified_within_10km_mv": int(round(unelectrified_within_10km_mv))
        },
        "capacity_by_technology_kw": {
            "grid_densification": densification_capacity_kw,
            "grid_extension": extension_capacity_kw,
            "standalone_solar": solar_capacity_kw,
            "mini_grid": mini_capacity_kw
        },
        "total_new_capacity_kw": total_new_capacity_kw,
        "mini_grid_summary": {
            "mini_grid_cluster_count": mini_grid_cluster_count,
            "average_mini_grid_capacity_kw": average_mini_grid_capacity_kw,
            "average_mini_grid_households": average_mini_grid_households
        },
        "dominant_technology_by_capex": dominant_tech
    }


def normalize_text(value):
    """Normalize text for robust province matching."""
    value = str(value).strip().lower()
    value = unicodedata.normalize("NFKD", value)
    value = "".join(char for char in value if not unicodedata.combining(char))
    return value


def find_province_in_query(processed_df, query_lower):
    """Detect whether the user's query mentions an Admin1 province in the active scenario file."""
    normalized_query = normalize_text(query_lower)
    province_names = (
        processed_df["Admin1"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )
    province_names = sorted(province_names, key=len, reverse=True)

    for province in province_names:
        if normalize_text(province) in normalized_query:
            return province

    return None


def calculate_province_summary(processed_df, province_name):
    """Filter by Admin1 and reuse the national summary engine on that province subset."""
    province_mask = processed_df["Admin1"].apply(normalize_text) == normalize_text(province_name)
    province_df = processed_df[province_mask].copy()

    if province_df.empty:
        return None

    province_metrics = calculate_national_summary(province_df)
    province_metrics["province_name"] = province_name
    province_metrics["settlement_cluster_count"] = int(len(province_df))

    return province_metrics


def convert_df(df_to_download):
    return df_to_download.to_csv(index=False).encode("utf-8")


def format_usd_short(value):
    if value >= 1_000_000_000:
        return f"USD {value / 1_000_000_000:.2f}B"
    return f"USD {value / 1_000_000:.1f}M"


def format_capacity(value_kw):
    if value_kw >= 1000:
        return f"{value_kw / 1000:,.2f} MW"
    return f"{value_kw:,.2f} kW"


# Global initialization.
active_scenario_code = "mz-3-0_0_0_0_0_0"

try:
    df = load_scenario_and_process(f"data/{active_scenario_code}.csv")
    metrics = calculate_national_summary(df)
except FileNotFoundError:
    st.error(f"Please ensure {active_scenario_code}.csv is placed in your 'data/' folder.")
    st.stop()
except ValueError as exc:
    st.error(str(exc))
    st.stop()


# --- 3. SYSTEM INSTRUCTIONS ---
system_instruction = """
You are ChatOnSSET, a technical interpretation assistant for Mozambique GEP/OnSSET electrification scenario outputs.
You provide country-wide investment, population, capacity, mini-grid, and connection summaries based on deterministic Python calculations from the active scenario.

DATA DICTIONARY MAPPING:
- id: Unique identifier per settlement cluster.
- Admin1: Admin level 1 name, such as province or region.
- PopStartYear: Population in the base/start year of the analysis.
- Pop2030: Projected population of the settlement at the end year of the analysis.
- ElecPopCalib: Calibrated electrified population at the start of analysis.
- CurrentMVLineDist: Distance in km to nearest existing medium-voltage line.
- Admin1: Province or first-level administrative unit used for province summaries.
- FinalElecCode2030: Final selected electrification technology.
    * Code 1 = Grid Densification
    * Code 2 = Grid Extension
    * Code 3 = Standalone Solar PV / SHS
    * Code 5, 6, or 7 = Mini-Grid

STRICT TECHNICAL RULES:
1. Format large currency totals using plain text words or commas.
2. If a query is outside the enabled deterministic calculation scope, state that the query is not yet enabled.
3. Start directly with the analysis. No greetings.
4. Do not include markdown bold markers, backticks, or dollar signs inside structured text fields.
5. Do not invent numbers. Use only the deterministic context object provided by Python.
6. Province-level outputs are enabled only when Python provides a validated Admin1-filtered result object.
7. Do not prescribe policy actions or implementation decisions. Do not recommend prioritizing a technology solely because it has the highest CAPEX, highest capacity, highest mini-grid count, or highest connection count.
"""


# --- 4. SIDEBAR ---
with st.sidebar:
    st.title("🛰️ ChatOnSSET")
    st.subheader("National Decision Support")

    if st.button("🗑️ Clear Chat History"):
        st.session_state.messages = []
        st.rerun()

    st.divider()
    st.info(
        f"Status: Operational\n"
        f"Test Scenario: {active_scenario_code}\n"
        f"Data Mode: Deterministic Python summaries"
    )
    st.caption("Developed for National IEP Framework Scaling")


# --- 5. OPENAI CLIENT ---
client = openai.OpenAI(api_key=st.secrets["OPENAI_API_KEY"])


# --- 6. CHAT INTERFACE ---
if "messages" not in st.session_state:
    st.session_state.messages = []

st.markdown("### 👋 Welcome to ChatOnSSET National")
st.markdown(
    "I am your specialized **Analytical Interface** for Mozambique GEP/OnSSET scenario analysis."
)

st.subheader("🛰️ National Scenario Matrix KPI Overview")
c1, c2, c3, c4 = st.columns(4)

with c1:
    st.metric(
        label="Grid Densification CAPEX",
        value=format_usd_short(metrics["grid_densification_investment_usd"])
    )
with c2:
    st.metric(
        label="Grid Extension CAPEX",
        value=format_usd_short(metrics["grid_extension_investment_usd"])
    )
with c3:
    st.metric(
        label="Mini-Grid CAPEX",
        value=format_usd_short(metrics["mini_grid_investment_usd"])
    )
with c4:
    st.metric(
        label="Standalone Solar CAPEX",
        value=format_usd_short(metrics["standalone_solar_investment_usd"])
    )

with st.expander("📊 Calculation Methodology & Traceability Notes"):
    st.markdown("""
    * **Investment Formula:** `(InvestmentCost2025 * ElecStatusIn2025) + InvestmentCost2030`
    * **Connection Formula:** `(NewConnections2025 * ElecStatusIn2025) + NewConnections2030`
    * **Household Connections Formula:** `Person-level new connections / NumPeoplePerHH`
    * **Unelectrified Population Formula:** `PopStartYear - ElecPopCalib`
    * **Near-Grid Unelectrified Population Filter:** `CurrentMVLineDist <= 10`
    * **Capacity Formula:** `(NewCapacity2025 * ElecStatusIn2025) + NewCapacity2030`
    * **Mini-Grid Count Formula:** Count settlement clusters where `FinalElecCode2030` is in `[5, 6, 7]`
    """)
    st.markdown("#### Current Question Registry")
    st.json(QUESTION_REGISTRY)

st.divider()

st.markdown("💡 **Click one of these shortcuts to query the active national scenario output:**")
col1, col2, col3, col4, col5 = st.columns(5)
user_query = None

with col1:
    if st.button("📊 Investment", use_container_width=True, key="btn_inv"):
        user_query = "What is the total capital expenditure required for each electrification technology by 2030?"

with col2:
    if st.button("🏠 Connections", use_container_width=True, key="btn_conn"):
        user_query = "How many estimated household connections are achieved by 2030?"

with col3:
    if st.button("👥 Population", use_container_width=True, key="btn_pop"):
        user_query = "What is the national population summary?"

with col4:
    if st.button("🔋 Capacity", use_container_width=True, key="btn_cap"):
        user_query = "What is the total capacity required by technology?"

with col5:
    if st.button("🧩 Mini-Grids", use_container_width=True, key="btn_mg"):
        user_query = "How many mini-grids need to be built?"

st.divider()

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
        query_lower = user_query.lower()
        province_match = find_province_in_query(df, query_lower)

        greetings_set = {"hi", "hello", "hey", "greetings", "howdy"}
        is_small_talk = (
            any(word in greetings_set for word in cleaned_query_words)
            or query_lower in ["how can you help", "what do you do", "test"]
        )

        methodology_keywords = [
            "formula",
            "methodology",
            "method",
            "calculate",
            "calculation",
            "how are you calculating",
            "how do you calculate",
            "connection formula",
            "household formula",
            "capacity formula",
            "population formula",
            "mini-grid formula",
            "minigrid formula"
        ]

        population_keywords = [
            "population",
            "unelectrified",
            "un-electrified",
            "un electrified",
            "currently unelectrified",
            "currently un-electrified",
            "within 10 km",
            "within 10km",
            "10 km",
            "10km",
            "mv lines",
            "mv line",
            "medium voltage"
        ]

        investment_keywords = [
            "investment",
            "capital expenditure",
            "capex",
            "capital cost",
            "cost by technology",
            "investment by technology",
            "expenditure required",
            "total capital expenditure",
            "technology-disaggregated capital"
        ]

        connection_keywords = [
            "household connections",
            "estimated household connections",
            "new connections",
            "connections achieved",
            "connections by technology",
            "connection targets",
            "number of connections",
            "how many connections",
            "electrified households",
            "households electrified"
        ]

        capacity_keywords = [
            "capacity",
            "kw",
            "kilowatt",
            "mw",
            "megawatt",
            "generation capacity",
            "capacity by technology"
        ]

        mini_grid_count_keywords = [
            "how many mini-grids",
            "number of mini-grids",
            "mini-grid count",
            "minigrid count",
            "mini grids need to be built",
            "mini-grids need to be built",
            "how many minigrids",
            "number of minigrids"
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

        grid_line_keywords = [
            "grid lines",
            "grid line",
            "new grid lines",
            "kilometers",
            "kilometres",
            "km of"
        ]

        is_methodology_query = any(keyword in query_lower for keyword in methodology_keywords)
        is_investment_query = any(keyword in query_lower for keyword in investment_keywords)
        is_connection_query = any(keyword in query_lower for keyword in connection_keywords)
        is_population_query = any(keyword in query_lower for keyword in population_keywords)
        is_capacity_query = any(keyword in query_lower for keyword in capacity_keywords)
        is_mini_grid_count_query = any(keyword in query_lower for keyword in mini_grid_count_keywords)

        is_near_grid_population_query = is_population_query and (
            "10 km" in query_lower
            or "10km" in query_lower
            or "mv line" in query_lower
            or "mv lines" in query_lower
            or "medium voltage" in query_lower
            or "near existing mv" in query_lower
        )

        is_current_unelectrified_query = is_population_query and (
            "unelectrified" in query_lower
            or "un-electrified" in query_lower
            or "un electrified" in query_lower
        )

        is_province_query = (
            province_match is not None
            or any(province in query_lower for province in mozambique_provinces)
            or "province" in query_lower
            or "admin1" in query_lower
        )
        is_multi_scenario_query = any(keyword in query_lower for keyword in multi_scenario_keywords)
        is_grid_line_query = any(keyword in query_lower for keyword in grid_line_keywords)

        if is_small_talk:
            greeting_response = """I am ChatOnSSET, your national GEP/OnSSET scenario analysis assistant for Mozambique.

I can help you evaluate investment metrics, connection targets, population metrics, capacity requirements, and mini-grid cluster counts for the active electrification scenario across four primary pathways:

* **Grid Densification**
* **Grid Extension**
* **Mini-Grid Infrastructure**
* **Standalone Solar Systems**

Please click one of the shortcuts above or enter an analytical question below to query the active scenario output."""
            st.markdown(greeting_response)
            st.session_state.messages.append({"role": "assistant", "content": greeting_response})

        elif is_methodology_query:
            mg = metrics["mini_grid_summary"]
            methodology_response = f"""### 📊 Calculation Methodology

#### Investment formula
`(InvestmentCost2025 * ElecStatusIn2025) + InvestmentCost2030`

#### Household connection formula
Person-level new connections:

`(NewConnections2025 * ElecStatusIn2025) + NewConnections2030`

Estimated household connections:

`Person-level new connections / NumPeoplePerHH`

#### Unelectrified population formula
`PopStartYear - ElecPopCalib`

This accounts for settlements that may be partially electrified at the start of the analysis.

#### Near-grid unelectrified population filter
`CurrentMVLineDist <= 10`

#### Capacity formula
`(NewCapacity2025 * ElecStatusIn2025) + NewCapacity2030`

#### Mini-grid count formula
Count settlement clusters where:

`FinalElecCode2030 in [5, 6, 7]`

This should be interpreted as a settlement-cluster count, not necessarily a final engineered project count.

For the active scenario, this gives:

* **Estimated Household Connections:** {metrics['estimated_household_connections']:,} households
* **Estimated Household Connections from 2025 Step:** {metrics['estimated_household_connections_by_year']['2025']:,} households
* **Estimated Household Connections from 2030 Step:** {metrics['estimated_household_connections_by_year']['2030']:,} households
* **Currently Unelectrified Population:** {metrics['population_summary']['unelectrified_population_start']:,} people
* **Near-Grid Unelectrified Population:** {metrics['population_summary']['unelectrified_within_10km_mv']:,} people
* **Total New Capacity:** {format_capacity(metrics['total_new_capacity_kw'])}
* **Mini-Grid Settlement-Cluster Count:** {mg['mini_grid_cluster_count']:,}
"""
            st.markdown(methodology_response)
            st.session_state.messages.append({"role": "assistant", "content": methodology_response})

        elif is_investment_query and not is_province_query:
            total_investment = (
                metrics["grid_densification_investment_usd"]
                + metrics["grid_extension_investment_usd"]
                + metrics["mini_grid_investment_usd"]
                + metrics["standalone_solar_investment_usd"]
            )

            investment_response = f"""### National Investment by Technology

#### Total Modelled CAPEX
* **Total Modelled CAPEX:** USD {total_investment:,.2f}

#### Modelled CAPEX by Technology
* **Grid Densification:** USD {metrics['grid_densification_investment_usd']:,.2f}
* **Grid Extension:** USD {metrics['grid_extension_investment_usd']:,.2f}
* **Mini-Grid Infrastructure:** USD {metrics['mini_grid_investment_usd']:,.2f}
* **Standalone Solar Systems (SHS):** USD {metrics['standalone_solar_investment_usd']:,.2f}

#### Analytical Note
This result summarizes modelled investment outputs from the active scenario. It does not prescribe implementation decisions.

#### Methodology
Investment is calculated using:

`(InvestmentCost2025 * ElecStatusIn2025) + InvestmentCost2030`

The resulting values are grouped by `FinalElecCode2030` technology category.
"""
            st.markdown(investment_response)
            st.session_state.messages.append({"role": "assistant", "content": investment_response})

        elif is_connection_query and not is_province_query:
            hh = metrics["estimated_household_connections_by_technology"]

            connections_response = f"""### National Estimated Household Connections

#### Total Estimated Household Connections
* **Total Estimated Household Connections by 2030:** {metrics['estimated_household_connections']:,} households

#### Estimated Household Connections by Milestone Year
* **2025 Step:** {metrics['estimated_household_connections_by_year']['2025']:,} households
* **2030 Step:** {metrics['estimated_household_connections_by_year']['2030']:,} households

#### Estimated Household Connections by Technology
* **Grid Densification:** {hh['grid_densification']:,} households
* **Grid Extension:** {hh['grid_extension']:,} households
* **Mini-Grid Infrastructure:** {hh['mini_grid']:,} households
* **Standalone Solar Systems (SHS):** {hh['standalone_solar']:,} households

#### Analytical Note
This result summarizes modelled household-connection outputs from the active scenario. It does not prescribe implementation decisions.

#### Methodology
Person-level new connections are calculated using:

`(NewConnections2025 * ElecStatusIn2025) + NewConnections2030`

Year-specific household connections are calculated as:

`(NewConnections2025 * ElecStatusIn2025) / NumPeoplePerHH`

`NewConnections2030 / NumPeoplePerHH`

Total estimated household connections are calculated using:

`Person-level new connections / NumPeoplePerHH`

The resulting household values are grouped by `FinalElecCode2030` technology category.
"""
            st.markdown(connections_response)
            st.session_state.messages.append({"role": "assistant", "content": connections_response})

        elif is_province_query:
            if province_match is None:
                available_provinces = sorted(df["Admin1"].dropna().astype(str).unique().tolist())
                province_response = f"""### Province-Level Query Needs a Recognized Province

I detected a province-level question, but I could not match the province name to the active scenario file.

Please ask using one of the available `Admin1` province names, for example:

{", ".join(available_provinces[:12])}
"""
                st.markdown(province_response)
                st.session_state.messages.append({"role": "assistant", "content": province_response})

            else:
                province_metrics = calculate_province_summary(df, province_match)

                if province_metrics is None:
                    province_response = f"""### Province Not Found

I could not find `{province_match}` in the active scenario file's `Admin1` column.
"""
                    st.markdown(province_response)
                    st.session_state.messages.append({"role": "assistant", "content": province_response})

                else:
                    pop = province_metrics["population_summary"]
                    cap = province_metrics["capacity_by_technology_kw"]
                    mg = province_metrics["mini_grid_summary"]
                    hh = province_metrics["estimated_household_connections_by_technology"]

                    province_response = f"""### Province Summary: {province_metrics['province_name']}

#### Settlement Coverage
* **Settlement Clusters in Province:** {province_metrics['settlement_cluster_count']:,}

#### Technology-Disaggregated Capital Requirements
* **Grid Densification Portfolio:** USD {province_metrics['grid_densification_investment_usd']:,.2f}
* **Grid Extension Portfolio:** USD {province_metrics['grid_extension_investment_usd']:,.2f}
* **Mini-Grid Infrastructure:** USD {province_metrics['mini_grid_investment_usd']:,.2f}
* **Standalone Solar Systems (SHS):** USD {province_metrics['standalone_solar_investment_usd']:,.2f}

#### Estimated Household Connections
* **Total Estimated Household Connections:** {province_metrics['estimated_household_connections']:,} households
* **Grid Densification:** {hh['grid_densification']:,} households
* **Grid Extension:** {hh['grid_extension']:,} households
* **Mini-Grid Infrastructure:** {hh['mini_grid']:,} households
* **Standalone Solar Systems (SHS):** {hh['standalone_solar']:,} households

#### Population Summary
* **Base-Year Population:** {pop['base_population']:,} people
* **2030 Population:** {pop['target_population_2030']:,} people
* **Currently Unelectrified Population:** {pop['unelectrified_population_start']:,} people
* **Currently Unelectrified Population Within 10 km of Existing MV Lines:** {pop['unelectrified_within_10km_mv']:,} people

#### Capacity by Technology
* **Total New Capacity:** {format_capacity(province_metrics['total_new_capacity_kw'])}
* **Grid Densification:** {format_capacity(cap['grid_densification'])}
* **Grid Extension:** {format_capacity(cap['grid_extension'])}
* **Mini-Grid Infrastructure:** {format_capacity(cap['mini_grid'])}
* **Standalone Solar Systems (SHS):** {format_capacity(cap['standalone_solar'])}

#### Mini-Grid Settlement-Cluster Count
* **Mini-Grid Settlement-Cluster Count:** {mg['mini_grid_cluster_count']:,}
* **Average Capacity per Mini-Grid Cluster:** {format_capacity(mg['average_mini_grid_capacity_kw'])}
* **Average Estimated Households per Mini-Grid Cluster:** {mg['average_mini_grid_households']:,} households

#### Methodology
This province summary filters the processed scenario file where:

`Admin1 == "{province_metrics['province_name']}"`

Then it reuses the same deterministic calculation engine used for the national outputs.
"""
                    st.markdown(province_response)
                    st.session_state.messages.append({"role": "assistant", "content": province_response})

        elif is_population_query:
            pop = metrics["population_summary"]

            if is_near_grid_population_query:
                population_response = f"""### Near-Grid Unelectrified Population

* **Currently Unelectrified Population Within 10 km of Existing MV Lines:** {pop['unelectrified_within_10km_mv']:,} people
* **Total Currently Unelectrified Population:** {pop['unelectrified_population_start']:,} people

#### Methodology
Currently unelectrified population is calculated first as:

`PopStartYear - ElecPopCalib`

The near-grid subset is then calculated by filtering settlement clusters where:

`CurrentMVLineDist <= 10`
"""
            elif is_current_unelectrified_query:
                population_response = f"""### Currently Unelectrified Population

* **Currently Unelectrified Population:** {pop['unelectrified_population_start']:,} people
* **Currently Unelectrified Population Within 10 km of Existing MV Lines:** {pop['unelectrified_within_10km_mv']:,} people

#### Methodology
Currently unelectrified population is calculated as:

`PopStartYear - ElecPopCalib`

This accounts for settlements that may be partially electrified at the start of the analysis.
"""
            else:
                population_response = f"""### National Population Summary

#### Base-Year and Target-Year Population
* **Base-Year Population:** {pop['base_population']:,} people
* **2030 Population:** {pop['target_population_2030']:,} people

#### Current Unelectrified Population
* **Currently Unelectrified Population:** {pop['unelectrified_population_start']:,} people
* **Currently Unelectrified Population Within 10 km of Existing MV Lines:** {pop['unelectrified_within_10km_mv']:,} people

#### Methodology
Currently unelectrified population is calculated as:

`PopStartYear - ElecPopCalib`

This accounts for settlements that may be partially electrified at the start of the analysis. The 10 km near-grid figure then filters the calculated unelectrified population using:

`CurrentMVLineDist <= 10`
"""
            st.markdown(population_response)
            st.session_state.messages.append({"role": "assistant", "content": population_response})

        elif is_capacity_query:
            cap = metrics["capacity_by_technology_kw"]

            capacity_response = f"""### National Capacity by Technology

#### Total New Capacity
* **Total New Capacity:** {format_capacity(metrics['total_new_capacity_kw'])}

#### Capacity by Technology
* **Grid Densification:** {format_capacity(cap['grid_densification'])}
* **Grid Extension:** {format_capacity(cap['grid_extension'])}
* **Mini-Grid Infrastructure:** {format_capacity(cap['mini_grid'])}
* **Standalone Solar Systems (SHS):** {format_capacity(cap['standalone_solar'])}

#### Methodology
Capacity is calculated using the validated time-step formula:

`(NewCapacity2025 * ElecStatusIn2025) + NewCapacity2030`

The resulting capacity values are then grouped by `FinalElecCode2030` technology category.
"""
            st.markdown(capacity_response)
            st.session_state.messages.append({"role": "assistant", "content": capacity_response})

        elif is_mini_grid_count_query:
            mg = metrics["mini_grid_summary"]

            minigrid_response = f"""### Mini-Grid Settlement-Cluster Count

#### National Mini-Grid Count
* **Mini-Grid Settlement-Cluster Count:** {mg['mini_grid_cluster_count']:,}

#### Average Mini-Grid Cluster Characteristics
* **Average Capacity per Mini-Grid Cluster:** {format_capacity(mg['average_mini_grid_capacity_kw'])}
* **Average Estimated Households per Mini-Grid Cluster:** {mg['average_mini_grid_households']:,} households

#### Methodology
Mini-grid count is calculated by counting settlement clusters where:

`FinalElecCode2030 in [5, 6, 7]`

This follows the current interpretation that each settlement cluster assigned to a mini-grid technology is counted as one mini-grid cluster. This should not be overinterpreted as a final engineered project count, because nearby settlements could potentially be combined into one mini-grid through separate post-processing.
"""
            st.markdown(minigrid_response)
            st.session_state.messages.append({"role": "assistant", "content": minigrid_response})

        elif is_multi_scenario_query:
            scenario_response = """### Multi-Scenario Comparison Not Yet Enabled

This version is currently locked to one active Mozambique electrification scenario: `mz-3-0_0_0_0_0_0`.

Multi-scenario comparison is planned for a later version after deterministic formulas are validated across scenario files. The current version can answer national investment, estimated household-connection, population-summary, capacity, and mini-grid-count questions for the active scenario only.
"""
            st.markdown(scenario_response)
            st.session_state.messages.append({"role": "assistant", "content": scenario_response})

        elif is_grid_line_query:
            grid_line_response = """### Grid-Line Length Query Not Yet Enabled

Grid-line length outputs are not enabled in this version.

The next implementation step is to confirm whether to use `NewGridExtensionDist2025 + NewGridExtensionDist2030`, or more detailed fields such as `MV_km`, `LV_km`, and `HV_km` by time step.

The current version supports national-level investment, estimated household-connection, population-summary, capacity, and mini-grid-count outputs.
"""
            st.markdown(grid_line_response)
            st.session_state.messages.append({"role": "assistant", "content": grid_line_response})

        else:
            result_context = {
                "scenario": active_scenario_code,
                "scope": "national",
                "calculation_type": "investment_connections_population_capacity_minigrid_count_and_admin1_province_summary",
                "columns_used": [
                    "FinalElecCode2030",
                    "InvestmentCost2025",
                    "InvestmentCost2030",
                    "ElecStatusIn2025",
                    "NewConnections2025",
                    "NewConnections2030",
                    "NumPeoplePerHH",
                    "PopStartYear",
                    "Pop2030",
                    "ElecPopCalib",
                    "CurrentMVLineDist",
                    "NewCapacity2025",
                    "NewCapacity2030",
                    "Admin1"
                ],
                "formulas": {
                    "investment_usd": "(InvestmentCost2025 * ElecStatusIn2025) + InvestmentCost2030",
                    "individual_connections": "(NewConnections2025 * ElecStatusIn2025) + NewConnections2030",
                    "estimated_household_connections": "individual_connections / NumPeoplePerHH",
                    "estimated_household_connections_by_technology": "Group estimated household connections by FinalElecCode2030 technology category",
                    "unelectrified_population_start": "PopStartYear - ElecPopCalib",
                    "unelectrified_within_10km_mv": "Filter unelectrified population where CurrentMVLineDist <= 10",
                    "new_capacity_kw": "(NewCapacity2025 * ElecStatusIn2025) + NewCapacity2030",
                    "capacity_by_technology": "Group Total_New_Capacity_kW by FinalElecCode2030 technology category",
                    "mini_grid_count": "Count settlement clusters where FinalElecCode2030 is in [5, 6, 7]"
                },
                "results": {
                    "grid_densification_investment_usd": metrics["grid_densification_investment_usd"],
                    "grid_extension_investment_usd": metrics["grid_extension_investment_usd"],
                    "mini_grid_investment_usd": metrics["mini_grid_investment_usd"],
                    "standalone_solar_investment_usd": metrics["standalone_solar_investment_usd"],
                    "estimated_household_connections": metrics["estimated_household_connections"],
                    "estimated_household_connections_by_year": metrics["estimated_household_connections_by_year"],
                    "estimated_household_connections_by_technology": metrics["estimated_household_connections_by_technology"],
                    "population_summary": metrics["population_summary"],
                    "capacity_by_technology_kw": metrics["capacity_by_technology_kw"],
                    "total_new_capacity_kw": metrics["total_new_capacity_kw"],
                    "mini_grid_summary": metrics["mini_grid_summary"],
                    "dominant_technology_by_capex": metrics["dominant_technology_by_capex"]
                }
            }

            final = client.beta.chat.completions.parse(
                model="gpt-5.4-mini",
                messages=[
                    {"role": "system", "content": system_instruction},
                    {
                        "role": "system",
                        "content": f"DETERMINISTIC CONTEXT OBJECT: {json.dumps(result_context)}"
                    },
                    {
                        "role": "system",
                        "content": f"""HARD QUANTITATIVE CONSTRAINTS:
- Absolute Grid Densification Investment: {metrics['grid_densification_investment_usd']:,.2f} USD
- Absolute Grid Extension Investment: {metrics['grid_extension_investment_usd']:,.2f} USD
- Absolute Mini-Grid Investment: {metrics['mini_grid_investment_usd']:,.2f} USD
- Absolute Standalone Solar Investment: {metrics['standalone_solar_investment_usd']:,.2f} USD
- Estimated Household Connections: {metrics['estimated_household_connections']:,} households
- Estimated Household Connections by Year: {json.dumps(metrics['estimated_household_connections_by_year'])}
- Estimated Household Connections by Technology: {json.dumps(metrics['estimated_household_connections_by_technology'])}
- Population Summary: {json.dumps(metrics['population_summary'])}
- Capacity by Technology in kW: {json.dumps(metrics['capacity_by_technology_kw'])}
- Total New Capacity in kW: {metrics['total_new_capacity_kw']:,.2f}
- Mini-Grid Summary: {json.dumps(metrics['mini_grid_summary'])}
- Dominant Capital Cost Technology: {metrics['dominant_technology_by_capex']}.

Your written text analysis and narrative descriptions MUST align strictly with this object profile. Do not restate formulas or structural definitions. Focus on explaining the modelled values without prescribing policy actions."""
                    },
                    {"role": "user", "content": user_query}
                ],
                response_format=OnSSETNarrative
            )

            structured_data = final.choices[0].message.parsed

            clean_summary = structured_data.executive_summary.replace("`", "").replace("−", "-")
            clean_observation = structured_data.scenario_observation.replace("`", "").replace("−", "-")

            answer = f"""### 📋 National Scenario Output
{clean_summary}

#### ⚡ Technology-Disaggregated Capital Requirements (CAPEX)
* **Grid Densification Portfolio:** USD {metrics['grid_densification_investment_usd']:,.2f}
* **Grid Extension Portfolio:** USD {metrics['grid_extension_investment_usd']:,.2f}
* **Mini-Grid Infrastructure:** USD {metrics['mini_grid_investment_usd']:,.2f}
* **Standalone Solar Systems (SHS):** USD {metrics['standalone_solar_investment_usd']:,.2f}

#### 📊 Macro Scalability Metrics
* **Estimated Household Connections (2030):** {metrics['estimated_household_connections']:,} households
* **2025 Step Household Connections:** {metrics['estimated_household_connections_by_year']['2025']:,} households
* **2030 Step Household Connections:** {metrics['estimated_household_connections_by_year']['2030']:,} households

#### 🏠 Estimated Household Connections by Technology
* **Grid Densification:** {metrics['estimated_household_connections_by_technology']['grid_densification']:,} households
* **Grid Extension:** {metrics['estimated_household_connections_by_technology']['grid_extension']:,} households
* **Mini-Grid Infrastructure:** {metrics['estimated_household_connections_by_technology']['mini_grid']:,} households
* **Standalone Solar Systems (SHS):** {metrics['estimated_household_connections_by_technology']['standalone_solar']:,} households

#### 👥 Population Summary
* **Base-Year Population:** {metrics['population_summary']['base_population']:,} people
* **2030 Population:** {metrics['population_summary']['target_population_2030']:,} people
* **Currently Unelectrified Population:** {metrics['population_summary']['unelectrified_population_start']:,} people
* **Currently Unelectrified Population Within 10 km of Existing MV Lines:** {metrics['population_summary']['unelectrified_within_10km_mv']:,} people

#### 🔋 Capacity by Technology
* **Total New Capacity:** {format_capacity(metrics['total_new_capacity_kw'])}
* **Grid Densification:** {format_capacity(metrics['capacity_by_technology_kw']['grid_densification'])}
* **Grid Extension:** {format_capacity(metrics['capacity_by_technology_kw']['grid_extension'])}
* **Mini-Grid Infrastructure:** {format_capacity(metrics['capacity_by_technology_kw']['mini_grid'])}
* **Standalone Solar Systems (SHS):** {format_capacity(metrics['capacity_by_technology_kw']['standalone_solar'])}

#### 🧩 Mini-Grid Count
* **Mini-Grid Settlement-Cluster Count:** {metrics['mini_grid_summary']['mini_grid_cluster_count']:,}
* **Average Capacity per Mini-Grid Cluster:** {format_capacity(metrics['mini_grid_summary']['average_mini_grid_capacity_kw'])}
* **Average Estimated Households per Mini-Grid Cluster:** {metrics['mini_grid_summary']['average_mini_grid_households']:,} households

#### 🧭 Analytical Note
* {clean_observation}
* This result summarizes modelled outputs from the active scenario. It does not prescribe implementation decisions.
"""

            st.markdown(answer)
            st.session_state.messages.append({"role": "assistant", "content": answer})

            st.download_button(
                label="💾 Export National Scenario Portfolio (CSV)",
                data=convert_df(df),
                file_name=f"{active_scenario_code}_national_export.csv",
                mime="text/csv"
            )