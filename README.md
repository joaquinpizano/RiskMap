# RiskMap
🌊 [Launch the Interactive RiskMap Dashboard](https://riskmap-vtvvsxoqbp9nxxwal4rjkh.streamlit.app/)

RiskMap is a local Streamlit project for exploring historical FEMA National Flood Insurance Program (NFIP) claims, reported gross payments, geographic data quality, and provisional recorded-policy exposure in Pinellas County, Florida. It is descriptive insurance analytics, not a flood prediction, property-risk score, premium estimate, or validated claims-frequency model.

## What the pilot shows

Launch **`dashboard_pilot.py`** for the current pilot. `dashboard.py` is the separate historical dashboard.

- **Overview:** historical claim counts and nominal reported payments, filtered by loss year and HUD ZIP classification.
- **Geographic Analysis:** the saved ZCTA map, fixed-period ZIP severity rankings, and selected-ZIP comparisons. The map and severity periods are saved analyses, not a live reaggregation of every sidebar filter.
- **2024 ZIP Comparison:** a fixed year-of-loss comparison for ZIPs 33703, 33706, and 33708, including claims with all gross payment components missing. Sidebar filters do not change this tab.
- **2024 ZIP Comparison, separate exposure panel:** ZIP 33708 non-condominium recorded-policy exposure, showing the baseline and termination-only sensitivity. It is kept separate from the claims table.
- **Flood Hazard Context:** mapped FEMA NFHL Special Flood Hazard Area (SFHA) polygon coverage summarized for Census ZCTAs 33703, 33706, and 33708. This is separate from historical claims and provisional policy-record exposure.
- **2024 Exposure Pilot:** the older, fixed ZIP 33706 exploratory record-based pilot, with provenance checks and coverage groups kept separate. Its existing ratios are not validated property/contract claim rates.
- **Data & Methodology:** source descriptions and interpretation limits.

The current fixed claims comparison is:

| ZIP | 2024 claim records | All gross payment components missing | Nominal reported gross payments |
|---|---:|---:|---:|
| 33703 | 3,207 | 70 | $433,068,218.60 |
| 33706 | 4,060 | 113 | $603,902,216.78 |
| 33708 | 3,048 | 101 | $467,748,036.70 |

Payments sum known gross building, contents, and increased-cost-of-compliance (ICC) components for the loss year. Missing components are unknown, not reported zeros. Dollars are nominal, not inflation-adjusted, final settled losses, or cash disbursed exclusively during 2024. Claims come from the county-selected historical file and use reported ZIPs; a ZIP label does not independently establish a precise property location.

## Start from a fresh setup

The verified platform is **Windows / PowerShell with CPython 3.13.17**. Obtain the project code **and the saved data/report bundle** described below. A code-only checkout is insufficient for the complete pilot or data-backed tests.

Install CPython 3.13 with the Windows Python launcher, open PowerShell in the project root, and run:

```powershell
py -3.13 --version
py -3.13 -m venv .venv-pilot
.\.venv-pilot\Scripts\python.exe -m pip install streamlit==1.66.1 pandas==3.1.0 plotly==7.1.0 shapely pyshp pyproj
.\.venv-pilot\Scripts\python.exe -m streamlit run dashboard_pilot.py --server.address 127.0.0.1 --server.port 8501
```

Open **http://127.0.0.1:8501**. Stop the server with **Ctrl+C**. If that port is occupied, choose another with `--server.port 8502` and open the corresponding URL.

Activation is not required: explicitly using the environment's interpreter avoids PowerShell activation-policy issues. Do not recreate or overwrite an existing environment just to launch the app; use its interpreter directly. If `py` is unavailable, use the full path to your installed CPython executable for the first two commands. The `python` app-execution alias is not a reliable substitute on every Windows installation.

The first three direct dependencies match the working pilot environment. `shapely`, `pyshp`, and `pyproj` are needed to rebuild the saved NFHL summary and the existing SVG map; they are not needed just to display the prebuilt dashboard results. There is currently no dependency manifest or complete transitive lockfile; the install command is not a guarantee of identical future dependency resolution.

Linux/macOS setup and the Windows-style paths embedded in saved JSON manifests have not been validated. Do not assume the archived evidence verifier is portable unchanged.

## Inputs needed to display the pilot

Paths are relative to the project root. Preserve filenames and directory structure.

| Input | Used for |
|---|---|
| `data/processed/nfip_payments_by_year_hud_status.csv` | Required at startup; Overview and sidebar year/geography options. Missing this file stops the dashboard. |
| `data/processed/nfip_claims_by_year_zip.csv` | Fixed three-ZIP claims comparison and historical selected-ZIP comparison. |
| `data/processed/nfip_payments_by_zip_hud.csv` | HUD ZIP classification for historical ZIP comparison. |
| `data/processed/nfip_zip_loss_severity.csv` | Saved All Years / 2024 Only / Excluding 2024 ZIP rankings. |
| `reports/nfip_pinellas_zcta_map.svg` | Saved geographic display. |
| `reports/provisional_exposure_33706_2024.json` | ZIP 33706 provisional recorded exposure. |
| `reports/claims_policy_compatibility_33706_2024.json` | ZIP 33706 claim/exposure scope and completeness reconciliation. |
| `reports/pilot_record_metrics_33706_2024.json` | ZIP 33706 exploratory pilot metrics. |
| `reports/noncondo_cancellation_gap_addendum_33708_2024_2026-11-11/evidence.json` | Baseline, termination-only exposure, and input hashes for the new 33708 panel. |
| `reports/noncondo_denominator_validation_33708_2024_2026-11-11/calculation_evidence.json` | 33708 scenario validation, snapshot, and date exceptions. |
| `reports/exposure_sensitivity_33708_2024_2026-11-11/evidence.json` | Hash-linked exposure evidence required by the 33708 panel. |
| `reports/census_boundary_source_manifest.json` | Pinned Census archive URLs, sizes, SHA-256 values, and required ZIP members for geographic rebuilds. |
| `data/processed/nfhl_zcta_hazard_summary.csv` | FEMA mapped-hazard area summary for the three target Census ZCTAs. |
| `reports/nfhl_zcta_hazard_metadata.json` | NFHL map versions/effective dates, retrieval metadata, field definitions, method, and source hashes. |
| `data/raw/nfhl_zcta_hazard_YYYYMMDD/nfhl_zones_*.geojson` | Retrieved NFHL features retained as a raw snapshot for calculation review. |

The pilot checks saved report consistency. For example, the 33706 report chain must have matching hashes, scope, source dates, coverage groups, and arithmetic. Missing optional map/ranking/pilot inputs produce local warnings; the 2024 claims and 33708 exposure sections handle failures separately. Keep the full report bundle rather than copying isolated JSON files without their dependencies.

The runtime reads processed claims and saved reports; it does not download FEMA data when a visitor opens the dashboard.

## Where the inputs come from

### Raw source material

- **FEMA claims:** [NFIP Redacted Claims v3](https://www.fema.gov/openfema-data-page/nfip-redacted-claims-v3), available through the [OpenFEMA claims API](https://www.fema.gov/api/open/v3/NfipClaims). The local `data/raw/NFIP_Claims_Pinellas.csv` contains the FL / countyCode 12103 selection. Obtain the archived original for exact reproduction; there is no complete raw-claims acquisition command in this project. A current bulk export or fully paginated API query can support a new analysis, but a single default API page is not the complete cohort.
- **FEMA policies:** [NFIP Redacted Policies v3](https://www.fema.gov/openfema-data-page/nfip-redacted-policies-v3) and the [policy API](https://www.fema.gov/api/open/v3/NfipPolicies). `scripts/download_nfip_policies.py` downloads ZIP/effective-year cohorts with Pinellas GEOID prefix 12103, checks IDs/counts, and saves query/quality metadata. Its county filter excludes missing GEOIDs; it is not sufficient by itself for the missing-GEOID sensitivity or all earlier overlapping terms.
- **HUD crosswalk:** [HUD–USPS ZIP Code Crosswalk Files](https://www.huduser.gov/portal/datasets/usps_crosswalk.html). The saved input is `data/raw/ZIP-COUNTY_122025.xlsx`, the December 2025 ZIP-to-county workbook. Access may require a HUD account. The crosswalk does not establish historical claim locations.
- **Census geography:** [2025 TIGER/Line ZCTAs](https://www2.census.gov/geo/tiger/TIGER2025/ZCTA520/) and [counties](https://www2.census.gov/geo/tiger/TIGER2025/COUNTY/). The 529,118,424-byte ZCTA archive and 83,989,800-byte county archive are excluded from Git and restored by `scripts/download_census_boundaries.py` using the pinned `reports/census_boundary_source_manifest.json`. ZIPs and ZCTAs are different geographic constructs; the map clips polygons for display without allocating ZIP payments spatially.
- **FEMA mapped flood hazard:** the [FEMA National Flood Hazard Layer (NFHL) public ArcGIS service](https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer), using **Flood Hazard Zones (layer 28)** and its linked **Study_Info table (table 41)**. Layer 28 is a polygon layer in NAD83 geographic coordinates (EPSG:4269); `SFHA_TF`, `FLD_ZONE`, and `ZONE_SUBTY` describe mapped flood-zone categories. The linked study table supplies map effective dates (`INDX_EFFDT`) and database revision dates (`DBREV_DT`) by `DFIRM_ID` and `VERSION_ID`. The observed Pinellas County record is map `12103C`, version `2.4.3.2`, effective **August 24, 2021**, with database revision **November 5, 2026**. The target-ZCTA features also include version `12103C:1.1.1.0`, for which the linked table returned no effective date. RiskMap retains those features but marks that date unknown; it does not copy the newer version's date onto them. The generated manifest records all intersecting map versions and the retrieval timestamp; NFHL has no single effective date for every polygon in the country.
- **Other evidence:** `data/raw/MarketShareTsExternal.xlsx` is a Florida OIR market-share workbook inspected during benchmark research. It is not a matching 2024 NFIP benchmark or a dashboard dependency. Preserve it if reproducing the denominator-validation packet's input hashes.

The saved analytical snapshot uses row `asOfDate` **September 8, 2026**. Live API results and current source documents can change. Filtering today's API by that field is not a versioned archive or a way to recover a past release. If the archived bundle is missing, exact reproduction of its hashes and results is **not established**. Obtain it from the project maintainer or retain new retrievals as a separate analysis; do not replace historical evidence to force a check to pass.

### Transformation and report lineage

For understanding the pipeline, not as a safe startup checklist:

| Script | Outputs / purpose |
|---|---|
| `scripts/summarize_nfip.py` | Raw claims → year, ZIP, and year/ZIP summaries, including payment missingness. |
| `scripts/match_nfip_hud.py` | Raw claims + HUD workbook → ZIP/HUD audit and crosswalk report. |
| `scripts/build_nfip_geographic_payment_summary.py` | Raw claims + ZIP/HUD audit → geographic payment summaries. |
| `scripts/analyze_loss_concentration.py` and `scripts/analyze_zip_loss_severity.py` | Processed claims → annual concentration and ZIP severity files. |
| `scripts/map_nfip_zcta.py` | Processed payments + Census archives → SVG and map-coverage report. |
| `scripts/summarize_nfhl_hazard.py` | FEMA NFHL zone polygons + 2025 TIGER/Line Census ZCTAs → raw GeoJSON snapshot, mapped-hazard area CSV, and source/method manifest. |
| `scripts/calculate_provisional_exposure.py` | Cached 33706 effective-year cohorts → provisional calendar-year exposure. |
| `scripts/compare_claims_policy_exposure.py` and `scripts/calculate_pilot_record_metrics.py` | 33706 compatibility audit and existing exploratory metrics. |
| `scripts/audit_33708_policy_counts.py` | 33708 ID/geography/policyCount audit, with a new `--output` folder. |
| `scripts/exposure_sensitivity_33708.py` | Reuses the audited 2024 input; retrieves missing-GEOID rows and earlier terms potentially overlapping 2024. |
| `scripts/validate_noncondo_denominator_33708.py` | Saved-input non-condominium validation packet; requires separately collected documentation in its output folder. It is not a standalone fresh-download pipeline. |
| `scripts/explain_33708_cancellation_gap.py` | Saved non-condominium inputs → record-level cancellation-gap addendum. |

**Do not run all scripts blindly.** Older transformation/validation scripts can overwrite fixed processed-data/report paths, and some execute on import. Newer audit scripts generally require a new output path, but several also refer to specific existing dated folders. Inspect their CLI and source before rebuilding in a separate project copy. There is no single end-to-end, archive-restoring pipeline.

### Restore large Census boundaries

The two Census ZIP archives exceed GitHub's 50 MB review threshold and are deliberately not committed. Before rebuilding the ZCTA map or NFHL summary, or running the source-backed hazard test in a fresh checkout, run:

```powershell
.\.venv-pilot\Scripts\python.exe scripts/download_census_boundaries.py
```

The downloader reads `reports/census_boundary_source_manifest.json`, downloads only missing files, verifies each pinned byte length and SHA-256, checks required shapefile components and ZIP CRCs, and refuses to overwrite an existing file. The archives total about 613 MB. They are not needed to launch the dashboard when the saved outputs listed above are present.

### Rebuild the NFHL ZCTA summary

From the project root, with the geospatial packages installed and the saved `data/raw/tl_2025_us_zcta520.zip` archive present:

```powershell
.\.venv-pilot\Scripts\python.exe scripts/summarize_nfhl_hazard.py
```

This command makes read-only requests to the public FEMA service, checks the service schema and CRS, submits each exact Census ZCTA polygon as a spatial filter, clips returned features to that boundary, and writes:

- `data/processed/nfhl_zcta_hazard_summary.csv`
- `reports/nfhl_zcta_hazard_metadata.json`
- `data/raw/nfhl_zcta_hazard_YYYYMMDD/` containing one raw GeoJSON feature collection per ZCTA

The CSV, manifest, and raw snapshot commands refuse to overwrite existing files. For another retrieval, provide new paths, for example:

```powershell
.\.venv-pilot\Scripts\python.exe scripts/summarize_nfhl_hazard.py --summary-csv data/processed/nfhl_zcta_hazard_summary_20261113.csv --manifest-json reports/nfhl_zcta_hazard_metadata_20261113.json --raw-dir data/raw/nfhl_zcta_hazard_20261113
```

The FEMA service is live and can change; retain each raw snapshot and manifest together when comparing runs. The dashboard reads the saved CSV and manifest and does not call FEMA at page load.

The processor uses the 2020 Census ZCTA identifiers (`ZCTA5CE20`) as published in the 2025 TIGER/Line release. NFHL geometries and Census polygons are checked in EPSG:4269, clipped in that shared geographic CRS, and measured geodesically on the GRS80 ellipsoid. A separate EPSG:4269 to EPSG:26917 to EPSG:4269 round-trip check verifies the coordinate transformation. NFHL SFHA polygons (`SFHA_TF = T`) are unioned to avoid double-counting overlaps. The principal percentage is SFHA area divided by the **full Census ZCTA polygon area**. It is not a land-only percentage. Geodesic boundary segmentation can produce sub-square-meter overages; only within a strict 1e-7 relative tolerance, mapped/SFHA area is capped at its parent area and the exact adjustment is recorded in square meters. Larger differences fail validation. The CSV separately reports mapped coverage, non-SFHA area, unclassified area, areas not represented by NFHL zone polygons, and any T/F overlap. The manifest defines every field.

FEMA's Special Flood Hazard Area is a mapped regulatory category generally associated with the 1% annual-chance floodplain, not an observation that flooding occurred or a prediction for a particular parcel. This is the current NFHL retrieval, not a reconstruction of map panels as of each historical claim's loss date. Areas not represented by a returned zone polygon are not assumed flood-free and may include water or data gaps. Census ZCTAs approximate postal ZIPs but are not USPS delivery geographies. Claims remain grouped by FEMA's reported postal ZIP; there is no spatial allocation of a claim or policy record to these ZCTAs. Do not divide claims by mapped area or combine this summary with provisional exposure to create a claim rate.

## Run the existing verification checks

From the project root, with the archived inputs present:

```powershell
# Restore the ignored Census boundary archives before source-backed checks.
.\.venv-pilot\Scripts\python.exe scripts/download_census_boundaries.py

# Offline: source hashes, source dates, earlier-term counts, and saved exposure reproduction.
.\.venv-pilot\Scripts\python.exe scripts/verify_saved_exposure.py

# Full tests, including raw-claims reconciliation, NFHL source recheck, and Streamlit AppTest.
.\.venv-pilot\Scripts\python.exe -m unittest discover -s scripts -p 'test_*.py'

# Read-only checks of saved annual/ZIP totals and period/payment-share consistency.
.\.venv-pilot\Scripts\python.exe scripts/validate_zip_analysis.py
```

The first command uses the standard library only. The full test suite also needs the dashboard dependencies, raw claims CSV, cached cohorts, and saved reports; it is not a synthetic-data-only unit suite. Streamlit's bare-mode `missing ScriptRunContext` warning can occur during AppTest without a test failure. An incomplete historical smoke-test cohort is deliberately skipped by the exposure loader.

For the exposure verifier, retain:

- `data/raw/nfip_policy_33706_2023/2023/` and `data/raw/nfip_policy_33706_2024/2024/`, including `query.json`, `quality_report.json`, all `page_*.json`, and the terminal empty page;
- the original 33706 exposure JSON and its referenced hashes;
- the complete `reports/policy_audit_33708_2024_2026-11-11/` bundle, including downloaded pages and both API responses;
- the complete `reports/exposure_sensitivity_33708_2024_2026-11-11/` bundle, including saved responses and evidence.

The ZIP validator additionally reads `data/processed/nfip_loss_concentration_by_year.csv`. It prints `ALL VALIDATION CHECKS PASSED` on success, but **does not currently return a failing exit code for failed analytical checks**. Inspect its output; do not use its process status alone as a CI gate.

Passing checks establishes saved-input consistency and computational reproducibility, not independent insurance coverage validation.

## Why exposure remains provisional

- The method integrates recorded intervals over January 1, 2024 to January 1, 2025 and divides by **366 days**. Record-years are not established as unique contracts or properties. Insured-unit-years weight duration by `policyCount`; they remain distinct measures.
- IDs identify rows, renewals create separate records, and public data does not resolve all contract links or endorsement/transaction histories. Equal snapshot labels do not prove an immutable database revision.
- The 33708 baseline uses the earlier of cancellation and termination. Termination-only selection yields **3,087.9071** versus **2,982.6284** non-condominium record-years: **+105.2787 (+3.53%)**, attributable to 293 records with conflicting end dates. Neither convention independently establishes actual coverage.
- The same **11 non-condominium cancellations before effective date** are excluded from both of those scenarios. Ignoring their cancellation dates is a different sensitivity, not part of the 105.2787-year difference. The all-coverage 33708 report has 18 date exceptions; the older 33706 report has 19.
- Missing-GEOID records are not confirmed Pinellas exposure. Adding them to 33708 non-condominium exposure adds **3.1230 record-years (+0.1047%)** as a separate geographic sensitivity. Known out-of-county records remain out.
- No independent policies-in-force benchmark matching ZIP/county scope, non-condominium coverage, counting unit, and observation date has been verified. Even a future matching point-in-time count would not validate a full-year exposure integral by itself.
- The 33706 and 33708 exposure workflows have different completeness evidence; the old 33706 loader does not independently establish all earlier-overlap completeness. Keep their limitations visible.

See the saved [33708 denominator validation](reports/noncondo_denominator_validation_33708_2024_2026-11-11/report.md) and [record-level cancellation addendum](reports/noncondo_cancellation_gap_addendum_33708_2024_2026-11-11/addendum.md). The [FEMA FAQ](https://agents.floodsmart.gov/flood-maps-and-data/faqs-about-nfip-data) and saved v3 field definitions distinguish documented meanings from RiskMap assumptions.

## Why the three-ZIP comparison has no claim rates

It compares **claim records and nominal reported payment totals**, not exposed contracts or properties. A valid rate needs compatible numerator and denominator definitions, geographic screening, coverage types, observation periods, and verified exposure units. The claims table includes all coverage types and retains unknown payment values; the adjacent 33708 exposure panel is only non-condominium coverage with confirmed Pinellas GEOIDs. Dividing one by the other would mix scopes. Multiple loss events can also produce multiple claims in a year.

The separate older 33706 pilot already displays explicitly exploratory claims-per-record-year ratios. Their presence does not validate insurance frequency or authorize expanding rates to the fixed three-ZIP table.

## Verification status and limits

Repository audit baseline was run on **November 11, 2026**; the NFHL source build and new validation are dated **November 12, 2026 UTC**:

- Before the RiskMap v2 changes, **33 tests passed**, including the rendered pilot, fixed-filter behavior, exposure-panel failure isolation, and raw-claims reconciliation.
- The FEMA NFHL query completed for all three ZCTAs and its GeoJSON feature snapshots, summary CSV, and metadata manifest were retained. The source manifest records the `12103C:2.4.3.2` effective date and the separate `12103C:1.1.1.0` date gap. The final full suite passed: **41 tests**, including independent recomputation from retained inputs and Streamlit AppTest coverage.
- `scripts/verify_saved_exposure.py` passed for both saved 33706 and 33708 evidence chains. `scripts/validate_zip_analysis.py` reported all checks passed, including annual/ZIP payment reconciliation at **$3,754,344,375.65**.
- Fresh interpreter creation/dependency installation is checked separately below; `py`/`python` Windows app-execution aliases were inaccessible in the sandbox. The working `.venv-pilot\Scripts\python.exe` is CPython 3.13.17. The launcher prerequisite on another machine has not been demonstrated here.
- Other historical raw-source acquisition, HUD account access, the older SVG map rebuild, and rebuilding every completed report were not rerun. The FEMA service is live; saved snapshots preserve this run but do not freeze future upstream data.
- No historical claims datasets, provisional exposure calculations, or prior reports were overwritten. This documentation does not claim a complete transitive environment lock, clean-checkout data availability, cross-platform support, or independently validated exposure.
