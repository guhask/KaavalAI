"""
KaavalAI - Synthetic Dataset Generator (v2)
Matches the official Karnataka Police FIR System ER Diagram exactly.

Generates all lookup/master tables + transactional tables (CaseMaster, Accused,
Victim, ComplainantDetails, ArrestSurrender, ChargesheetDetails, ActSectionAssociation)
with correct column names, keys, and the CrimeNo/CaseNo numbering format specified
in the ER document.
"""

import pandas as pd
import numpy as np
from faker import Faker
import random
from datetime import datetime, timedelta

fake = Faker('en_IN')
random.seed(42)
np.random.seed(42)
import os
OUT = os.environ.get("KAAVALAI_DATA_DIR", "./data")
os.makedirs(OUT, exist_ok=True)

START_DATE = datetime(2022, 1, 1)
END_DATE = datetime(2026, 5, 31)

def random_date(start=START_DATE, end=END_DATE):
    delta = end - start
    return start + timedelta(days=random.randint(0, delta.days),
                              hours=random.randint(0, 23), minutes=random.randint(0, 59))

# ===========================================================
# 1. LOOKUP / MASTER TABLES
# ===========================================================

# --- State ---
state_df = pd.DataFrame([{"StateID": 1, "StateName": "Karnataka", "NationalityID": 1, "Active": 1}])

# --- District (Karnataka's 31 districts, using real DistrictIDs mirrored from CrimeNo examples) ---
DISTRICT_NAMES = [
    "Bengaluru Urban", "Bengaluru Rural", "Mysuru", "Belagavi", "Kalaburagi", "Mangaluru (D.K.)",
    "Hubballi-Dharwad", "Ballari", "Tumakuru", "Shivamogga", "Vijayapura", "Raichur", "Bidar",
    "Chitradurga", "Davanagere", "Hassan", "Mandya", "Kodagu", "Chikkamagaluru", "Udupi",
    "Uttara Kannada", "Kolar", "Chikkaballapur", "Ramanagara", "Yadgir", "Koppal", "Gadag",
    "Haveri", "Bagalkot", "Chamarajanagar", "Vijayanagara",
]
district_df = pd.DataFrame([
    {"DistrictID": 4430 + i if i == 0 else 1000 + i, "DistrictName": name, "StateID": 1, "Active": 1}
    for i, name in enumerate(DISTRICT_NAMES)
])
# Keep DistrictID 4430 fixed for Bengaluru Urban to match the ER doc's CrimeNo example (04430...)
district_df.loc[0, "DistrictID"] = 4430

# --- UnitType ---
unit_type_df = pd.DataFrame([
    {"UnitTypeID": 1, "UnitTypeName": "Police Station", "CityDistState": "City", "Hierarchy": 4, "Active": 1},
    {"UnitTypeID": 2, "UnitTypeName": "Circle Office", "CityDistState": "District", "Hierarchy": 3, "Active": 1},
    {"UnitTypeID": 3, "UnitTypeName": "Sub-Division Office", "CityDistState": "District", "Hierarchy": 2, "Active": 1},
    {"UnitTypeID": 4, "UnitTypeName": "SP Office", "CityDistState": "District", "Hierarchy": 1, "Active": 1},
])

# --- Unit (Police Stations, ~10 per district) ---
unit_rows = []
unit_id_counter = 1
for _, d in district_df.iterrows():
    n_ps = random.randint(6, 12)
    for j in range(n_ps):
        unit_rows.append({
            "UnitID": 6202600001 + unit_id_counter if False else unit_id_counter,  # simple sequential UnitID
            "UnitName": f"{d['DistrictName']} PS-{j+1}",
            "TypeID": 1,
            "ParentUnit": None,
            "NationalityID": 1,
            "StateID": 1,
            "DistrictID": d["DistrictID"],
            "Active": 1,
        })
        unit_id_counter += 1
unit_df = pd.DataFrame(unit_rows)
# Unit code used inside CrimeNo (4-digit) — derive from UnitID mod 9999, zero-padded
unit_df["UnitCode4Digit"] = (unit_df["UnitID"] % 9999).apply(lambda x: f"{x:04d}")

