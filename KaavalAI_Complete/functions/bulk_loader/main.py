"""
KaavalAI - Catalyst Data Store Bulk Loader (deploy as a Function)

Triggers ONE table's bulk-write job per function call (Basic I/O functions
have a hard 30-second execution limit, so this can't loop over all 26 tables
or poll for completion in a single call — see handler() docstring below for
the call pattern).

Prerequisites:
  1. All 26 tables + columns already created in the Catalyst console per
     catalyst_datastore_schema.md (table/column creation has no programmatic API).
  2. All 26 CSVs manually uploaded to a Stratus bucket named 'kaavalai-bulk-data'
     via the console (drag-and-drop — this function does NOT read your local
     filesystem, since Functions run in Catalyst's cloud, not on your laptop).
  3. Deploy this as a Basic I/O Python Function named e.g. 'bulk_loader'.

Why a Function and not a local script: zcatalyst-sdk auto-authenticates as
App Administrator only when running inside a deployed Function. Running it
as a standalone local script would require manually generating OAuth refresh
tokens — more setup than it's worth for a one-time data load.
"""

import zcatalyst_sdk as zcatalyst

BUCKET_NAME = "kaavalai-bulk-data"

# Load order matters — parents before children, so FK lookups resolve.
# fk_mapping tells Catalyst which local column maps to which column in the
# already-loaded reference table (only needed where a Foreign Key column exists).
LOAD_PLAN = [
    # (csv_filename, table_name, fk_mapping)
    ("State.csv", "State", []),
    ("UnitType.csv", "UnitType", []),
    ("Rank.csv", "Rank", []),
    ("Designation.csv", "Designation", []),
    ("CaseCategory.csv", "CaseCategory", []),
    ("GravityOffence.csv", "GravityOffence", []),
    ("CrimeHead.csv", "CrimeHead", []),
    ("Act.csv", "Act", []),
    ("CaseStatusMaster.csv", "CaseStatusMaster", []),
    ("CasteMaster.csv", "CasteMaster", []),
    ("ReligionMaster.csv", "ReligionMaster", []),
    ("OccupationMaster.csv", "OccupationMaster", []),

    ("District.csv", "District", [{"local_column": "StateID", "reference_column": "StateID"}]),
    ("Section.csv", "Section", [{"local_column": "ActCode", "reference_column": "ActCode"}]),
    ("CrimeSubHead.csv", "CrimeSubHead", [{"local_column": "CrimeHeadID", "reference_column": "CrimeHeadID"}]),
    ("CrimeHeadActSection.csv", "CrimeHeadActSection", [
        {"local_column": "CrimeHeadID", "reference_column": "CrimeHeadID"},
        {"local_column": "ActCode", "reference_column": "ActCode"},
    ]),

    ("Court.csv", "Court", [{"local_column": "DistrictID", "reference_column": "DistrictID"}]),
    ("Unit.csv", "Unit", [
        {"local_column": "TypeID", "reference_column": "UnitTypeID"},
        {"local_column": "DistrictID", "reference_column": "DistrictID"},
    ]),

    ("Employee.csv", "Employee", [
        {"local_column": "UnitID", "reference_column": "UnitID"},
        {"local_column": "DistrictID", "reference_column": "DistrictID"},
        {"local_column": "RankID", "reference_column": "RankID"},
        {"local_column": "DesignationID", "reference_column": "DesignationID"},
    ]),

    ("CaseMaster.csv", "CaseMaster", [
        {"local_column": "PolicePersonID", "reference_column": "EmployeeID"},
        {"local_column": "PoliceStationID", "reference_column": "UnitID"},
        {"local_column": "CaseCategoryID", "reference_column": "CaseCategoryID"},
        {"local_column": "GravityOffenceID", "reference_column": "GravityOffenceID"},
        {"local_column": "CrimeMajorHeadID", "reference_column": "CrimeHeadID"},
        {"local_column": "CrimeMinorHeadID", "reference_column": "CrimeSubHeadID"},
        {"local_column": "CaseStatusID", "reference_column": "CaseStatusID"},
        {"local_column": "CourtID", "reference_column": "CourtID"},
        {"local_column": "DistrictID", "reference_column": "DistrictID"},
    ]),
    ("ComplainantDetails.csv", "ComplainantDetails", [
        {"local_column": "CaseMasterID", "reference_column": "CaseMasterID"},
        {"local_column": "OccupationID", "reference_column": "OccupationID"},
        {"local_column": "ReligionID", "reference_column": "ReligionID"},
        {"local_column": "CasteID", "reference_column": "caste_master_id"},
    ]),
    ("Victim.csv", "Victim", [{"local_column": "CaseMasterID", "reference_column": "CaseMasterID"}]),
    ("Accused.csv", "Accused", [{"local_column": "CaseMasterID", "reference_column": "CaseMasterID"}]),
    ("ActSectionAssociation.csv", "ActSectionAssociation", [
        {"local_column": "CaseMasterID", "reference_column": "CaseMasterID"},
    ]),
    ("ArrestSurrender.csv", "ArrestSurrender", [
        {"local_column": "CaseMasterID", "reference_column": "CaseMasterID"},
        {"local_column": "ArrestSurrenderStateId", "reference_column": "StateID"},
        {"local_column": "ArrestSurrenderDistrictId", "reference_column": "DistrictID"},
        {"local_column": "PoliceStationID", "reference_column": "UnitID"},
        {"local_column": "IOID", "reference_column": "EmployeeID"},
        {"local_column": "CourtID", "reference_column": "CourtID"},
        {"local_column": "AccusedMasterID", "reference_column": "AccusedMasterID"},
    ]),
    ("ChargesheetDetails.csv", "ChargesheetDetails", [
        {"local_column": "CaseMasterID", "reference_column": "CaseMasterID"},
        {"local_column": "PolicePersonID", "reference_column": "EmployeeID"},
    ]),
]


