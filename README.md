# KaavalAI — Complete Package

Everything for the Datathon 2026 submission, in one place.

```
KaavalAI_Complete/
├── README.md                  ← you are here
├── generate_dataset.py        ← builds the synthetic ER-schema dataset
├── analytics_engine.py        ← hotspot/network/risk analytics
├── app.py                     ← the Streamlit dashboard
├── requirements.txt
├── data/                      ← pre-generated CSVs (ready to run immediately)
└── catalyst_cloud_deployment/ ← for later: deploying to Zoho Catalyst
```

## Fastest path: just run it (data is already generated)

```bash
pip install -r requirements.txt
streamlit run app.py
```

That's it — `app.py` reads from the `data/` folder by default. It'll open
at `http://localhost:8501`.

## If you want to regenerate the data yourself

Useful if you tweak the generator (different district weights, more
records, etc.) or just want to see the pipeline run.

```bash
pip install -r requirements.txt
python3 generate_dataset.py     # writes 26 CSVs into ./data
python3 analytics_engine.py     # reads them, writes hotspots/network/risk outputs into ./data
streamlit run app.py            # reads everything from ./data
```

Regenerating takes under a minute total — `generate_dataset.py` builds
~6,000 FIRs and related records; `analytics_engine.py` runs DBSCAN
clustering, network analysis, and trains the risk-scoring model.

## Changing where data lives

Both scripts and the app respect an environment variable if you'd rather
point them somewhere else:

```bash
export KAAVALAI_DATA_DIR=/some/other/path
python3 generate_dataset.py
python3 analytics_engine.py
streamlit run app.py
```

## What's in `catalyst_cloud_deployment/`

The separate package for actually deploying this to Zoho Catalyst (Data
Store, Authentication, QuickML, AppSail) for the hackathon's mandatory
Catalyst requirement. Has its own `DEPLOYMENT_GUIDE.md` — that's a
different, later step from just running the app locally. Ignore this
folder entirely if you only want to demo locally.

## Known limitations (worth mentioning to judges, not hiding)

- Data is synthetic (Faker-generated), matching the official ER schema's
  structure and CrimeNo/CaseNo format, but not real KSP records.
- Zia AutoML, Zia Services (voice/Kannada), SmartBrowz (PDF export), and
  RAG-over-case-narratives are documented as planned Catalyst integrations
  but not built — see `catalyst_cloud_deployment/DEPLOYMENT_GUIDE.md` for
  the full deferred list and reasoning.
- The Catalyst integration code (Data Store, Auth, QuickML) has been
  written against documented SDK patterns but not executed against a live
  Catalyst account.