# --- Rank ---
rank_df = pd.DataFrame([
    {"RankID": 1, "RankName": "Constable", "Hierarchy": 7, "Active": 1},
    {"RankID": 2, "RankName": "Head Constable", "Hierarchy": 6, "Active": 1},
    {"RankID": 3, "RankName": "Asst Sub-Inspector (ASI)", "Hierarchy": 5, "Active": 1},
    {"RankID": 4, "RankName": "Sub-Inspector (SI)", "Hierarchy": 4, "Active": 1},
    {"RankID": 5, "RankName": "Inspector", "Hierarchy": 3, "Active": 1},
    {"RankID": 6, "RankName": "Deputy Superintendent (DSP)", "Hierarchy": 2, "Active": 1},
    {"RankID": 7, "RankName": "Superintendent of Police (SP)", "Hierarchy": 1, "Active": 1},
])

# --- Designation ---
designation_df = pd.DataFrame([
    {"DesignationID": 1, "DesignationName": "Investigating Officer", "Active": 1, "SortOrder": 1},
    {"DesignationID": 2, "DesignationName": "Station House Officer (SHO)", "Active": 1, "SortOrder": 2},
    {"DesignationID": 3, "DesignationName": "Circle Inspector", "Active": 1, "SortOrder": 3},
    {"DesignationID": 4, "DesignationName": "Sub-Divisional Officer", "Active": 1, "SortOrder": 4},
])

# --- Employee ---
N_EMPLOYEES = 1500
employee_rows = []
for i in range(N_EMPLOYEES):
    unit_row = unit_df.sample(1).iloc[0]
    employee_rows.append({
        "EmployeeID": i + 1,
        "DistrictID": unit_row["DistrictID"],
        "UnitID": unit_row["UnitID"],
        "RankID": random.choices([1,2,3,4,5,6,7], weights=[25,20,15,20,12,5,3])[0],
        "DesignationID": random.choice([1,2,3,4]),
        "KGID": f"KGID{fake.random_number(digits=8)}",
        "FirstName": fake.first_name(),
        "EmployeeDOB": fake.date_of_birth(minimum_age=25, maximum_age=58),
        "GenderID": random.choices(["M", "F"], weights=[0.85, 0.15])[0],
        "BloodGroupID": random.choice(["A+", "B+", "O+", "AB+", "A-", "B-", "O-"]),
        "PhysicallyChallenged": random.choices([0, 1], weights=[0.97, 0.03])[0],
        "AppointmentDate": fake.date_between(start_date="-30y", end_date="-1y"),
    })
employee_df = pd.DataFrame(employee_rows)

# --- CaseCategory (from ER doc examples: FIR=1, UDR=3, PAR=4, Zero FIR=8) ---
case_category_df = pd.DataFrame([
    {"CaseCategoryID": 1, "LookupValue": "FIR"},
    {"CaseCategoryID": 3, "LookupValue": "UDR"},
    {"CaseCategoryID": 4, "LookupValue": "PAR"},
    {"CaseCategoryID": 8, "LookupValue": "Zero FIR"},
])

# --- GravityOffence ---
gravity_df = pd.DataFrame([
    {"GravityOffenceID": 1, "LookupValue": "Heinous"},
    {"GravityOffenceID": 2, "LookupValue": "Non-Heinous"},
])

