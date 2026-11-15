# SupeRR Intelligence

A private, reproducible scouting dashboard for SupeRR Selector Season 2. The frozen analysis profiles players in regulation IPL and T20I matches. It uses 2022 as a historical reference and scores 2023 through the last date in the supplied pack. No API key, network data provider or database service is required.

## Open the dashboard

Install Node.js 20 or later. In this directory run `npm run dev`, then open http://localhost:3000. The Node server reads the analysis snapshot at startup and serves the dashboard, API, season splits and downloadable competition materials. Restart it after replacing the data. The app also builds as a single ES-module Worker with `npm run build`.

## Reproduce the freeze

Use Python 3.11+ and the original organiser archive. Unzip it and use the folder containing ball_by_ball.csv and the five supporting CSVs. The raw pack is distributed separately by the organiser.

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
OPENBLAS_NUM_THREADS=1 python pipeline.py "/path/to/Data Pack" data/snapshot.json
python splits.py "/path/to/Data Pack" data
python unstop.py
python -m unittest -v test_pipeline
npm test
```

The delivered freeze is 0631d158d463. The identifier is the first 12 hex digits of SHA-256 over the canonical sorted-key snapshot before adding its freeze field. Source hashes are recorded in the audit. The historical report and deck in files/ belong to this freeze. New data or changes to the model require new report exports. Input dates, identities and format come from the organiser. Manual auction eligibility is separate from qualification under the model.

## API

| Route | Response |
| --- | --- |
| GET /api/health | Service status and freeze |
| GET /api/snapshot | Players, fit configuration, validation and audit |
| GET /api/methodology | Configuration, QA counts and validation |
| GET /api/rankings?role=bat | Top ten in order. Use bowl for bowling or omit role for both |
| GET /api/players?role=bowl&q=bumrah | Case-insensitive name search, including players below the gates |
| GET /api/players/bowl/{id} | One player's bowling profile |
| GET /api/splits/bowl/{id} | Reconciled year, league and pressure/ordinary observations |
| GET /api/export.csv | Frozen top tens, optionally filtered by role |
| GET /files/brief.pptx | Editable competition presentation |
| GET /files/report.pdf | Methodology and cohort appendix |
| GET /files/unstop.txt | Manual Unstop entry order |

Each role uses its own player ID and eligibility calculation. An absent rank denotes insufficient exposure. A missing alternate rank denotes failure of eligibility under that rule. Scores are rounded for display after sorting unrounded values. The two roles use different ledgers and score scales.
