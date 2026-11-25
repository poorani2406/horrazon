# Problem 1 – Meridian Threads ETL (Windows)

## 1. Install
Install Python 3.10+ and PostgreSQL 14+. In pgAdmin create an empty database named `meridian`.

Open this folder in VS Code. In PowerShell:
```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```
Edit `.env` and replace `YOUR_PASSWORD` with your PostgreSQL password.

## 2. Generate sample data
```powershell
python -m src.generate_data
```
This creates Ads JSON, two CRM CSV files (UTF-8 BOM and multilingual names) and Store JSON with duplicate order versions, paise and renamed phone field.

## 3. Start the mock API
In terminal 1:
```powershell
uvicorn src.mock_ads_api:app --reload
```
Open http://127.0.0.1:8000/docs to test it.

## 4. Run the ETL
In terminal 2:
```powershell
python -m src.run_pipeline
```
The pipeline creates tables automatically and prints source counts and final table counts.

## 5. Test
```powershell
python -m pytest -q
```

## 6. Verify in pgAdmin
```sql
SELECT * FROM mart.pipeline_runs ORDER BY started_at DESC;
SELECT * FROM mart.dim_campaign;
SELECT * FROM mart.fact_ad_spend_daily;
SELECT * FROM mart.fact_leads;
SELECT * FROM mart.fact_orders;
SELECT * FROM mart.fact_order_items;
SELECT * FROM mart.rejected_rows;
```
Run the pipeline a second time. CRM files are skipped using `mart.processed_files`; Ads use a saved `updated_at` watermark and upsert by campaign/platform/date; orders are re-read and upserted by order ID. Rejected records use a stable fingerprint so reruns do not duplicate rejects. Final fact counts and totals should stay unchanged.

## Architecture
Ads API / CRM CSV / Store JSON -> Extract -> RAW (original JSON) -> STAGING (typed/cleaned) -> validation + dedupe -> MART (dimensions and facts) -> dashboard / ML / Pogee.

## Design decisions
- `Decimal` in Python and `NUMERIC` in PostgreSQL prevent floating-point money errors.
- All timestamps are stored as timezone-aware timestamps. Naive CRM timestamps are interpreted as India time.
- Phone is normalized to 10 digits. Missing/invalid phones remain unmatched, not dropped.
- Latest `updated_at` wins for corrected ad-day rows and order versions.
- Lead ID is the CRM deduplication key; order ID is the order deduplication key.
- Invalid rows go to `mart.rejected_rows` with rule, reason and original JSON.
- Campaign matching uses normalized exact UTM campaign names. Fuzzy matching is avoided to prevent false attribution.

## Honest limitations to explain
This is a beginner-scale runnable implementation. Ads API supports `updated_after`; the pipeline saves the latest successful timestamp in `mart.watermarks`. Store JSON is re-read on each run and deduplicated by latest update; CRM files are incremental via processed-file ledger. Add an explicit API `updated_since` endpoint and persisted watermark for production. The paise heuristic is only a sample-data rule; production should receive a currency-unit field. Add more validation rules and large-file chunking before scaling to the assessment's full volume.