# --- CrimeHead / CrimeSubHead ---
crime_head_df = pd.DataFrame([
    {"CrimeHeadID": 1, "CrimeGroupName": "Crimes Against Body", "Active": 1},
    {"CrimeHeadID": 2, "CrimeGroupName": "Crimes Against Property", "Active": 1},
    {"CrimeHeadID": 3, "CrimeGroupName": "Crimes Against Women", "Active": 1},
    {"CrimeHeadID": 4, "CrimeGroupName": "Economic Offences", "Active": 1},
    {"CrimeHeadID": 5, "CrimeGroupName": "Cyber Crime", "Active": 1},
    {"CrimeHeadID": 6, "CrimeGroupName": "Narcotics (NDPS)", "Active": 1},
])
crime_subhead_df = pd.DataFrame([
    {"CrimeSubHeadID": 1, "CrimeHeadID": 1, "CrimeHeadName": "Murder", "SeqID": 1},
    {"CrimeSubHeadID": 2, "CrimeHeadID": 1, "CrimeHeadName": "Grievous Hurt", "SeqID": 2},
    {"CrimeSubHeadID": 3, "CrimeHeadID": 2, "CrimeHeadName": "Robbery", "SeqID": 1},
    {"CrimeSubHeadID": 4, "CrimeHeadID": 2, "CrimeHeadName": "Theft", "SeqID": 2},
    {"CrimeSubHeadID": 5, "CrimeHeadID": 2, "CrimeHeadName": "House Break-in", "SeqID": 3},
    {"CrimeSubHeadID": 6, "CrimeHeadID": 3, "CrimeHeadName": "Dowry Death", "SeqID": 1},
    {"CrimeSubHeadID": 7, "CrimeHeadID": 3, "CrimeHeadName": "Assault on Women", "SeqID": 2},
    {"CrimeSubHeadID": 8, "CrimeHeadID": 4, "CrimeHeadName": "Cheating", "SeqID": 1},
    {"CrimeSubHeadID": 9, "CrimeHeadID": 4, "CrimeHeadName": "Criminal Breach of Trust", "SeqID": 2},
    {"CrimeSubHeadID": 10, "CrimeHeadID": 5, "CrimeHeadName": "Online Fraud", "SeqID": 1},
    {"CrimeSubHeadID": 11, "CrimeHeadID": 5, "CrimeHeadName": "Phishing", "SeqID": 2},
    {"CrimeSubHeadID": 12, "CrimeHeadID": 6, "CrimeHeadName": "Drug Possession", "SeqID": 1},
    {"CrimeSubHeadID": 13, "CrimeHeadID": 6, "CrimeHeadName": "Drug Trafficking", "SeqID": 2},
])

# --- Act / Section / CrimeHeadActSection ---
act_df = pd.DataFrame([
    {"ActCode": "IPC", "ActDescription": "Indian Penal Code, 1860", "ShortName": "IPC", "Active": 1},
    {"ActCode": "NDPS", "ActDescription": "Narcotic Drugs and Psychotropic Substances Act, 1985", "ShortName": "NDPS", "Active": 1},
    {"ActCode": "IT_ACT", "ActDescription": "Information Technology Act, 2000", "ShortName": "IT Act", "Active": 1},
    {"ActCode": "POCSO", "ActDescription": "Protection of Children from Sexual Offences Act, 2012", "ShortName": "POCSO", "Active": 1},
])
section_df = pd.DataFrame([
    {"ActCode": "IPC", "SectionCode": "302", "SectionDescription": "Murder", "Active": 1},
    {"ActCode": "IPC", "SectionCode": "307", "SectionDescription": "Attempt to Murder", "Active": 1},
    {"ActCode": "IPC", "SectionCode": "379", "SectionDescription": "Theft", "Active": 1},
    {"ActCode": "IPC", "SectionCode": "392", "SectionDescription": "Robbery", "Active": 1},
    {"ActCode": "IPC", "SectionCode": "420", "SectionDescription": "Cheating", "Active": 1},
    {"ActCode": "IPC", "SectionCode": "304B", "SectionDescription": "Dowry Death", "Active": 1},
    {"ActCode": "IPC", "SectionCode": "354", "SectionDescription": "Assault on Woman with Intent to Outrage Modesty", "Active": 1},
    {"ActCode": "NDPS", "SectionCode": "20", "SectionDescription": "Possession of Cannabis", "Active": 1},
    {"ActCode": "NDPS", "SectionCode": "21", "SectionDescription": "Possession of Manufactured Drugs", "Active": 1},
    {"ActCode": "IT_ACT", "SectionCode": "66C", "SectionDescription": "Identity Theft", "Active": 1},
    {"ActCode": "IT_ACT", "SectionCode": "66D", "SectionDescription": "Cheating by Personation using Computer", "Active": 1},
])
crime_head_act_section_df = pd.DataFrame([
    {"CrimeHeadID": 1, "ActCode": "IPC", "SectionCode": "302"},
    {"CrimeHeadID": 1, "ActCode": "IPC", "SectionCode": "307"},
    {"CrimeHeadID": 2, "ActCode": "IPC", "SectionCode": "379"},
    {"CrimeHeadID": 2, "ActCode": "IPC", "SectionCode": "392"},
    {"CrimeHeadID": 3, "ActCode": "IPC", "SectionCode": "304B"},
    {"CrimeHeadID": 3, "ActCode": "IPC", "SectionCode": "354"},
    {"CrimeHeadID": 4, "ActCode": "IPC", "SectionCode": "420"},
    {"CrimeHeadID": 5, "ActCode": "IT_ACT", "SectionCode": "66C"},
    {"CrimeHeadID": 5, "ActCode": "IT_ACT", "SectionCode": "66D"},
    {"CrimeHeadID": 6, "ActCode": "NDPS", "SectionCode": "20"},
    {"CrimeHeadID": 6, "ActCode": "NDPS", "SectionCode": "21"},
])

