# KaavalAI — Master Catalyst Deployment Guide

This is the single ordered checklist to go from what we've built to a live
Catalyst deployment. Each step references the file/doc already produced.

**Honesty check before you start:** every script here was written against
Catalyst's documented SDK/CLI patterns, but none of it has been executed
against a live account — `catalyst.zoho.com` isn't reachable from the
sandbox this was built in. Budget time to debug the first real run.

## 0. Prerequisites
- Node.js installed (for Catalyst CLI)
- `npm install -g zcatalyst-cli`
- `catalyst login`
- Claim Catalyst credits: https://catalyst.zoho.com/promotions.html?cn=KSPH26

## 1. Create the project
```
mkdir kaavalai-catalyst && cd kaavalai-catalyst
catalyst init
```
Select: AppSail (Catalyst-Managed Runtime, Python) for the client, and add
two Basic I/O Python functions (`auth_login`, `nl_query`) when prompted, or
add them after with:
```
catalyst function:add
```

## 2. Copy in the code
- `client/app.py`, `client/requirements.txt`, `client/app-config.json` →
  from this deliverable's `client/` folder
- `functions/auth_login/main.py`, `requirements.txt` → from `functions/auth_login/`
- `functions/nl_query/main.py`, `requirements.txt` → from `functions/nl_query/`

The CLI auto-generates each function's `catalyst-config.json` — don't
hand-write it; just let `catalyst function:add` create it, then drop our
`main.py` logic in.

## 3. Data Store (do this before anything else touches data)
1. Follow `catalyst_datastore_schema.md` — create all 26 tables/columns via
   console, in the 5 dependency tiers listed (lookups first).
2. Create a Stratus bucket named `kaavalai-bulk-data`.
3. Run `catalyst_bulk_load.py` to push all CSVs in. **Test on `State` and
   `District` first** (small, no dependencies) before running the full load.
4. Set table Scopes & Permissions per role (Investigator/Supervisor get
   Insert+Update on PII tables like Accused/Victim/ComplainantDetails;
   Analyst/Policymaker get Select-only).

## 4. Authentication
1. Console → Authentication → enable Embedded Authentication.
2. Create 4 Roles: Investigator, Analyst, Supervisor, Policymaker.
3. Add real end-users (or via `authentication_service.add_user_to_org`),
   assigning each the correct role.
4. Deploy the `auth_login` function (`catalyst deploy` covers this once
   it's in your project — see step 6).
5. Copy its Function URL into the client's environment variable
   `KAAVALAI_AUTH_URL` (Console → AppSail → Environment Variables).

## 5. QuickML
1. Console → QuickML → LLM Serving → select Qwen 2.5-14B-Instruct → copy
   its endpoint URL + `X-QUICKML-ENDPOINT-KEY`.
2. Generate a Zoho OAuth token with scope `QuickML.deployment.READ`.
3. Set these as environment variables on the `nl_query` function:
   `QUICKML_ENDPOINT_URL`, `QUICKML_ENDPOINT_KEY`, `ZOHO_OAUTH_TOKEN`,
   `CATALYST_ORG`.
4. **Verify the response JSON shape** against the console's sample response
   before trusting `call_quickml_llm()`'s parsing — this was our one
   explicitly-unverified assumption.
5. Copy the deployed function's URL into the client's
   `KAAVALAI_NL_QUERY_URL` environment variable.

## 6. Deploy
```
catalyst serve      # local smoke test first
catalyst deploy
```
This deploys the AppSail client and both functions together. Note the
AppSail URL and both function URLs from the CLI output.

## 7. Post-deploy checklist
- [ ] Open the AppSail URL — dashboard loads, 5 tabs render
- [ ] Log in with a real KGID+role via the sidebar — confirms `auth_login`
- [ ] Ask a question in "Ask KaavalAI" — confirms `nl_query`; if it falls
      back to local keyword search, the function URL or QuickML env vars
      need checking
- [ ] Spot-check a few Data Store tables in console match the CSV row
      counts (e.g. CaseMaster should show 6,000 rows)

## Deferred / documented-not-built
- **Zia AutoML** — risk scoring still runs on scikit-learn locally, not
  migrated. Fine for a prototype demo; revisit if shortlisted.
- **Zia Services (voice, Kannada)** — not started.
- **SmartBrowz (PDF export)** — not started.
- **QuickML RAG over `BriefFacts`** ("find similar past cases") — documented
  as the right future use of RAG, not built.

Be upfront about this list with judges — it reads as disciplined scoping
under a 16-day constraint, not as gaps to hide.
