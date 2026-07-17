"""
KaavalAI - Catalyst Data Store Bulk Loader
Uploads each generated CSV to Catalyst Stratus, then triggers a Data Store
bulk-write job to populate the corresponding table.

Prerequisites:
  1. All 26 tables + columns already created in the Catalyst console per
     catalyst_datastore_schema.md (table/column creation has no programmatic API).
  2. `pip install zcatalyst-sdk`
  3. Run this from within a Catalyst Function, or locally with a service token
     (see Catalyst Python SDK setup docs for local/server-token auth).
  4. A Stratus bucket already created (e.g. "kaavalai-bulk-data").

Usage: python catalyst_bulk_load.py
"""

import os
import time
import zcatalyst_sdk as zcatalyst

DATA_DIR = "/mnt/user-data/outputs"
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


def upload_to_stratus(stratus, bucket_name, filepath):
    """Upload a local CSV to a Stratus bucket, return object details for bulk_write."""
    bucket = stratus.bucket(bucket_name)
    filename = os.path.basename(filepath)
    with open(filepath, "rb") as f:
        upload_response = bucket.upload_object(filename, f)
    return {
        "bucket_name": bucket_name,
        "object_key": filename,
        "version_id": upload_response.get("version_id"),
    }


def run_bulk_load(app):
    datastore = app.datastore()
    stratus = app.stratus()

    for csv_file, table_name, fk_mapping in LOAD_PLAN:
        filepath = os.path.join(DATA_DIR, csv_file)
        if not os.path.exists(filepath):
            print(f"  SKIP {table_name}: {csv_file} not found")
            continue

        print(f"Uploading {csv_file} to Stratus...")
        object_details = upload_to_stratus(stratus, BUCKET_NAME, filepath)

        print(f"Starting bulk write into {table_name}...")
        bulk_write = datastore.table(table_name).bulk_write()
        job = bulk_write.create_job(object_details, {
            "operation": "insert",
            "fk_mapping": fk_mapping,
        })
        job_id = job.get("job_id") or job.get("jobId")

        # Poll until the job finishes before moving to the next table (dependency order matters)
        while True:
            status = bulk_write.get_status(job_id)
            state = status.get("status")
            print(f"  {table_name} bulk write status: {state}")
            if state in ("Completed", "Failed", "PartiallyCompleted"):
                break
            time.sleep(5)

        if state == "Failed":
            print(f"  ERROR: {table_name} bulk write failed — check result for details before continuing.")
            result = bulk_write.get_result(job_id)
            print(result)
            break

    print("\nBulk load complete.")


if __name__ == "__main__":
    # Initialize Catalyst SDK — see docs.catalyst.zoho.com Python SDK setup for
    # local dev (service token) vs in-function (auto-initialized) auth.
    app = zcatalyst.initialize()
    run_bulk_load(app)