# --- CaseStatusMaster ---
case_status_df = pd.DataFrame([
    {"CaseStatusID": 1, "CaseStatusName": "Under Investigation"},
    {"CaseStatusID": 2, "CaseStatusName": "Charge Sheeted"},
    {"CaseStatusID": 3, "CaseStatusName": "Closed"},
    {"CaseStatusID": 4, "CaseStatusName": "Undetected"},
])

# --- Court ---
court_rows = []
for i, (_, d) in enumerate(district_df.iterrows()):
    court_rows.append({
        "CourtID": i + 1,
        "CourtName": f"District & Sessions Court, {d['DistrictName']}",
        "DistrictID": d["DistrictID"],
        "StateID": 1,
        "Active": 1,
    })
court_df = pd.DataFrame(court_rows)

# --- CasteMaster / ReligionMaster / OccupationMaster ---
caste_df = pd.DataFrame([
    {"caste_master_id": i + 1, "caste_master_name": name}
    for i, name in enumerate(["General", "OBC", "SC", "ST", "Category-1", "Category-2A", "Category-2B", "Category-3A", "Category-3B"])
])
religion_df = pd.DataFrame([
    {"ReligionID": i + 1, "ReligionName": name}
    for i, name in enumerate(["Hindu", "Muslim", "Christian", "Sikh", "Jain", "Buddhist", "Other"])
])
occupation_df = pd.DataFrame([
    {"OccupationID": i + 1, "OccupationName": name}
    for i, name in enumerate(["Farmer", "Daily Wage Worker", "Government Employee", "Private Employee",
                               "Self-Employed / Business", "Student", "Unemployed", "Homemaker", "Unknown"])
])

# ===========================================================
# 2. TRANSACTIONAL TABLES
# ===========================================================
N_CASES = 6000

def build_crime_no(case_category_id, district_id, unit_code_4digit, year, serial):
    return f"{case_category_id}{district_id:04d}{unit_code_4digit}{year}{serial:05d}"

def build_case_no(year, serial):
    return f"{year}{serial:05d}"

# Assign gangs across accused pool later; first generate CaseMaster
case_rows = []
serial_counters = {}  # (unit_id, case_category_id, year) -> serial

# Fixed centroid per district (approx Karnataka geography), computed ONCE —
# previously this was recomputed per-case for non-Bengaluru districts, scattering
# points ~300km apart and breaking DBSCAN hotspot detection (0 clusters found).
KARNATAKA_BOUNDS = {"lat": (11.6, 18.4), "lon": (74.0, 78.5)}
district_centroid_map = {4430: (12.9716, 77.5946)}  # Bengaluru Urban (real coords)
for did in district_df["DistrictID"].tolist():
    if did not in district_centroid_map:
        district_centroid_map[did] = (
            round(np.random.uniform(*KARNATAKA_BOUNDS["lat"]), 4),
            round(np.random.uniform(*KARNATAKA_BOUNDS["lon"]), 4),
        )

# 2 hotspot sub-zones per district, offset ~2-5km from the district centroid
district_hotspot_zones = {}
for did, (clat, clon) in district_centroid_map.items():
    zones = []
    for _ in range(2):
        zones.append((clat + np.random.uniform(-0.03, 0.03), clon + np.random.uniform(-0.03, 0.03)))
    district_hotspot_zones[did] = zones


