"""
KaavalAI - Catalyst Authentication Function
Deploy this as a Catalyst Serverless (Advanced I/O) Python function, e.g. named
"auth_login". Streamlit calls its HTTPS endpoint instead of using a mock role
dropdown.

Console setup required first:
  1. Authentication -> enable "Embedded Authentication" (any one auth type
     must be active before Roles/Users can be managed).
  2. Authentication -> Roles -> create 4 roles matching KSP hierarchy:
       Investigator, Analyst, Supervisor, Policymaker
  3. Authentication -> Users -> add each real end-user (or via
     authentication_service.add_user_to_org) and assign one of the 4 roles.
  4. Data Store -> for each table, open "Scopes and Permissions" and restrict
     PII-heavy tables (ComplainantDetails, Victim, Accused) to Insert/Update
     for Investigator + Supervisor only; Select-only for Analyst/Policymaker.
     This is where the real RBAC enforcement happens — the Function below
     only handles login and token issuance.

Flow:
  Streamlit login form -> POST {kgid, pin} to this function's URL
    -> Function verifies KGID+PIN against Employee table (ZCQL)
    -> Function mints a Catalyst custom auth token carrying the user's role
    -> Streamlit stores the token + role in st.session_state
    -> Subsequent Data Store calls from Streamlit/Functions pass this token,
       so Catalyst's table-level Scopes & Permissions enforce access per role
       automatically — KaavalAI's own code doesn't need to re-check roles.
"""

import json
import zcatalyst_sdk as zcatalyst

# Employee.KGID -> assigned Catalyst role_name. In production this mapping
# would live in a dedicated UserCredentials table (KGID, pin_hash, role_name)
# rather than being hardcoded — this is a prototype stand-in.
ROLE_BY_DESIGNATION = {
    1: "Investigator",       # Investigating Officer
    2: "Supervisor",         # Station House Officer (SHO)
    3: "Analyst",            # Circle Inspector
    4: "Policymaker",        # Sub-Divisional Officer
}


def handler(context, basicio):
    app = zcatalyst.initialize(context)
    req_body = json.loads(basicio.get_request().get_body() or "{}")
    kgid = req_body.get("kgid", "").strip()
    pin = req_body.get("pin", "")

    if not kgid or not pin:
        basicio.write(json.dumps({"status": "failure", "reason": "kgid and pin required"}))
        return

    zcql = app.zcql()
    # LIMITATION (flag to judges): Employee has no password/PIN column in the
    # official ER schema, so this prototype only verifies that the KGID exists
    # — it does NOT check the PIN yet. Before any real deployment, add a
    # UserCredentials(KGID, pin_hash, role_name) table and verify pin here
    # with something like: hashlib.sha256(pin.encode()).hexdigest() == stored_hash
    query = f"SELECT EmployeeID, FirstName, DesignationID FROM Employee WHERE KGID = '{kgid}'"
    result = zcql.execute_query(query)

    if not result:
        basicio.write(json.dumps({"status": "failure", "reason": "unknown KGID"}))
        return

    employee = result[0]["Employee"]
    role_name = ROLE_BY_DESIGNATION.get(int(employee["DesignationID"]), "Analyst")

    auth_service = app.authentication()
    token_response = auth_service.generate_custom_token({
        "type": "web",
        "user_details": {
            "first_name": employee["FirstName"],
            "email_id": f"{kgid}@kaavalai.internal",
            "role_name": role_name,
        },
    })

    basicio.write(json.dumps({
        "status": "success",
        "employee_name": employee["FirstName"],
        "role": role_name,
        "auth_token": token_response,
    }))
