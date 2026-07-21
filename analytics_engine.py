"""
KaavalAI - Core Analytics Engine (v2)
Rewired to read from the official Karnataka Police ER-schema tables
(CaseMaster, Accused, Victim, ComplainantDetails, ArrestSurrender, etc.)
instead of the earlier mock incidents/accused/links CSVs.

1. Spatiotemporal hotspot detection (DBSCAN) on CaseMaster lat/long
2. Criminal network analysis (NetworkX) on Accused, resolved via _pool_id
   (proxy for real-world entity resolution across name/age/biometrics —
   in production this would be a Zia-based identity matching step, since
   AccusedMasterID is unique PER CASE, not per person)
3. Predictive risk scoring (district-month) using CaseMaster + GravityOffence
"""

import pandas as pd
import numpy as np
import networkx as nx
from sklearn.cluster import DBSCAN
from sklearn.ensemble import RandomForestRegressor

import os
DATA_DIR = os.environ.get("KAAVALAI_DATA_DIR", "./data")

# ---------------------------------------------------------
# Load ER-schema tables
# ---------------------------------------------------------
case_master = pd.read_csv(f"{DATA_DIR}/CaseMaster.csv", parse_dates=["CrimeRegisteredDate", "IncidentFromDate", "IncidentToDate"])
accused = pd.read_csv(f"{DATA_DIR}/Accused.csv")
victim = pd.read_csv(f"{DATA_DIR}/Victim.csv")
complainant = pd.read_csv(f"{DATA_DIR}/ComplainantDetails.csv")
arrest = pd.read_csv(f"{DATA_DIR}/ArrestSurrender.csv")
chargesheet = pd.read_csv(f"{DATA_DIR}/ChargesheetDetails.csv")
district = pd.read_csv(f"{DATA_DIR}/District.csv")
crime_head = pd.read_csv(f"{DATA_DIR}/CrimeHead.csv")
crime_subhead = pd.read_csv(f"{DATA_DIR}/CrimeSubHead.csv")
gravity = pd.read_csv(f"{DATA_DIR}/GravityOffence.csv")
case_status = pd.read_csv(f"{DATA_DIR}/CaseStatusMaster.csv")
unit = pd.read_csv(f"{DATA_DIR}/Unit.csv")

# ---------------------------------------------------------
# Enrich CaseMaster with readable labels (joins)
# ---------------------------------------------------------
cm = case_master.merge(district[["DistrictID", "DistrictName"]], on="DistrictID", how="left")
cm = cm.merge(crime_head[["CrimeHeadID", "CrimeGroupName"]], left_on="CrimeMajorHeadID", right_on="CrimeHeadID", how="left")
cm = cm.merge(crime_subhead[["CrimeSubHeadID", "CrimeHeadName"]], left_on="CrimeMinorHeadID", right_on="CrimeSubHeadID", how="left")
cm = cm.merge(gravity, on="GravityOffenceID", how="left")
cm = cm.merge(case_status, on="CaseStatusID", how="left")
cm = cm.rename(columns={
    "CrimeGroupName": "crime_type",       # major head, e.g. "Crimes Against Property"
    "CrimeHeadName": "crime_subtype",     # sub head, e.g. "Theft"
    "DistrictName": "district",
    "LookupValue": "gravity",
    "CaseStatusName": "case_status",
})

# ===========================================================
# 1. SPATIOTEMPORAL HOTSPOT DETECTION
# ===========================================================
def detect_hotspots(df, eps_km=3.0, min_samples=6):
    results = []
    for (district_name, crime_type), group in df.groupby(["district", "crime_type"]):
        if len(group) < min_samples:
            continue
        coords_km = group[["latitude", "longitude"]].values * 111.0
        db = DBSCAN(eps=eps_km, min_samples=min_samples).fit(coords_km)
        group = group.copy()
        group["hotspot_cluster"] = db.labels_
        results.append(group)
    result_df = pd.concat(results)

    hotspot_summary = (
        result_df[result_df["hotspot_cluster"] != -1]
        .groupby(["crime_type", "district", "hotspot_cluster"])
        .agg(
            incident_count=("CaseMasterID", "count"),
            centroid_lat=("latitude", "mean"),
            centroid_lon=("longitude", "mean"),
            heinous_ratio=("gravity", lambda x: (x == "Heinous").mean()),
        )
        .reset_index()
        .sort_values("incident_count", ascending=False)
    )
    return result_df, hotspot_summary