for i in range(N_CASES):
    district_row = district_df.sample(1, weights=district_df["DistrictID"].apply(
        lambda x: 3.0 if x == 4430 else 1.0)).iloc[0]
    district_id = district_row["DistrictID"]
    unit_candidates = unit_df[unit_df["DistrictID"] == district_id]
    unit_row = unit_candidates.sample(1).iloc[0]

    case_category_id = random.choices([1, 3, 4, 8], weights=[0.85, 0.05, 0.05, 0.05])[0]
    crime_reg_date = random_date()
    year = crime_reg_date.year

    key = (unit_row["UnitID"], case_category_id, year)
    serial_counters[key] = serial_counters.get(key, 0) + 1
    serial = serial_counters[key]

    crime_no = build_crime_no(case_category_id, district_id, unit_row["UnitCode4Digit"], year, serial)
    case_no = build_case_no(year, serial)

    crime_head_id = random.choice(crime_head_df["CrimeHeadID"].tolist())
    sub_heads = crime_subhead_df[crime_subhead_df["CrimeHeadID"] == crime_head_id]
    crime_sub_head_id = sub_heads.sample(1)["CrimeSubHeadID"].values[0]

    emp_row = employee_df[employee_df["UnitID"] == unit_row["UnitID"]]
    officer_id = emp_row.sample(1)["EmployeeID"].values[0] if len(emp_row) else employee_df.sample(1)["EmployeeID"].values[0]

    # 70% of cases cluster tightly around 1-2 known "hotspot zones" within the
    # district (e.g. a busy market area, a slum cluster, a highway junction) —
    # 30% scatter more broadly. This gives DBSCAN genuine spatial density to
    # detect, rather than clustering random noise fluctuations.
    hotspot_zones = district_hotspot_zones[district_id]
    if random.random() < 0.7:
        zone_lat, zone_lon = random.choice(hotspot_zones)
        lat0, lon0 = zone_lat, zone_lon
        jitter_std = 0.012  # ~1.3km tight cluster
    else:
        lat0, lon0 = district_centroid_map[district_id]
        jitter_std = 0.08  # ~9km broad scatter

    case_rows.append({
        "CaseMasterID": i + 1,
        "CrimeNo": crime_no,
        "CaseNo": case_no,
        "CrimeRegisteredDate": crime_reg_date.date(),
        "PolicePersonID": officer_id,
        "PoliceStationID": unit_row["UnitID"],
        "CaseCategoryID": case_category_id,
        "GravityOffenceID": random.choices([1, 2], weights=[0.25, 0.75])[0],
        "CrimeMajorHeadID": crime_head_id,
        "CrimeMinorHeadID": crime_sub_head_id,
        "CaseStatusID": random.choices([1, 2, 3, 4], weights=[0.4, 0.3, 0.2, 0.1])[0],
        "CourtID": court_df[court_df["DistrictID"] == district_id]["CourtID"].values[0],
        "IncidentFromDate": crime_reg_date - timedelta(hours=random.randint(1, 48)),
        "IncidentToDate": crime_reg_date,
        "InfoReceivedPSDate": crime_reg_date + timedelta(hours=random.randint(0, 6)),
        "latitude": round(lat0 + np.random.normal(0, jitter_std), 6),
        "longitude": round(lon0 + np.random.normal(0, jitter_std), 6),
        "BriefFacts": fake.sentence(nb_words=12),
        "DistrictID": district_id,  # kept for convenience joins in dashboard (not in original ER but derivable via Unit)
    })

case_master_df = pd.DataFrame(case_rows)

# --- ComplainantDetails ---
complainant_rows = []
comp_id = 1
for _, c in case_master_df.iterrows():
    complainant_rows.append({
        "ComplainantID": comp_id,
        "CaseMasterID": c["CaseMasterID"],
        "ComplainantName": fake.name(),
        "AgeYear": int(np.clip(np.random.normal(36, 13), 18, 85)),
        "OccupationID": random.choice(occupation_df["OccupationID"].tolist()),
        "ReligionID": random.choices(religion_df["ReligionID"].tolist(), weights=[70,13,5,3,3,2,4])[0],
        "CasteID": random.choice(caste_df["caste_master_id"].tolist()),
        "GenderID": random.choices(["M", "F"], weights=[0.6, 0.4])[0],
    })
    comp_id += 1
