"""
KaavalAI - AI-Driven Crime Analytics & Visualization Platform (Flask edition)

Rebuilt on Flask after confirming Streamlit's WebSocket-dependent reactive
UI doesn't render correctly behind Catalyst AppSail's reverse proxy. Flask
is Zoho's own confirmed-working AppSail pattern (plain HTTP request/response,
no persistent connection needed) — every chart here is rendered as
self-contained interactive HTML (Plotly's to_html), and filtering works via
standard GET query parameters + full page reloads, so there's no dependency
on WebSockets anywhere in this app.
"""

import sys
import os
import re
# Tell Python to look inside the vendor folder for numpy, pandas, etc.
vendor_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor")
if vendor_path not in sys.path:
    sys.path.insert(0, vendor_path)

import json
from flask import Flask, request, render_template
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import networkx as nx

app = Flask(__name__)

DATA_DIR = os.environ.get("KAAVALAI_DATA_DIR", "./data")

# ---------------------------------------------------------
# Load all data once at startup
# ---------------------------------------------------------
def load_all_data():
    cases = pd.read_csv(f"{DATA_DIR}/CaseMaster_enriched.csv",
                         parse_dates=["CrimeRegisteredDate", "IncidentFromDate", "IncidentToDate"])
    accused = pd.read_csv(f"{DATA_DIR}/Accused.csv")
    arrest = pd.read_csv(f"{DATA_DIR}/ArrestSurrender.csv")
    chargesheet = pd.read_csv(f"{DATA_DIR}/ChargesheetDetails.csv")
    hotspots = pd.read_csv(f"{DATA_DIR}/hotspots.csv")
    trends = pd.read_csv(f"{DATA_DIR}/emerging_trends.csv")
    centrality = pd.read_csv(f"{DATA_DIR}/network_centrality.csv")
    groups = pd.read_csv(f"{DATA_DIR}/organized_crime_groups.csv")
    risk = pd.read_csv(f"{DATA_DIR}/risk_scores.csv")
    return cases, accused, arrest, chargesheet, hotspots, trends, centrality, groups, risk

CASES, ACCUSED, ARREST, CHARGESHEET, HOTSPOTS, TRENDS, CENTRALITY, GROUPS, RISK = load_all_data()

DISTRICTS = sorted(CASES["district"].dropna().unique().tolist())
CRIME_TYPES = sorted(CASES["crime_type"].dropna().unique().tolist())

PLOTLY_TEMPLATE = "plotly_dark"
BRAND_COLORS = ["#C9A227", "#4C8DAE", "#C0392B", "#6B8F71", "#8E6C9E", "#D98E4A"]


def fig_to_div(fig, height=420):
    fig.update_layout(
        template=PLOTLY_TEMPLATE,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="IBM Plex Sans, sans-serif", color="#EDEFF2"),
        margin=dict(l=10, r=10, t=40, b=10),
        height=height,
    )
    return fig.to_html(include_plotlyjs="cdn", full_html=False, config={"displaylogo": False})


# ---------------------------------------------------------
# Chart builders
# ---------------------------------------------------------
def build_hotspot_map(filtered):
    fig = px.scatter_mapbox(
        filtered, lat="latitude", lon="longitude", color="crime_type",
        hover_data=["district", "crime_subtype", "case_status"],
        zoom=5.3, opacity=0.65, color_discrete_sequence=BRAND_COLORS,
    )
    fig.update_layout(mapbox_style="carto-darkmatter")
    return fig_to_div(fig, height=480)


def build_district_bar(filtered):
    counts = filtered.groupby("district").size().reset_index(name="fir_count").sort_values("fir_count", ascending=False).head(15)
    fig = px.bar(counts, x="district", y="fir_count", color="fir_count", color_continuous_scale=["#1B3A5C", "#C9A227"])
    return fig_to_div(fig, height=360)