def detect_emerging_trends(df, recent_months=3, baseline_months=12):
    df = df.copy()
    df["year_month"] = df["CrimeRegisteredDate"].dt.to_period("M")
    max_month = df["year_month"].max()
    recent_cutoff = max_month - recent_months
    baseline_cutoff = max_month - baseline_months

    recent = df[df["year_month"] > recent_cutoff]
    baseline = df[(df["year_month"] > baseline_cutoff) & (df["year_month"] <= recent_cutoff)]

    recent_rate = recent.groupby(["district", "crime_type"]).size() / recent_months
    baseline_rate = baseline.groupby(["district", "crime_type"]).size() / (baseline_months - recent_months)

    comparison = pd.DataFrame({
        "recent_monthly_rate": recent_rate, "baseline_monthly_rate": baseline_rate
    }).fillna(0)
    comparison["pct_change"] = np.where(
        comparison["baseline_monthly_rate"] > 0,
        (comparison["recent_monthly_rate"] - comparison["baseline_monthly_rate"]) / comparison["baseline_monthly_rate"] * 100,
        np.where(comparison["recent_monthly_rate"] > 0, 100, 0)
    )
    comparison = comparison.reset_index().sort_values("pct_change", ascending=False)
    comparison["alert_level"] = pd.cut(
        comparison["pct_change"], bins=[-np.inf, 10, 30, 60, np.inf],
        labels=["Stable", "Watch", "Elevated", "Red Alert"]
    )
    return comparison


# ===========================================================
# 2. CRIMINAL NETWORK ANALYSIS
# ===========================================================
def build_criminal_network(accused_df):
    """
    Nodes = unique persons, resolved via _pool_id (real deployment would use
    Zia-based fuzzy identity resolution on name+age+gender+biometrics, since
    AccusedMasterID is scoped per-case in the real ER schema, not per-person).
    Edges = co-accused on the same CaseMasterID.
    """
    G = nx.Graph()
    person_ids = accused_df["_pool_id"].unique()
    for pid in person_ids:
        G.add_node(pid)

    for case_id, group in accused_df.groupby("CaseMasterID"):
        members = group["_pool_id"].unique().tolist()
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                if G.has_edge(members[i], members[j]):
                    G[members[i]][members[j]]["weight"] += 1
                else:
                    G.add_edge(members[i], members[j], weight=1, relation="co-accused")

    degree_cent = nx.degree_centrality(G)
    betweenness_cent = nx.betweenness_centrality(G, k=min(500, len(G)), seed=42)

    centrality_df = pd.DataFrame({
        "person_id": list(degree_cent.keys()),
        "degree_centrality": list(degree_cent.values()),
        "betweenness_centrality": [betweenness_cent[k] for k in degree_cent.keys()],
    })

    repeat_counts = accused_df.groupby("_pool_id")["CaseMasterID"].nunique().rename("case_count")
    centrality_df = centrality_df.merge(repeat_counts, left_on="person_id", right_index=True, how="left").fillna(0)
    centrality_df["repeat_offender_flag"] = centrality_df["case_count"] >= 3

    # sample a representative name per person_id for display
    name_lookup = accused_df.drop_duplicates("_pool_id").set_index("_pool_id")["AccusedName"]
    centrality_df["display_name"] = centrality_df["person_id"].map(name_lookup)

    components = [c for c in nx.connected_components(G) if len(c) >= 4]
    group_summary = pd.DataFrame([
        {"group_id": f"NET{i+1:03d}", "members": len(c),
         "member_ids": ",".join(str(x) for x in c)}  # full membership, not truncated
        for i, c in enumerate(sorted(components, key=len, reverse=True))
    ])

    return G, centrality_df, group_summary


# ===========================================================
# 3. PREDICTIVE RISK SCORING (explainable)
# ===========================================================
def compute_risk_scores(cm_df):
    df = cm_df.copy()
    df["year_month"] = df["CrimeRegisteredDate"].dt.to_period("M").astype(str)
    df["month_num"] = df["CrimeRegisteredDate"].dt.month
    df["hour"] = df["IncidentFromDate"].dt.hour

    agg = df.groupby(["district", "year_month"]).agg(
        incident_count=("CaseMasterID", "count"),
        heinous_ratio=("gravity", lambda x: (x == "Heinous").mean()),
        night_incident_ratio=("hour", lambda x: ((x >= 20) | (x <= 5)).mean()),
        undetected_ratio=("case_status", lambda x: (x == "Undetected").mean()),
        month_num=("month_num", "first"),
    ).reset_index()

    agg = agg.sort_values(["district", "year_month"])
    agg["next_month_incidents"] = agg.groupby("district")["incident_count"].shift(-1)
    train_df = agg.dropna(subset=["next_month_incidents"])

    features = ["incident_count", "heinous_ratio", "night_incident_ratio", "undetected_ratio", "month_num"]
    X = train_df[features]
    y = train_df["next_month_incidents"]

    model = RandomForestRegressor(n_estimators=200, max_depth=6, random_state=42)
    model.fit(X, y)

    agg["predicted_next_month_risk"] = model.predict(agg[features])
    importances = dict(zip(features, model.feature_importances_))

    agg["risk_score_0_100"] = (
        (agg["predicted_next_month_risk"] - agg["predicted_next_month_risk"].min())
        / (agg["predicted_next_month_risk"].max() - agg["predicted_next_month_risk"].min()) * 100
    ).round(1)

    return agg, importances