complainant_df = pd.DataFrame(complainant_rows)

# --- Victim (1-2 per case) ---
victim_rows = []
vic_id = 1
for _, c in case_master_df.iterrows():
    n_v = random.choices([1, 2], weights=[0.85, 0.15])[0]
    for _ in range(n_v):
        victim_rows.append({
            "VictimMasterID": vic_id,
            "CaseMasterID": c["CaseMasterID"],
            "VictimName": fake.name(),
            "AgeYear": int(np.clip(np.random.normal(33, 15), 1, 90)),
            "GenderID": random.choices(["M", "F", "T"], weights=[0.52, 0.46, 0.02])[0],
            "VictimPolice": random.choices([0, 1], weights=[0.98, 0.02])[0],
        })
        vic_id += 1
victim_df = pd.DataFrame(victim_rows)

# --- Accused pool with gang structure (for network analysis) ---
N_ACCUSED_POOL = 2600
accused_pool = []
for i in range(N_ACCUSED_POOL):
    accused_pool.append({
        "_pool_id": i + 1,
        "AccusedName": fake.name(),
        "AgeYear": int(np.clip(np.random.normal(29, 9), 15, 70)),
        "GenderID": random.choices(["M", "F", "T"], weights=[0.9, 0.09, 0.01])[0],
        "_prior_convictions": np.random.choice([0,0,0,1,1,2,3,4,5],
                                                p=[0.35,0.15,0.1,0.15,0.08,0.07,0.05,0.03,0.02]),
    })
accused_pool_df = pd.DataFrame(accused_pool)

# gangs: cluster high-conviction accused into groups for realistic network analysis
def assign_gangs(pool_df, n_gangs=25, size_range=(4, 9)):
    candidates = pool_df[pool_df["_prior_convictions"] >= 1]["_pool_id"].tolist()
    random.shuffle(candidates)
    gang_map, idx = {}, 0
    for g in range(n_gangs):
        size = random.randint(*size_range)
        members = candidates[idx: idx + size]
        idx += size
        if len(members) < 2:
            break
        for m in members:
            gang_map[m] = f"GANG{g+1:03d}"
    return gang_map

gang_map = assign_gangs(accused_pool_df)
gang_members_by_gang = {}
for pid, gid in gang_map.items():
    gang_members_by_gang.setdefault(gid, []).append(pid)

accused_rows = []
acc_id = 1
pool_weights = 1 + accused_pool_df["_prior_convictions"].values * 2
pool_ids = accused_pool_df["_pool_id"].tolist()

for _, c in case_master_df.iterrows():
    n_acc = random.choices([1, 2], weights=[0.8, 0.2])[0]
    if n_acc == 2 and random.random() < 0.6 and gang_members_by_gang:
        gid = random.choice(list(gang_members_by_gang.keys()))
        members = gang_members_by_gang[gid]
        chosen = random.sample(members, 2) if len(members) >= 2 else random.choices(pool_ids, weights=pool_weights, k=n_acc)
    else:
        chosen = random.choices(pool_ids, weights=pool_weights, k=n_acc)

    for order, pid in enumerate(chosen):
        pool_row = accused_pool_df[accused_pool_df["_pool_id"] == pid].iloc[0]
        accused_rows.append({
            "AccusedMasterID": acc_id,
            "CaseMasterID": c["CaseMasterID"],
            "AccusedName": pool_row["AccusedName"],
            "AgeYear": pool_row["AgeYear"],
            "GenderID": pool_row["GenderID"],
            "PersonID": f"A{order+1}",
            "_pool_id": pid,  # kept for network analysis; not in original ER schema
        })
        acc_id += 1
accused_df = pd.DataFrame(accused_rows)

