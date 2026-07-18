"""
KaavalAI - Catalyst Direct Loader (bypasses bulk-write entirely)

After repeated unresolved failures with Data Store's bulk-write + Stratus job
mechanism (silent 0-row "success", unexplained "Download_URL not available"
errors), this takes a more robust path using only two things independently
confirmed to work:
  1. Plain HTTPS GET of a public Stratus object (confirmed working when the
     bucket's access policy was set to "public")
  2. Data Store's normal insert_rows() API (confirmed working for Act/Section
     once Foreign Key columns were resolved to the parent row's ROWID)

Call pattern (Basic I/O has a 30-second execution limit, so this processes
ONE table per call):
    ?action=load&table_index=0
    (table_index 0-25, matching TABLE_ORDER below — same dependency order as
    the original bulk-write LOAD_PLAN)

For large tables (CaseMaster and its children), rows are inserted in chunks
of 500 to keep each call comfortably within the time limit and avoid overly
large single request bodies.
"""

import json
import csv
import io
import requests
import zcatalyst_sdk as zcatalyst

# Public Stratus object base URL — update the domain if yours differs
# (confirmed pattern: https://<bucket>-development.zohostratus.in/<file>)
STRATUS_BASE_URL = "https://kaavalai-bulk-data-development.zohostratus.in"

# (table_name, [(local_fk_column, referenced_table, referenced_column), ...])
# Empty FK list = no Foreign Key columns, insert as-is.
TABLE_ORDER = [
    ("State", []),
    ("UnitType", []),
    ("Rank", []),
    ("Designation", []),
    ("CaseCategory", []),
    ("GravityOffence", []),
    ("CrimeHead", []),
    ("Act", []),
    ("CaseStatusMaster", []),
    ("CasteMaster", []),
    ("ReligionMaster", []),
    ("OccupationMaster", []),
    ("District", [("StateID", "State", "StateID")]),
    ("Section", [("ActCode", "Act", "ActCode")]),
    ("CrimeSubHead", [("CrimeHeadID", "CrimeHead", "CrimeHeadID")]),
    ("CrimeHeadActSection", [("CrimeHeadID", "CrimeHead", "CrimeHeadID"), ("ActCode", "Act", "ActCode")]),
    ("Court", [("DistrictID", "District", "DistrictID"), ("StateID", "State", "StateID")]),
    ("Unit", [("TypeID", "UnitType", "UnitTypeID"), ("StateID", "State", "StateID"), ("DistrictID", "District", "DistrictID")]),
    ("Employee", [("UnitID", "Unit", "UnitID"), ("DistrictID", "District", "DistrictID"),
                  ("RankID", "Rank", "RankID"), ("DesignationID", "Designation", "DesignationID")]),
    ("CaseMaster", [("PolicePersonID", "Employee", "EmployeeID"), ("PoliceStationID", "Unit", "UnitID"),
                    ("CaseCategoryID", "CaseCategory", "CaseCategoryID"),
                    ("GravityOffenceID", "GravityOffence", "GravityOffenceID"),
                    ("CrimeMajorHeadID", "CrimeHead", "CrimeHeadID"),
                    ("CrimeMinorHeadID", "CrimeSubHead", "CrimeSubHeadID"),
                    ("CaseStatusID", "CaseStatusMaster", "CaseStatusID"),
                    ("CourtID", "Court", "CourtID"), ("DistrictID", "District", "DistrictID")]),
    ("ComplainantDetails", [("CaseMasterID", "CaseMaster", "CaseMasterID"),
                             ("OccupationID", "OccupationMaster", "OccupationID"),
                             ("ReligionID", "ReligionMaster", "ReligionID"),
                             ("CasteID", "CasteMaster", "caste_master_id")]),
    ("Victim", [("CaseMasterID", "CaseMaster", "CaseMasterID")]),
    ("Accused", [("CaseMasterID", "CaseMaster", "CaseMasterID")]),
    ("ActSectionAssociation", [("CaseMasterID", "CaseMaster", "CaseMasterID")]),
    ("ArrestSurrender", [("CaseMasterID", "CaseMaster", "CaseMasterID"),
                          ("ArrestSurrenderStateId", "State", "StateID"),
                          ("ArrestSurrenderDistrictId", "District", "DistrictID"),
                          ("PoliceStationID", "Unit", "UnitID"),
                          ("IOID", "Employee", "EmployeeID"),
                          ("CourtID", "Court", "CourtID"),
                          ("AccusedMasterID", "Accused", "AccusedMasterID")]),
    ("ChargesheetDetails", [("CaseMasterID", "CaseMaster", "CaseMasterID"),
                             ("PolicePersonID", "Employee", "EmployeeID")]),
]