def build_network_graph(group_id):
    group_row = GROUPS[GROUPS["group_id"] == group_id].iloc[0]
    member_ids = [int(x) for x in group_row["member_ids"].split(",")]
    sub_accused = ACCUSED[ACCUSED["_pool_id"].isin(member_ids)]

    G = nx.Graph()
    for case_id, grp in sub_accused.groupby("CaseMasterID"):
        members = grp["_pool_id"].unique().tolist()
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                G.add_edge(members[i], members[j])

    if G.number_of_nodes() > 40:
        cent_in_group = CENTRALITY[CENTRALITY["person_id"].isin(member_ids)].sort_values("betweenness_centrality", ascending=False)
        seed = int(cent_in_group.iloc[0]["person_id"]) if len(cent_in_group) else member_ids[0]
        keep = list(nx.bfs_tree(G, source=seed, depth_limit=3).nodes())[:40]
        G = G.subgraph(keep).copy()

    pos = nx.spring_layout(G, seed=42, k=0.6)
    name_lookup = CENTRALITY.set_index("person_id")["display_name"].to_dict()
    case_count_lookup = CENTRALITY.set_index("person_id")["case_count"].to_dict()

    edge_x, edge_y = [], []
    for u, v in G.edges():
        edge_x += [pos[u][0], pos[v][0], None]
        edge_y += [pos[u][1], pos[v][1], None]
    edge_trace = go.Scatter(x=edge_x, y=edge_y, mode="lines", line=dict(width=1, color="#4A5A6A"), hoverinfo="none")

    node_x = [pos[n][0] for n in G.nodes()]
    node_y = [pos[n][1] for n in G.nodes()]
    node_color = ["#C0392B" if case_count_lookup.get(n, 0) >= 3 else "#C9A227" for n in G.nodes()]
    node_text = [f"{name_lookup.get(n, n)} — {int(case_count_lookup.get(n, 0))} linked cases" for n in G.nodes()]
    node_trace = go.Scatter(
        x=node_x, y=node_y, mode="markers", hoverinfo="text", text=node_text,
        marker=dict(size=16, color=node_color, line=dict(width=1.5, color="#0B1520")),
    )

    fig = go.Figure(data=[edge_trace, node_trace])
    fig.update_layout(showlegend=False, xaxis=dict(visible=False), yaxis=dict(visible=False))
    return fig_to_div(fig, height=480), G.number_of_nodes(), int(group_row["members"])


def build_trend_line(filtered):
    ts = filtered.copy()
    ts["month"] = ts["CrimeRegisteredDate"].dt.to_period("M").astype(str)
    ts_agg = ts.groupby(["month", "crime_type"]).size().reset_index(name="count")
    fig = px.line(ts_agg, x="month", y="count", color="crime_type", markers=True, color_discrete_sequence=BRAND_COLORS)
    return fig_to_div(fig, height=380)


def build_risk_bar():
    latest = RISK.sort_values("year_month").groupby("district").tail(1).sort_values("risk_score_0_100", ascending=False).head(15)
    fig = px.bar(latest, x="district", y="risk_score_0_100", color="risk_score_0_100",
                 color_continuous_scale=["#1B3A5C", "#C0392B"], labels={"risk_score_0_100": "Risk Score"})
    return fig_to_div(fig, height=380)


def build_feature_importance():
    data = pd.DataFrame({
        "feature": ["incident_count", "month_num", "undetected_ratio", "night_incident_ratio", "heinous_ratio"],
        "importance": [0.645, 0.114, 0.094, 0.071, 0.076],
    }).sort_values("importance")
    fig = px.bar(data, x="importance", y="feature", orientation="h", color_discrete_sequence=["#C9A227"])
    return fig_to_div(fig, height=300)


CRIME_TYPE_SYNONYMS = {
    "Crimes Against Body": ["violent", "violence", "murder", "assault", "killing", "homicide"],
    "Crimes Against Property": ["theft", "robbery", "burglary", "stolen", "steal", "property"],
    "Crimes Against Women": ["women", "woman", "dowry", "molestation"],
    "Cyber Crime": ["cyber", "online", "hacking", "internet", "phishing"],
    "Narcotics (NDPS)": ["drug", "drugs", "narcotic", "narcotics"],
    "Economic Offences": ["fraud", "economic", "financial", "scam", "cheating"],
}


def match_district(q_lower):
    """Matches on the district's first significant word (handles compound
    names like 'Bengaluru Urban'/'Bengaluru Rural' when the question just
    says 'Bengaluru'). Returns ALL matching districts, since a generic
    mention can legitimately match more than one."""
    matches = []
    for d in DISTRICTS:
        first_word = d.split()[0].lower().strip("()")
        if first_word in q_lower or d.lower() in q_lower:
            matches.append(d)
    return matches


def match_crime_types(q_lower):
    matches = [c for c in CRIME_TYPES if c.lower() in q_lower]
    for crime_type, synonyms in CRIME_TYPE_SYNONYMS.items():
        if crime_type not in matches and any(s in q_lower for s in synonyms):
            matches.append(crime_type)
    return matches