# --- ActSectionAssociation (1-2 sections per case, matched to crime head) ---
act_section_rows = []
for _, c in case_master_df.iterrows():
    matches = crime_head_act_section_df[crime_head_act_section_df["CrimeHeadID"] == c["CrimeMajorHeadID"]]
    if len(matches) == 0:
        continue
    n_sections = random.choices([1, 2], weights=[0.7, 0.3])[0]
    sampled = matches.sample(min(n_sections, len(matches)))
    for order, (_, m) in enumerate(sampled.iterrows()):
        act_section_rows.append({
            "CaseMasterID": c["CaseMasterID"],
            "ActID": m["ActCode"],
            "SectionID": m["SectionCode"],
            "ActOrderID": order + 1,
            "SectionOrderID": order + 1,
        })
act_section_df = pd.DataFrame(act_section_rows)

# --- ArrestSurrender (for ~60% of cases with accused) ---
arrest_rows = []
arrest_id = 1
for _, c in case_master_df.iterrows():
    case_accused = accused_df[accused_df["CaseMasterID"] == c["CaseMasterID"]]
    if len(case_accused) == 0 or random.random() > 0.6:
        continue
    for _, acc in case_accused.iterrows():
        arrest_rows.append({
            "ArrestSurrenderID": arrest_id,
            "CaseMasterID": c["CaseMasterID"],
            "ArrestSurrenderTypeID": random.choices([1, 2], weights=[0.8, 0.2])[0],  # 1=Arrest, 2=Surrender
            "ArrestSurrenderDate": (pd.Timestamp(c["CrimeRegisteredDate"]) + timedelta(days=random.randint(0, 45))).date(),
            "ArrestSurrenderStateId": 1,
            "ArrestSurrenderDistrictId": c["DistrictID"],
            "PoliceStationID": c["PoliceStationID"],
            "IOID": c["PolicePersonID"],
            "CourtID": c["CourtID"],
            "AccusedMasterID": acc["AccusedMasterID"],
            "IsAccused": 1,
            "IsComplainantAccused": random.choices([0, 1], weights=[0.95, 0.05])[0],
        })
        arrest_id += 1
arrest_df = pd.DataFrame(arrest_rows)

# --- ChargesheetDetails (for cases with CaseStatusID == 2 i.e. Charge Sheeted) ---
cs_rows = []
cs_id = 1
chargesheeted = case_master_df[case_master_df["CaseStatusID"] == 2]
for _, c in chargesheeted.iterrows():
    cs_rows.append({
        "CSID": cs_id,
        "CaseMasterID": c["CaseMasterID"],
        "csdate": (pd.Timestamp(c["CrimeRegisteredDate"]) + timedelta(days=random.randint(30, 90))).to_pydatetime(),
        "cstype": random.choices(["A", "B", "C"], weights=[0.85, 0.1, 0.05])[0],
        "PolicePersonID": c["PolicePersonID"],
    })
    cs_id += 1
chargesheet_df = pd.DataFrame(cs_rows)

# ===========================================================
# 3. SAVE ALL TABLES
# ===========================================================
tables = {
    "State": state_df, "District": district_df, "UnitType": unit_type_df, "Unit": unit_df,
    "Rank": rank_df, "Designation": designation_df, "Employee": employee_df,
    "CaseCategory": case_category_df, "GravityOffence": gravity_df,
    "CrimeHead": crime_head_df, "CrimeSubHead": crime_subhead_df,
    "Act": act_df, "Section": section_df, "CrimeHeadActSection": crime_head_act_section_df,
    "CaseStatusMaster": case_status_df, "Court": court_df,
    "CasteMaster": caste_df, "ReligionMaster": religion_df, "OccupationMaster": occupation_df,
    "CaseMaster": case_master_df, "ComplainantDetails": complainant_df, "Victim": victim_df,
    "Accused": accused_df, "ActSectionAssociation": act_section_df,
    "ArrestSurrender": arrest_df, "ChargesheetDetails": chargesheet_df,
}

if __name__ == "__main__":
    for name, df in tables.items():
        df.to_csv(f"{OUT}/{name}.csv", index=False)
        print(f"  {name}: {len(df)} rows")
    print("\nAll ER-schema-aligned tables saved to", OUT)
