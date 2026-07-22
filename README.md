# KaavalAI — AI-Driven Crime Analytics & Visualization Platform

**Datathon 2026 · Karnataka State Police · Challenge 02**

KaavalAI ("Kaaval" = vigil/guard in Kannada) is an AI-driven crime analytics
and conversational intelligence platform built for Karnataka Police —
hotspot detection, criminal network analysis, predictive risk scoring, and
natural language querying over crime records, built on the official KSP FIR
ER schema and deployed natively on Zoho Catalyst.

**Live demo:** https://kaavalai-dashboard-50044016067.development.catalystappsail.in
**Demo video:** [add your video link here]

---

## Features

- 🗺️ **Spatiotemporal hotspot detection** — DBSCAN clustering on FIR coordinates, grouped by district + crime type
- 🕸️ **Criminal network analysis** — graph-based detection of organized crime groups and repeat-offender networks, with centrality scoring
- 📈 **Trend & anomaly alerts** — recent vs. baseline crime-rate comparison, flagged Red Alert / Elevated / Watch / Stable
- 🎯 **Explainable risk forecasting** — district-level predictive risk scores with visible feature importances (audit-traceable, not a black box)
- 💬 **Natural language query** — ask questions like "violent cases in Bengaluru" and get filtered, real-time results
- 🔗 **Similar Past Cases** — structured similarity matching (crime subtype, district, gravity, shared accused network) surfaced alongside NL query results, giving investigators a concrete lead rather than just a record list
- 🌐 **Kannada language toggle** — EN/ಕನ್ನಡ switch for all UI labels
- ⬇️ **CSV export** — download filtered FIR records or NL query results directly

## Note on Similar Past Cases

`BriefFacts` in this synthetic dataset is Faker-generated Lorem Ipsum, not
real narrative text — so similarity is computed on structured fields (crime
subtype, district, gravity, case status, shared accused) rather than text
similarity, which would have produced meaningless-but-plausible-looking
matches on fake prose. This is likely still the right approach even with
real KSP narrative text, since structured similarity is more auditable than
free-text matching for investigative use.

## Why Flask, not Streamlit

This started as a Streamlit app. After deploying to Zoho Catalyst AppSail,
the dashboard loaded but never rendered — Streamlit's UI depends entirely on
a persistent WebSocket connection for every update, and AppSail's reverse
proxy doesn't reliably support that. Flask has no such dependency (plain
HTTP request/response, full page reloads for filtering), and is one of
Zoho's own confirmed-working AppSail patterns, so the dashboard was rebuilt
on Flask — same features, same design, but actually renders in production.

## Tech Stack

- **Backend:** Python, Flask
- **Data processing:** Pandas, NumPy
- **Analytics:** scikit-learn (DBSCAN, RandomForest) — used offline in `analytics_engine.py` to precompute hotspots/networks/risk scores, not called live by the deployed app
- **Network analysis:** NetworkX
- **Visualization:** Plotly (self-contained interactive HTML, no client-side JS framework needed)
- **Deployment:** Zoho Catalyst — AppSail (Managed Runtime), Data Store (26-table relational schema matching KSP's official FIR ER diagram)

## Project Structure

```
KaavalAI/
├── app.py                 # Flask app — routes, chart builders, NL query logic
├── app-config.json        # Catalyst AppSail deployment config
├── requirements.txt       # Runtime dependencies (Flask, pandas, numpy, plotly, networkx)
├── templates/
│   └── dashboard.html     # Single-page dashboard template (Jinja2)
├── static/
│   ├── style.css          # Command-center dark theme
│   ├── favicon.ico
│   └── apple-touch-icon.png
├── data/                  # Synthetic dataset matching KSP's ER schema + precomputed analytics outputs
├── generate_dataset.py    # Builds the synthetic ER-schema-aligned dataset
├── analytics_engine.py    # Offline: hotspot clustering, network analysis, risk scoring
└── catalyst_cloud_deployment/   # Catalyst Functions (auth, NL query) — documented, deployment optional
```

## Running Locally

```bash
pip install -r requirements.txt
python3 app.py
```

Opens at `http://localhost:9000` (or the port set by `X_ZOHO_CATALYST_LISTEN_PORT`, defaults to 9000).

Data is pre-generated in `data/` — the app reads directly from those CSVs, no setup needed.

### Regenerating the dataset

```bash
python3 generate_dataset.py     # writes 26 CSVs into ./data
python3 analytics_engine.py     # runs DBSCAN/network analysis/risk model, writes outputs into ./data
python3 app.py
```

## Deploying to Zoho Catalyst AppSail

1. `catalyst init` (or `catalyst appsail:add` if already inside a project), select **Python 3.11**, **Catalyst-Managed Runtime**
2. Point the build path at this folder
3. `app-config.json` is already configured with a `predeploy` script that vendors dependencies into `./vendor` at deploy time (Catalyst's Python runtime does not auto-install `requirements.txt`, and the vendored packages must target the runtime's actual architecture — `--platform manylinux2014_x86_64 --implementation cp --python-version 3.11` — not whatever architecture the dependencies were originally installed for; this was one of several deployment issues worked through, see commit history)
4. `catalyst deploy`

## Data Store Schema

The full 26-table relational schema (matching Karnataka Police's official
FIR ER diagram — `CaseMaster`, `Accused`, `Victim`, `ComplainantDetails`,
`ArrestSurrender`, `ChargesheetDetails`, plus all lookup/master tables) is
documented in `catalyst_cloud_deployment/catalyst_datastore_schema.md`.
Data is currently loaded into Catalyst Data Store; the deployed dashboard
reads from a synchronized CSV snapshot rather than querying Data Store live
per request — a scoped decision given the submission timeline, with live
ZCQL querying documented as the next iteration.

## Known Limitations (documented, not hidden)

- Dataset is synthetic (Faker-generated), matching the real ER schema's
  structure and CrimeNo/CaseNo numbering format, not actual KSP records
- NL query uses keyword/synonym matching, not a full LLM — Catalyst QuickML
  integration is written and documented (`catalyst_cloud_deployment/`) but
  not wired into this deployment
- Kannada support is currently a UI text-label toggle only; Zia Services
  voice interaction (speech-to-text/text-to-speech) is documented as the
  next step, not built
- Zia AutoML and SmartBrowz (PDF export) are documented as planned
  integrations, not built — CSV export is implemented; PDF is not
- Authentication/RBAC is designed and documented (`catalyst_cloud_deployment/functions/auth_login`)
  but not wired into this deployment — deferred given submission timeline,
  see roadmap in the submission deck

## Team

**KaavalAI** — Datathon 2026, Challenge 02 (AI-Driven Crime Analytics & Visualization Platform)
