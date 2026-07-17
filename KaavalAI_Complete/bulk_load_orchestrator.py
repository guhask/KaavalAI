"""
KaavalAI - Local Bulk Load Orchestrator

Runs on YOUR machine (not inside Catalyst) and drives the deployed
'bulk_loader' Basic I/O function through all 26 tables in the correct
dependency order, waiting for each table's bulk-write job to finish before
starting the next one.

Why this runs locally: it just makes plain HTTPS calls to your function's
public Function URL — no Catalyst SDK or auth token needed on this end,
since the function itself already handles Catalyst-side authentication.

Usage:
    pip install requests
    python bulk_load_orchestrator.py

Before running: set FUNCTION_BASE_URL below to your actual deployed
function URL (Console -> Functions -> bulk_loader -> copy the Function URL).
"""

import requests
import time
import sys
import json

# ---- SET THIS to your actual deployed function URL ----
FUNCTION_BASE_URL = "https://kaavalai-60078345314.development.catalystserverless.in/server/bulk_loader/execute"

# Must match the deployed function's LOAD_PLAN order exactly (26 tables, index 0-25)
TABLE_ORDER = [
    "State", "UnitType", "Rank", "Designation", "CaseCategory", "GravityOffence",
    "CrimeHead", "Act", "CaseStatusMaster", "CasteMaster", "ReligionMaster", "OccupationMaster",
    "District", "Section", "CrimeSubHead", "CrimeHeadActSection",
    "Court", "Unit",
    "Employee",
    "CaseMaster", "ComplainantDetails", "Victim", "Accused", "ActSectionAssociation",
    "ArrestSurrender", "ChargesheetDetails",
]

POLL_INTERVAL_SECONDS = 5
MAX_WAIT_SECONDS = 300  # 5 min cap per table before giving up and flagging it


def _unwrap(resp):
    """
    Catalyst's Function URL wraps a Basic I/O function's basicio.write() output
    inside an outer envelope: {"output": "<json string we wrote>", ...}.
    This unwraps that so callers get our actual dict directly.
    """
    outer = resp.json()
    if "output" not in outer:
        raise RuntimeError(f"Unexpected response shape (no 'output' key): {outer}")
    return json.loads(outer["output"])


def start_table_load(table_index):
    resp = requests.get(FUNCTION_BASE_URL, params={"action": "start", "table_index": table_index}, timeout=30)
    resp.raise_for_status()
    return _unwrap(resp)


def check_table_status(table_index, job_id):
    resp = requests.get(FUNCTION_BASE_URL,
                         params={"action": "status", "table_index": table_index, "job_id": job_id},
                         timeout=30)
    resp.raise_for_status()
    return _unwrap(resp)


def load_all_tables():
    for i, table_name in enumerate(TABLE_ORDER):
        print(f"\n[{i+1}/{len(TABLE_ORDER)}] Starting {table_name}...")

        try:
            start_result = start_table_load(i)
        except Exception as e:
            print(f"  FAILED to start {table_name}: {e}")
            print("  Stopping here — fix the issue and re-run (safe to re-run from this table).")
            sys.exit(1)

        if start_result.get("status") != "success":
            print(f"  FAILED to start {table_name}: {start_result}")
            sys.exit(1)

        job_id = start_result["job_id"]
        print(f"  job_id={job_id}, polling for completion...")

        elapsed = 0
        while elapsed < MAX_WAIT_SECONDS:
            time.sleep(POLL_INTERVAL_SECONDS)
            elapsed += POLL_INTERVAL_SECONDS

            status_result = check_table_status(i, job_id)
            state = status_result.get("job_state")
            print(f"    ...{elapsed}s elapsed, state={state}")

            if state == "Completed":
                print(f"  ✓ {table_name} loaded successfully.")
                break
            elif state in ("Failed", "PartiallyCompleted"):
                print(f"  ✗ {table_name} bulk write {state}. Detail: {status_result.get('error_detail')}")
                print("  Stopping here — check the table in Data Store console before continuing.")
                sys.exit(1)
        else:
            print(f"  ⚠ {table_name} still not complete after {MAX_WAIT_SECONDS}s.")
            print("  Check the Data Store console manually — this may just be a big table (e.g. CaseMaster)")
            print("  still processing. Re-run this script (it's safe to skip already-loaded tables by")
            print("  editing TABLE_ORDER) once you've confirmed its status.")
            sys.exit(1)

    print(f"\n✅ All {len(TABLE_ORDER)} tables loaded successfully.")


if __name__ == "__main__":
    if "your-project" in FUNCTION_BASE_URL:
        print("Set FUNCTION_BASE_URL at the top of this script to your actual deployed function URL first.")
        sys.exit(1)
    load_all_tables()
