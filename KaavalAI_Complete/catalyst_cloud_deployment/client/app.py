"""
KaavalAI - AI-Driven Crime Analytics & Visualization Platform (v2)
Rewired to read from the official Karnataka Police ER-schema tables and
analytics_engine_v2.py outputs.

Run with: streamlit run app.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import networkx as nx
from pyvis.network import Network
import streamlit.components.v1 as components
import requests
import os

st.set_page_config(page_title="KaavalAI - Crime Intelligence Platform", layout="wide", page_icon="🛡️")

DATA_DIR = os.environ.get("KAAVALAI_DATA_DIR", "/mnt/user-data/outputs")

# ---------------------------------------------------------
# Data loading (cached)
# ---------------------------------------------------------
@st.cache_data
def load_data():
    cases = pd.read_csv(f"{DATA_DIR}/CaseMaster_enriched.csv",
                         parse_dates=["CrimeRegisteredDate", "IncidentFromDate", "IncidentToDate"])
    accused = pd.read_csv(f"{DATA_DIR}/Accused.csv")
    victim = pd.read_csv(f"{DATA_DIR}/Victim.csv")
    arrest = pd.read_csv(f"{DATA_DIR}/ArrestSurrender.csv")
    chargesheet = pd.read_csv(f"{DATA_DIR}/ChargesheetDetails.csv")
    hotspots = pd.read_csv(f"{DATA_DIR}/hotspots.csv")
    trends = pd.read_csv(f"{DATA_DIR}/emerging_trends.csv")
    centrality = pd.read_csv(f"{DATA_DIR}/network_centrality.csv")
    groups = pd.read_csv(f"{DATA_DIR}/organized_crime_groups.csv")
    risk = pd.read_csv(f"{DATA_DIR}/risk_scores.csv")
    return cases, accused, victim, arrest, chargesheet, hotspots, trends, centrality, groups, risk

cases, accused, victim, arrest, chargesheet, hotspots, trends, centrality, groups, risk = load_data()

# ---------------------------------------------------------
# Sidebar - filters + branding
# ---------------------------------------------------------
st.sidebar.title("🛡️ KaavalAI")
st.sidebar.caption("Crime Intelligence & Analytics Platform | Datathon 2026")

districts = sorted(cases["district"].dropna().unique())
crime_types = sorted(cases["crime_type"].dropna().unique())

sel_districts = st.sidebar.multiselect("District", districts, default=districts)
sel_crime_types = st.sidebar.multiselect("Crime Type (Major Head)", crime_types, default=crime_types)
date_range = st.sidebar.date_input(
    "Date range",
    value=(cases["CrimeRegisteredDate"].min().date(), cases["CrimeRegisteredDate"].max().date()),
)

filtered = cases[cases["district"].isin(sel_districts) & cases["crime_type"].isin(sel_crime_types)]
if len(date_range) == 2:
    filtered = filtered[
        (filtered["CrimeRegisteredDate"].dt.date >= date_range[0])
        & (filtered["CrimeRegisteredDate"].dt.date <= date_range[1])
    ]

st.sidebar.markdown("---")

# --- Real login via Catalyst Authentication function (replaces role mock) ---
AUTH_FUNCTION_URL = os.environ.get(
    "KAAVALAI_AUTH_URL",
    "https://your-project.zohocatalystdevapi.com/server/auth_login/execute"
)

if "auth" not in st.session_state:
    st.session_state.auth = None

if st.session_state.auth is None:
    with st.sidebar.form("login_form"):
        st.caption("Sign in with your KSP credentials")
        kgid_input = st.text_input("KGID")
        pin_input = st.text_input("PIN", type="password")
        submitted = st.form_submit_button("Sign in")
    if submitted:
        try:
            resp = requests.post(AUTH_FUNCTION_URL, json={"kgid": kgid_input, "pin": pin_input}, timeout=10)
            data = resp.json()
            if data.get("status") == "success":
                st.session_state.auth = data
                st.rerun()
            else:
                st.sidebar.error(f"Login failed: {data.get('reason', 'unknown error')}")
        except Exception as e:
            st.sidebar.error(f"Could not reach Authentication service: {e}")
    st.sidebar.caption("Not signed in — showing read-only demo view below.")
    role = "Analyst"  # safe default view while unauthenticated
else:
    role = st.session_state.auth["role"]
    st.sidebar.success(f"Signed in as {st.session_state.auth['employee_name']} ({role})")
    if st.sidebar.button("Sign out"):
        st.session_state.auth = None
        st.rerun()

st.sidebar.caption(f"Access level: {role} — Data Store table permissions enforce this per-role, "
                    f"not just this UI. Audit trail active ✅")

# ---------------------------------------------------------
# Header
# ---------------------------------------------------------
st.title("KaavalAI — AI-Driven Crime Analytics & Visualization Platform")
st.caption("Karnataka State Police | Datathon 2026 | Prototype on ER-schema-aligned synthetic data")

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Total FIRs (CaseMaster)", f"{len(filtered):,}")
k2.metric("Districts Covered", filtered["district"].nunique())
k3.metric("Active Hotspots", hotspots["hotspot_cluster"].nunique() if len(hotspots) else 0)
k4.metric("Organized Crime Groups", len(groups))
k5.metric("Red-Alert Trends", int((trends["alert_level"] == "Red Alert").sum()))

tabs = st.tabs([
    "🗺️ Hotspot Map", "🕸️ Criminal Network", "📈 Trends & Alerts",
    "🎯 Risk Forecast", "💬 Ask KaavalAI (NL Query)"
])

# ---------------------------------------------------------
# TAB 1: Hotspot Map
# ---------------------------------------------------------
with tabs[0]:
    st.subheader("Spatiotemporal Crime Hotspots")
    st.caption("DBSCAN clustering on FIR coordinates, grouped by district + crime major-head. "
               "Circle size = incident density.")

    map_fig = px.scatter_mapbox(
        filtered, lat="latitude", lon="longitude", color="crime_type",
        hover_data=["district", "crime_subtype", "CrimeRegisteredDate", "case_status", "gravity"],
        zoom=5.5, height=550, opacity=0.6,
    )
    map_fig.update_layout(mapbox_style="carto-positron", margin=dict(l=0, r=0, t=0, b=0))
    st.plotly_chart(map_fig, use_container_width=True)

    st.subheader("Top Hotspot Clusters")
    top_hotspots = hotspots[hotspots["district"].isin(sel_districts)].sort_values(
        "incident_count", ascending=False
    ).head(10)
    st.dataframe(top_hotspots, use_container_width=True, hide_index=True)

    st.subheader("District Drill-down: FIR Volume")
    district_counts = filtered.groupby("district").size().reset_index(name="fir_count").sort_values(
        "fir_count", ascending=False
    )
    bar_fig = px.bar(district_counts, x="district", y="fir_count", color="fir_count",
                      color_continuous_scale="Reds")
    st.plotly_chart(bar_fig, use_container_width=True)

# ---------------------------------------------------------
# TAB 2: Criminal Network
# ---------------------------------------------------------
with tabs[1]:
    st.subheader("Criminal Network & Organized Crime Group Detection")
    st.caption("Nodes = persons (resolved across cases via identity matching — in production this "
               "uses Zia-based fuzzy matching on name/age/biometrics, since AccusedMasterID in the "
               "real schema is scoped per-case, not per-person). Edges = co-accused on same CaseMasterID.")

    if len(groups):
        top_groups = groups.sort_values("members", ascending=False).head(8)
        sel_group = st.selectbox("Select a detected network to visualize",
                                  top_groups["group_id"].tolist())

        group_row = groups[groups["group_id"] == sel_group].iloc[0]
        member_ids = [int(x) for x in group_row["member_ids"].split(",")]

        sub_accused_full = accused[accused["_pool_id"].isin(member_ids)]
        G_full = nx.Graph()
        for case_id, grp in sub_accused_full.groupby("CaseMasterID"):
            members = grp["_pool_id"].unique().tolist()
            for i in range(len(members)):
                for j in range(i + 1, len(members)):
                    G_full.add_edge(members[i], members[j])

        # For large groups, cap the visual to a connected neighborhood (BFS from the
        # most-central node) rather than an arbitrary member slice — guarantees the
        # displayed nodes actually have edges to each other.
        MAX_DISPLAY_NODES = 40
        if G_full.number_of_nodes() > MAX_DISPLAY_NODES:
            cent_in_group = centrality[centrality["person_id"].isin(member_ids)].sort_values(
                "betweenness_centrality", ascending=False
            )
            seed_node = int(cent_in_group.iloc[0]["person_id"]) if len(cent_in_group) else member_ids[0]
            bfs_nodes = list(nx.bfs_tree(G_full, source=seed_node, depth_limit=3).nodes())[:MAX_DISPLAY_NODES]
            G_sub = G_full.subgraph(bfs_nodes).copy()
            st.caption(f"Showing a {len(bfs_nodes)}-node neighborhood around the most central figure "
                       f"(full network has {G_full.number_of_nodes()} members).")
        else:
            G_sub = G_full

        net = Network(height="500px", width="100%", bgcolor="#ffffff", font_color="#222")
        cent_lookup = centrality.set_index("person_id")["betweenness_centrality"].to_dict()
        name_lookup = centrality.set_index("person_id")["display_name"].to_dict()
        case_count_lookup = centrality.set_index("person_id")["case_count"].to_dict()
        for node in G_sub.nodes():
            case_count = int(case_count_lookup.get(node, 0))
            size = 15 + cent_lookup.get(node, 0) * 500
            net.add_node(node, label=name_lookup.get(node, str(node)), size=max(size, 15),
                         title=f"{name_lookup.get(node, node)} | Linked cases: {case_count}",
                         color="#c0392b" if case_count >= 3 else "#e67e22")
        for u, v in G_sub.edges():
            net.add_edge(u, v)

        net.repulsion(node_distance=150, spring_length=200)
        net.save_graph("./network.html")
        with open("./network.html", "r", encoding="utf-8") as f:
            components.html(f.read(), height=520)

        st.subheader("Key Figures (Network Centrality)")
        key_figures = centrality[centrality["person_id"].isin(member_ids)].sort_values(
            "betweenness_centrality", ascending=False
        ).head(5)
        st.dataframe(
            key_figures[["display_name", "case_count", "degree_centrality", "betweenness_centrality"]],
            use_container_width=True, hide_index=True
        )

        st.subheader("All Detected Organized Crime Groups")
        st.dataframe(top_groups[["group_id", "members"]], use_container_width=True, hide_index=True)
    else:
        st.info("No organized crime groups (size ≥ 4) detected in the current filtered dataset.")

# ---------------------------------------------------------
# TAB 3: Trends & Alerts
# ---------------------------------------------------------
with tabs[2]:
    st.subheader("Emerging Crime Trend Alerts")
    st.caption("Recent 3-month FIR rate vs 12-month baseline, per district & crime major-head.")

    alert_colors = {"Red Alert": "🔴", "Elevated": "🟠", "Watch": "🟡", "Stable": "🟢"}
    trends_display = trends.copy()
    trends_display["alert"] = trends_display["alert_level"].map(alert_colors) + " " + trends_display["alert_level"].astype(str)
    st.dataframe(
        trends_display[["district", "crime_type", "recent_monthly_rate", "baseline_monthly_rate", "pct_change", "alert"]]
        .sort_values("pct_change", ascending=False).head(20),
        use_container_width=True, hide_index=True
    )

    st.subheader("Monthly Trend by Crime Type")
    ts = filtered.copy()
    ts["month"] = ts["CrimeRegisteredDate"].dt.to_period("M").astype(str)
    ts_agg = ts.groupby(["month", "crime_type"]).size().reset_index(name="count")
    line_fig = px.line(ts_agg, x="month", y="count", color="crime_type", markers=True)
    st.plotly_chart(line_fig, use_container_width=True)

    st.subheader("Case Disposition — Investigation Outcomes")
    c1, c2 = st.columns(2)
    with c1:
        status_counts = filtered["case_status"].value_counts().reset_index()
        status_counts.columns = ["case_status", "count"]
        status_fig = px.pie(status_counts, names="case_status", values="count",
                             title="Case Status Distribution")
        st.plotly_chart(status_fig, use_container_width=True)
    with c2:
        cs_type_map = {"A": "Chargesheet Filed", "B": "False Case", "C": "Undetected"}
        cs = chargesheet.copy()
        cs["outcome"] = cs["cstype"].map(cs_type_map)
        cs_fig = px.pie(cs["outcome"].value_counts().reset_index(name="count"), names="outcome",
                         values="count", title="Chargesheet Final Report Type")
        st.plotly_chart(cs_fig, use_container_width=True)

    st.subheader("Arrest & Surrender Activity")
    arrest_type_map = {1: "Arrest", 2: "Voluntary Surrender"}
    arrest_display = arrest.copy()
    arrest_display["type"] = arrest_display["ArrestSurrenderTypeID"].map(arrest_type_map)
    at_counts = arrest_display["type"].value_counts().reset_index()
    at_counts.columns = ["type", "count"]
    st.dataframe(at_counts, use_container_width=True, hide_index=True)

# ---------------------------------------------------------
# TAB 4: Risk Forecast
# ---------------------------------------------------------
with tabs[3]:
    st.subheader("Predictive Risk Scoring (Explainable AI)")
    st.caption("RandomForest model forecasting next-month FIR volume per district. "
               "Feature importances shown for transparency & audit compliance.")

    latest_risk = risk.sort_values("year_month").groupby("district").tail(1).sort_values(
        "risk_score_0_100", ascending=False
    )
    risk_fig = px.bar(latest_risk, x="district", y="risk_score_0_100", color="risk_score_0_100",
                       color_continuous_scale="OrRd", labels={"risk_score_0_100": "Risk Score (0-100)"})
    st.plotly_chart(risk_fig, use_container_width=True)

    st.subheader("Model Explainability — Feature Importance")
    importance_data = pd.DataFrame({
        "feature": ["incident_count", "heinous_ratio", "night_incident_ratio", "undetected_ratio", "month_num"],
        "importance": [0.645, 0.076, 0.071, 0.094, 0.114]  # from analytics_engine_v2.py output
    })
    imp_fig = px.bar(importance_data, x="importance", y="feature", orientation="h",
                      color="importance", color_continuous_scale="Blues")
    st.plotly_chart(imp_fig, use_container_width=True)
    st.info("Audit trail: every risk score is traceable to the underlying district-month "
            "feature values shown above — supports investigator accountability requirements.")

# ---------------------------------------------------------
# TAB 5: NL Query (prototype)
# ---------------------------------------------------------
with tabs[4]:
    st.subheader("💬 Ask KaavalAI")
    st.caption("Powered by Catalyst QuickML (Qwen 2.5-14B-Instruct) — translates your question into "
               "a database query, runs it, and answers in plain language. Falls back to a local "
               "keyword search if the QuickML function isn't reachable.")

    NL_QUERY_FUNCTION_URL = os.environ.get(
        "KAAVALAI_NL_QUERY_URL",
        "https://your-project.zohocatalystdevapi.com/server/nl_query/execute"
    )

    query = st.text_input("Ask a question about crime data",
                           placeholder="e.g. How many theft cases were registered in Mysuru this year?")

    def handle_query_quickml(q):
        resp = requests.post(NL_QUERY_FUNCTION_URL, json={"question": q}, timeout=20)
        data = resp.json()
        if data.get("status") != "success":
            raise RuntimeError(data.get("reason", "unknown error"))
        return data

    def handle_query_fallback(q):
        """Local keyword-match fallback, used only if QuickML is unreachable."""
        q_lower = q.lower()
        matched_district = next((d for d in districts if d.lower() in q_lower), None)
        matched_crime = next((c for c in crime_types if c.lower() in q_lower), None)
        result = cases.copy()
        if matched_district:
            result = result[result["district"] == matched_district]
        if matched_crime:
            result = result[result["crime_type"] == matched_crime]
        summary = f"Found **{len(result)}** FIRs"
        if matched_crime:
            summary += f" of type **{matched_crime}**"
        if matched_district:
            summary += f" in **{matched_district}**"
        return summary, result.head(20)

    if query:
        try:
            data = handle_query_quickml(query)
            st.success(data["answer"])
            st.caption(f"Generated query ({data['row_count']} rows): `{data['generated_zcql']}`")
            if data["rows"]:
                st.dataframe(pd.DataFrame(data["rows"]), use_container_width=True, hide_index=True)
        except Exception as e:
            st.warning(f"QuickML function unreachable ({e}) — showing local keyword-search fallback instead.")
            summary, result = handle_query_fallback(query)
            st.info(summary)
            st.dataframe(
                result[["CrimeNo", "CaseNo", "district", "crime_type", "crime_subtype",
                         "CrimeRegisteredDate", "case_status", "gravity"]],
                use_container_width=True, hide_index=True
            )
            if len(result):
                st.plotly_chart(
                    px.scatter_mapbox(result, lat="latitude", lon="longitude", zoom=6, height=350,
                                       color="crime_type").update_layout(
                        mapbox_style="carto-positron", margin=dict(l=0, r=0, t=0, b=0)),
                    use_container_width=True
                )

    st.markdown("---")
    st.caption("📄 Export: conversation history export to PDF available via Catalyst SmartBrowz in production.")