CHUNK_SIZE = 200  # Data Store hard cap: "Only 200 rows can be updated at once"

BOOLEAN_COLUMNS = {"Active", "VictimPolice", "IsAccused", "IsComplainantAccused", "PhysicallyChallenged"}

# Columns that LOOK numeric in some rows but are Var Char in the schema —
# must never be auto-coerced to int/float, or mixed types land in one column
# (e.g. SectionCode has both "302" and "304B" — coercing only the first kind
# sends int 302 alongside string "304B" into the same Var Char column, which
# Data Store rejects with a vague INVALID_INPUT error).
FORCE_STRING_COLUMNS = {
    ("Section", "SectionCode"),
    ("CrimeHeadActSection", "SectionCode"),
    ("Unit", "UnitCode4Digit"),
    ("Employee", "KGID"), ("Employee", "GenderID"), ("Employee", "BloodGroupID"),
    ("CaseMaster", "CrimeNo"), ("CaseMaster", "CaseNo"),
    ("ComplainantDetails", "GenderID"),
    ("Victim", "GenderID"),
    ("Accused", "GenderID"), ("Accused", "PersonID"),
    ("ActSectionAssociation", "ActID"), ("ActSectionAssociation", "SectionID"),
    ("ChargesheetDetails", "cstype"),
}


def coerce_types(row, table_name):
    """csv.DictReader returns every value as a string — convert numeric-looking
    values to int/float and known boolean columns to actual True/False, EXCEPT
    columns in FORCE_STRING_COLUMNS which must stay as strings regardless of
    how they look, since they're Var Char in the schema."""
    coerced = {}
    for key, value in row.items():
        if (table_name, key) in FORCE_STRING_COLUMNS:
            coerced[key] = value
        elif key in BOOLEAN_COLUMNS:
            coerced[key] = value.strip() in ("1", "true", "True")
        elif value == "" or value is None:
            coerced[key] = None
        else:
            try:
                coerced[key] = int(value)
            except ValueError:
                try:
                    coerced[key] = float(value)
                except ValueError:
                    coerced[key] = value
    return coerced


def fetch_csv_rows(table_name):
    url = f"{STRATUS_BASE_URL}/{table_name}.csv"
    resp = requests.get(url, timeout=25)
    resp.raise_for_status()
    reader = csv.DictReader(io.StringIO(resp.text))
    return [coerce_types(row, table_name) for row in reader]


def build_fk_lookup(zcql, referenced_table, referenced_column):
    """Returns {natural_key_value: ROWID} for a referenced table."""
    rows = zcql.execute_query(f"SELECT ROWID, {referenced_column} FROM {referenced_table}")
    return {str(r[referenced_table][referenced_column]): r[referenced_table]["ROWID"] for r in rows}


def handler(context, basicio):
    app = zcatalyst.initialize()
    datastore = app.datastore()
    zcql = app.zcql()

    table_index = int(basicio.get_argument("table_index") or 0)
    if table_index < 0 or table_index >= len(TABLE_ORDER):
        basicio.write(json.dumps({"status": "failure", "reason": f"table_index must be 0-{len(TABLE_ORDER)-1}"}))
        context.close()
        return

    table_name, fk_columns = TABLE_ORDER[table_index]

    try:
        rows = fetch_csv_rows(table_name)

        # Resolve each FK column's natural-key values to the parent's ROWID
        for local_col, ref_table, ref_col in fk_columns:
            lookup = build_fk_lookup(zcql, ref_table, ref_col)
            missing = set()
            for row in rows:
                key = str(row.get(local_col, ""))
                if key in lookup:
                    row[local_col] = lookup[key]
                else:
                    missing.add(key)
            if missing:
                basicio.write(json.dumps({
                    "status": "failure", "table_name": table_name,
                    "reason": f"'{local_col}' values not found in {ref_table}.{ref_col}: {list(missing)[:10]}"
                              f"{'...' if len(missing) > 10 else ''}. Load {ref_table} before {table_name}.",
                }))
                context.close()
                return

        # Drop helper column not part of the real table schema (Accused only)
        for row in rows:
            row.pop("_pool_id", None)

        table = datastore.table(table_name)
        total_inserted = 0
        for i in range(0, len(rows), CHUNK_SIZE):
            chunk = rows[i:i + CHUNK_SIZE]
            table.insert_rows(chunk)
            total_inserted += len(chunk)

        basicio.write(json.dumps({
            "status": "success", "table_name": table_name,
            "rows_fetched": len(rows), "rows_inserted": total_inserted,
        }))

    except Exception as e:
        basicio.write(json.dumps({"status": "failure", "table_name": table_name, "reason": str(e)}))

    context.close()