def handler(context, basicio):
    """
    Basic I/O functions have a hard 30-second execution limit, so this does NOT
    loop over all 26 tables or poll for completion in one call — both would
    time out. Instead, call this once PER TABLE, using query parameters:

    Mode 1 — start a table's load (fires the job, returns immediately):
        ?action=start&table_index=0
        (table_index 0-25, matching LOAD_PLAN order below)

    Mode 2 — check whether that table's load finished before starting the next:
        ?action=status&table_index=0&job_id=<job_id from Mode 1's response>

    Usage: call action=start for table_index=0, wait ~10-20s (longer for
    CaseMaster, which has 6000 rows), call action=status to confirm
    "Completed", THEN call action=start for table_index=1, and so on — table
    order matters because later tables' Foreign Keys reference earlier ones.
    """
    import json
    app = zcatalyst.initialize()
    datastore = app.datastore()

    action = basicio.get_argument("action") or "start"
    table_index = int(basicio.get_argument("table_index") or 0)

    if table_index < 0 or table_index >= len(LOAD_PLAN):
        basicio.write(json.dumps({"status": "failure", "reason": f"table_index must be 0-{len(LOAD_PLAN)-1}"}))
        context.close()
        return

    csv_file, table_name, fk_mapping = LOAD_PLAN[table_index]

    try:
        if action == "start":
            object_details = {"bucket_name": BUCKET_NAME, "object_key": csv_file}
            bulk_write = datastore.table(table_name).bulk_write()
            job = bulk_write.create_job(object_details, {
                "operation": "insert",
                "fk_mapping": fk_mapping,
            })
            job_id = job.get("job_id") or job.get("jobId")
            basicio.write(json.dumps({
                "status": "success", "table_index": table_index, "table_name": table_name,
                "job_id": job_id, "next_step": "call action=status with this job_id to check progress",
            }))

        elif action == "status":
            job_id = basicio.get_argument("job_id")
            bulk_write = datastore.table(table_name).bulk_write()
            status = bulk_write.get_status(job_id)
            state = status.get("status")
            response = {"status": "success", "table_index": table_index, "table_name": table_name, "job_state": state}
            if state == "Failed":
                response["error_detail"] = bulk_write.get_result(job_id)
            basicio.write(json.dumps(response))

        elif action == "result":
            # Detailed row-level result — use this even when job_state showed
            # "Completed", since that alone doesn't confirm rows actually
            # inserted (e.g. a column-name mismatch can silently produce 0 rows).
            job_id = basicio.get_argument("job_id")
            bulk_write = datastore.table(table_name).bulk_write()
            result = bulk_write.get_result(job_id)
            basicio.write(json.dumps({
                "status": "success", "table_index": table_index, "table_name": table_name,
                "result_detail": result,
            }))

        elif action == "direct_insert_section":
            # Bypasses Stratus/bulk-write entirely for this one small table (11 rows).
            # NOTE: ActCode is a Foreign Key column — direct insert_rows() likely needs
            # the referenced Act row's actual ROWID, not the natural key "IPC"/"NDPS"/
            # "IT_ACT" (bulk-write's fk_mapping would normally resolve this for you).
            zcql = app.zcql()
            act_rows = zcql.execute_query("SELECT ROWID, ActCode FROM Act")
            act_rowid_by_code = {r["Act"]["ActCode"]: r["Act"]["ROWID"] for r in act_rows}

            rows_raw = [
                {"SectionMasterID": 1, "ActCode": "IPC", "SectionCode": "302", "SectionDescription": "Murder", "Active": 1},
                {"SectionMasterID": 2, "ActCode": "IPC", "SectionCode": "307", "SectionDescription": "Attempt to Murder", "Active": 1},
                {"SectionMasterID": 3, "ActCode": "IPC", "SectionCode": "379", "SectionDescription": "Theft", "Active": 1},
                {"SectionMasterID": 4, "ActCode": "IPC", "SectionCode": "392", "SectionDescription": "Robbery", "Active": 1},
                {"SectionMasterID": 5, "ActCode": "IPC", "SectionCode": "420", "SectionDescription": "Cheating", "Active": 1},
                {"SectionMasterID": 6, "ActCode": "IPC", "SectionCode": "304B", "SectionDescription": "Dowry Death", "Active": 1},
                {"SectionMasterID": 7, "ActCode": "IPC", "SectionCode": "354", "SectionDescription": "Assault on Woman with Intent to Outrage Modesty", "Active": 1},
                {"SectionMasterID": 8, "ActCode": "NDPS", "SectionCode": "20", "SectionDescription": "Possession of Cannabis", "Active": 1},
                {"SectionMasterID": 9, "ActCode": "NDPS", "SectionCode": "21", "SectionDescription": "Possession of Manufactured Drugs", "Active": 1},
                {"SectionMasterID": 10, "ActCode": "IT_ACT", "SectionCode": "66C", "SectionDescription": "Identity Theft", "Active": 1},
                {"SectionMasterID": 11, "ActCode": "IT_ACT", "SectionCode": "66D", "SectionDescription": "Cheating by Personation using Computer", "Active": 1},
            ]

            missing_codes = set(r["ActCode"] for r in rows_raw) - set(act_rowid_by_code.keys())
            if missing_codes:
                basicio.write(json.dumps({
                    "status": "failure",
                    "reason": f"Act table is missing rows for ActCode(s): {missing_codes}. "
                              f"Act table currently has: {list(act_rowid_by_code.keys())}",
                }))
                context.close()
                return

            rows = []
            for r in rows_raw:
                row = dict(r)
                row["ActCode"] = act_rowid_by_code[r["ActCode"]]
                rows.append(row)

            section_table = datastore.table("Section")
            result = section_table.insert_rows(rows)
            basicio.write(json.dumps({"status": "success", "inserted": result,
                                       "act_rowid_mapping_used": act_rowid_by_code}))

        else:
            basicio.write(json.dumps({"status": "failure", "reason": "action must be 'start' or 'status'"}))

    except Exception as e:
        basicio.write(json.dumps({"status": "failure", "reason": str(e)}))

    context.close()