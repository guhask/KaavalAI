"""
KaavalAI - Natural Language Query Function (QuickML LLM Serving)
Deploy as a Catalyst Serverless (Advanced I/O) Python function, e.g. "nl_query".

Design choice: QuickML's RAG/Knowledge Base is document-retrieval (PDF/DOCX/TXT
chunks + semantic search) — a good fit for unstructured text like case
BriefFacts narratives, but NOT the right tool for structured questions like
"how many thefts in Mysuru last month", which need an actual database query.

So this function uses QuickML's LLM Serving (Qwen 2.5-14B-Instruct chat
endpoint) as a text-to-ZCQL translator instead:
  1. User's NL question + our schema summary -> LLM generates a ZCQL SELECT
  2. Function executes that ZCQL against Data Store
  3. Results (+ original question) -> LLM again to phrase a natural-language
     answer, so the investigator gets prose, not a raw row dump

CAVEAT (flagged honestly): I could not test this against a live QuickML
endpoint — catalyst.zoho.com isn't reachable from my sandbox. The REST call
shape below (headers, payload keys) is assembled from Catalyst's documented
patterns but should be verified against the exact endpoint snippet Catalyst
generates for you in the console before relying on it.

Console setup required first:
  1. QuickML -> LLM Serving -> select Qwen 2.5-14B-Instruct -> copy its
     endpoint URL and X-QUICKML-ENDPOINT-KEY.
  2. Generate a Zoho OAuth token with scope QuickML.deployment.READ.
  3. Store both as Catalyst environment variables (QUICKML_ENDPOINT_URL,
     QUICKML_ENDPOINT_KEY, ZOHO_OAUTH_TOKEN) rather than hardcoding.

Future extension (deferred, documented not built): feed CaseMaster.BriefFacts
text into QuickML's Knowledge Base + RAG to power "find similar past cases"
(Challenge 01's Investigator Decision Support requirement) — genuinely a
document-retrieval problem, unlike the structured queries this function
handles.
"""

import json
import os
import requests
import zcatalyst_sdk as zcatalyst

QUICKML_ENDPOINT_URL = os.environ.get("QUICKML_ENDPOINT_URL", "")
QUICKML_ENDPOINT_KEY = os.environ.get("QUICKML_ENDPOINT_KEY", "")
ZOHO_OAUTH_TOKEN = os.environ.get("ZOHO_OAUTH_TOKEN", "")
CATALYST_ORG = os.environ.get("CATALYST_ORG", "")

# Trimmed schema summary — enough for the LLM to write correct ZCQL without
# needing all 26 tables (only the ones useful for typical investigator questions).
SCHEMA_SUMMARY = """
CaseMaster(CaseMasterID, CrimeNo, CaseNo, CrimeRegisteredDate, PoliceStationID,
  CaseCategoryID, GravityOffenceID, CrimeMajorHeadID, CrimeMinorHeadID,
  CaseStatusID, DistrictID, latitude, longitude, BriefFacts)
District(DistrictID, DistrictName)
CrimeHead(CrimeHeadID, CrimeGroupName)
CrimeSubHead(CrimeSubHeadID, CrimeHeadName)
CaseStatusMaster(CaseStatusID, CaseStatusName)
GravityOffence(GravityOffenceID, LookupValue)
Accused(AccusedMasterID, CaseMasterID, AccusedName, AgeYear, GenderID)
Victim(VictimMasterID, CaseMasterID, VictimName, AgeYear, GenderID)

Join CaseMaster.DistrictID -> District.DistrictID for district names.
Join CaseMaster.CrimeMajorHeadID -> CrimeHead.CrimeHeadID for crime type names.
Join CaseMaster.CaseStatusID -> CaseStatusMaster.CaseStatusID for status names.
"""

SYSTEM_PROMPT = f"""You are a query translator for the Karnataka Police crime database.
Given an investigator's natural language question, output ONLY a valid ZCQL
SELECT query (no explanation, no markdown fences) that answers it, using this schema:

{SCHEMA_SUMMARY}

Rules:
- Only SELECT statements. Never INSERT, UPDATE, DELETE.
- Use JOINs to resolve names (district, crime type, status) rather than raw IDs.
- Add a reasonable LIMIT (e.g. 50) unless the question asks for a count/aggregate.
"""


def call_quickml_llm(prompt, max_tokens=300, temperature=0.2):
    """Generic call to the QuickML LLM Serving chat endpoint."""
    headers = {
        "X-QUICKML-ENDPOINT-KEY": QUICKML_ENDPOINT_KEY,
        "Authorization": f"Zoho-oauthtoken {ZOHO_OAUTH_TOKEN}",
        "CATALYST-ORG": CATALYST_ORG,
        "Environment": "Development",
        "Content-Type": "application/json",
    }
    payload = {
        "prompt": prompt,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    resp = requests.post(QUICKML_ENDPOINT_URL, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    # Response key name is unverified against a live endpoint — check the
    # console's sample response and adjust if it differs (e.g. "text",
    # "generated_text", "choices"[0]["message"]["content"]).
    return data.get("response") or data.get("text") or str(data)


def handler(context, basicio):
    app = zcatalyst.initialize(context)
    req_body = json.loads(basicio.get_request().get_body() or "{}")
    user_question = req_body.get("question", "").strip()

    if not user_question:
        basicio.write(json.dumps({"status": "failure", "reason": "question is required"}))
        return

    if not QUICKML_ENDPOINT_URL:
        basicio.write(json.dumps({
            "status": "failure",
            "reason": "QuickML endpoint not configured — set QUICKML_ENDPOINT_URL etc. as env vars",
        }))
        return

    try:
        # Step 1: NL question -> ZCQL
        translation_prompt = f"{SYSTEM_PROMPT}\n\nQuestion: {user_question}\nZCQL:"
        zcql_query = call_quickml_llm(translation_prompt, max_tokens=150).strip()

        # Basic safety check before executing anything the LLM produced
        if not zcql_query.upper().startswith("SELECT"):
            basicio.write(json.dumps({
                "status": "failure", "reason": "Model did not return a SELECT query",
                "raw_output": zcql_query,
            }))
            return

        # Step 2: execute the generated ZCQL
        zcql = app.zcql()
        rows = zcql.execute_query(zcql_query)

        # Step 3: results -> natural language summary
        summary_prompt = (
            f"The investigator asked: '{user_question}'\n"
            f"The database returned {len(rows)} row(s): {json.dumps(rows[:10])}\n"
            f"Write a concise 2-3 sentence natural-language answer for the investigator."
        )
        nl_answer = call_quickml_llm(summary_prompt, max_tokens=200)

        basicio.write(json.dumps({
            "status": "success",
            "answer": nl_answer,
            "generated_zcql": zcql_query,
            "row_count": len(rows),
            "rows": rows[:50],
        }))

    except Exception as e:
        basicio.write(json.dumps({"status": "failure", "reason": str(e)}))