def handle_nl_query(question):
    q_lower = question.lower()
    matched_districts = match_district(q_lower)
    matched_crimes = match_crime_types(q_lower)

    # If the question explicitly names a place via "in <place>" but that
    # place isn't one of our districts, don't silently drop the location
    # constraint and show all-district results — the user specified
    # somewhere, just not somewhere we have data for.
    in_match = re.search(r"\bin\s+([a-zA-Z\s]+?)(?:$|[.,?!])", question)
    if in_match and not matched_districts:
        mentioned_place = in_match.group(1).strip()
        if mentioned_place and not any(w in q_lower for w in ["karnataka", "district", "state"]):
            return (f"No FIRs found — \"{mentioned_place}\" is not a recognized Karnataka district in this system.",
                    CASES.iloc[0:0])

    if not matched_districts and not matched_crimes:
        return f"No matching district or crime type recognized in \"{question}\" — 0 FIRs found.", CASES.iloc[0:0]

    result = CASES.copy()
    if matched_districts:
        result = result[result["district"].isin(matched_districts)]
    if matched_crimes:
        result = result[result["crime_type"].isin(matched_crimes)]

    summary = f"Found {len(result)} FIRs"
    if matched_crimes:
        summary += f" of type {' / '.join(matched_crimes)}"
    if matched_districts:
        summary += f" in {' / '.join(matched_districts)}"
    return summary, result.head(15)


# ---------------------------------------------------------
# Routes
# ---------------------------------------------------------
@app.route("/")
def dashboard():
    district_param = request.args.get("district", "")
    crime_type_param = request.args.get("crime_type", "")
    sel_districts = district_param.split(",") if district_param else DISTRICTS
    sel_crime_types = crime_type_param.split(",") if crime_type_param else CRIME_TYPES
    active_tab = request.args.get("tab", "map")

    filtered = CASES[CASES["district"].isin(sel_districts) & CASES["crime_type"].isin(sel_crime_types)]

    kpis = {
        "total_firs": len(filtered),
        "districts": filtered["district"].nunique(),
        "hotspots": HOTSPOTS["hotspot_cluster"].nunique() if len(HOTSPOTS) else 0,
        "networks": len(GROUPS),
        "red_alerts": int((TRENDS["alert_level"] == "Red Alert").sum()),
    }

    top_groups = GROUPS.sort_values("members", ascending=False).head(8).to_dict("records")
    sel_group = request.args.get("group_id", top_groups[0]["group_id"] if top_groups else None)

    network_div, shown_nodes, full_nodes = ("", 0, 0)
    if sel_group:
        network_div, shown_nodes, full_nodes = build_network_graph(sel_group)

    nl_question = request.args.get("question", "")
    nl_summary, nl_results = (None, None)
    if nl_question:
        nl_summary, nl_results = handle_nl_query(nl_question)

    alert_emoji = {"Red Alert": "🔴", "Elevated": "🟠", "Watch": "🟡", "Stable": "🟢"}
    trends_display = TRENDS.copy()
    trends_display["alert_display"] = trends_display["alert_level"].map(alert_emoji).fillna("") + " " + trends_display["alert_level"].astype(str)
    top_trends = trends_display.sort_values("pct_change", ascending=False).head(15).to_dict("records")

    return render_template(
        "dashboard.html",
        kpis=kpis,
        districts=DISTRICTS, crime_types=CRIME_TYPES,
        sel_districts=set(sel_districts), sel_crime_types=set(sel_crime_types),
        district_param=",".join(sel_districts), crime_type_param=",".join(sel_crime_types),
        active_tab=active_tab,
        map_div=build_hotspot_map(filtered) if active_tab == "map" else None,
        district_bar_div=build_district_bar(filtered) if active_tab == "map" else None,
        top_hotspots=HOTSPOTS.sort_values("incident_count", ascending=False).head(10).to_dict("records"),
        network_div=network_div, shown_nodes=shown_nodes, full_nodes=full_nodes,
        top_groups=top_groups, sel_group=sel_group,
        trend_line_div=build_trend_line(filtered) if active_tab == "trends" else None,
        top_trends=top_trends,
        risk_bar_div=build_risk_bar() if active_tab == "risk" else None,
        feature_importance_div=build_feature_importance() if active_tab == "risk" else None,
        nl_question=nl_question, nl_summary=nl_summary,
        nl_results=nl_results.to_dict("records") if nl_results is not None else None,
    )


if __name__ == "__main__":
    port = int(os.environ.get("X_ZOHO_CATALYST_LISTEN_PORT", 9000))
    app.run(host="0.0.0.0", port=port)