# ===========================================================
# 5. SIMILAR PAST CASES (structured similarity, not text)
# ===========================================================
def compute_similar_cases(cm_df, links_df, top_n=3):
    """
    Finds the top-N most similar past cases for each case, using structured
    fields rather than BriefFacts text — BriefFacts is Faker-generated Lorem
    Ipsum in this synthetic dataset, so text similarity on it would produce
    meaningless (or misleadingly plausible-looking) matches. Real KSP data
    would have genuine narrative text; this approach is honest either way
    and arguably more useful for investigators than prose similarity alone.

    Similarity score combines: same crime subtype (heaviest weight), same
    district, same gravity level, and same case status — plus a bonus if
    any accused persons overlap between the two cases (shared network).
    """
    df = cm_df[["CaseMasterID", "district", "crime_subtype", "gravity", "case_status",
                "CrimeRegisteredDate"]].copy()

    # accused-per-case lookup for the network-overlap bonus
    accused_by_case = links_df.groupby("CaseMasterID")["_pool_id"].apply(set).to_dict() \
        if "_pool_id" in links_df.columns else {}

    # Group by crime_subtype first — comparing only within the same subtype
    # keeps this O(n * group_size) instead of O(n^2) across all cases.
    results = []
    for subtype, group in df.groupby("crime_subtype"):
        records = group.to_dict("records")
        for i, case_a in enumerate(records):
            scores = []
            for j, case_b in enumerate(records):
                if case_a["CaseMasterID"] == case_b["CaseMasterID"]:
                    continue
                score = 40  # same subtype baseline (guaranteed within this group)
                if case_a["district"] == case_b["district"]:
                    score += 25
                if case_a["gravity"] == case_b["gravity"]:
                    score += 15
                if case_a["case_status"] == case_b["case_status"]:
                    score += 10
                shared_accused = accused_by_case.get(case_a["CaseMasterID"], set()) & \
                                  accused_by_case.get(case_b["CaseMasterID"], set())
                if shared_accused:
                    score += 30
                scores.append((case_b["CaseMasterID"], score))

            scores.sort(key=lambda x: x[1], reverse=True)
            top_matches = scores[:top_n]
            for rank, (matched_id, score) in enumerate(top_matches, start=1):
                results.append({
                    "CaseMasterID": case_a["CaseMasterID"],
                    "similar_CaseMasterID": matched_id,
                    "similarity_score": score,
                    "rank": rank,
                })

    return pd.DataFrame(results)


if __name__ == "__main__":
    print("=== 1. Hotspot Detection ===")
    labeled_cases, hotspots = detect_hotspots(cm)
    print(f"Found {len(hotspots)} hotspot clusters")
    hotspots.to_csv(f"{DATA_DIR}/hotspots.csv", index=False)

    print("\n=== 2. Emerging Trend Alerts ===")
    trends = detect_emerging_trends(cm)
    print(trends.head(5))
    trends.to_csv(f"{DATA_DIR}/emerging_trends.csv", index=False)

    print("\n=== 3. Criminal Network Analysis ===")
    G, centrality_df, groups = build_criminal_network(accused)
    print(f"Network: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    print(f"Organized crime groups detected (size>=4): {len(groups)}")
    centrality_df.sort_values("betweenness_centrality", ascending=False).to_csv(
        f"{DATA_DIR}/network_centrality.csv", index=False)
    groups.to_csv(f"{DATA_DIR}/organized_crime_groups.csv", index=False)

    print("\n=== 4. Predictive Risk Scoring ===")
    risk_df, importances = compute_risk_scores(cm)
    print("Feature importances (explainability):", importances)
    risk_df.to_csv(f"{DATA_DIR}/risk_scores.csv", index=False)

    # Save enriched CaseMaster (with joined labels) for the dashboard to use directly
    cm.to_csv(f"{DATA_DIR}/CaseMaster_enriched.csv", index=False)

    print("\n=== 5. Similar Past Cases ===")
    similar_cases = compute_similar_cases(cm, accused)
    print(f"Computed similar-case matches for {similar_cases['CaseMasterID'].nunique()} cases")
    similar_cases.to_csv(f"{DATA_DIR}/similar_cases.csv", index=False)

    print("\nAll analytics outputs saved to", DATA_DIR)
