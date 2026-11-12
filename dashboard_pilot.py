
from pathlib import Path
from decimal import Decimal, InvalidOperation
import hashlib
import json

import pandas as pd
import plotly.express as px
import streamlit as st

from scripts.pilot_comparisons import claims_comparison, noncondo_exposure


# --------------------------------------------------
# PAGE CONFIGURATION
# --------------------------------------------------

st.set_page_config(
    page_title="RiskMap | Insurance Analytics",
    page_icon="🌊",
    layout="wide",
)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data" / "processed"
REPORTS_DIR = BASE_DIR / "reports"

DATA_PATH = DATA_DIR / "nfip_payments_by_year_hud_status.csv"
ZIP_DATA_PATH = DATA_DIR / "nfip_claims_by_year_zip.csv"
ZIP_STATUS_PATH = DATA_DIR / "nfip_payments_by_zip_hud.csv"
MAP_PATH = REPORTS_DIR / "nfip_pinellas_zcta_map.svg"
HAZARD_DATA_PATH = DATA_DIR / "nfhl_zcta_hazard_summary.csv"
HAZARD_METADATA_PATH = REPORTS_DIR / "nfhl_zcta_hazard_metadata.json"


PILOT_CODES = {
    "N": "Non-condominium",
    "U": "Individual condominium unit",
    "A": "Condominium association",
    "H": "High-rise master policy",
    "L": "Low-rise master policy",
}


def load_exposure_pilot(reports_dir):
    """Read the three saved reports, verify provenance, and reconcile display data."""
    filenames = {
        "exposure": "provisional_exposure_33706_2024.json",
        "comparison": "claims_policy_compatibility_33706_2024.json",
        "metrics": "pilot_record_metrics_33706_2024.json",
    }
    raw = {}
    reports = {}
    for key, filename in filenames.items():
        path = reports_dir / filename
        if not path.is_file():
            raise ValueError(f"Missing pilot report: {filename}")
        raw[key] = path.read_bytes()
        try:
            reports[key] = json.loads(raw[key])
        except (ValueError, UnicodeError) as error:
            raise ValueError(f"Cannot read pilot report: {filename}") from error

    exposure = reports["exposure"]
    comparison = reports["comparison"]
    metrics = reports["metrics"]
    scope = {"calendar_year": 2024, "zip": "33706", "county_geoid_prefix": "12103"}
    if comparison.get("scope") != scope or metrics.get("scope") != scope:
        raise ValueError("Pilot reports have different years or geographic scopes.")
    if any(exposure.get(key) != value for key, value in scope.items()):
        raise ValueError("Exposure report does not match the 2024 ZIP 33706 pilot.")
    if comparison.get("source_dates_align") is not True:
        raise ValueError("Claim and policy source dates do not align.")

    links = [
        (comparison.get("input_sha256", {}).get("exposure"), "exposure"),
        (metrics.get("input_sha256", {}).get("exposure"), "exposure"),
        (metrics.get("input_sha256", {}).get("comparison"), "comparison"),
    ]
    if any(expected != hashlib.sha256(raw[key]).hexdigest() for expected, key in links):
        raise ValueError("Pilot reports come from different runs. Regenerate the comparison and metrics from the current exposure report.")

    def numeric(value):
        try:
            result = Decimal(str(value))
        except InvalidOperation as error:
            raise ValueError("Pilot report contains a missing or invalid number.") from error
        if not result.is_finite():
            raise ValueError("Pilot report contains a nonfinite number.")
        return result

    def count(value):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError("Pilot report contains an invalid record count.")
        return value

    def indexed(items, field):
        groups = {item[field]: item for item in items}
        if len(items) != 5 or set(groups) != set(PILOT_CODES):
            raise ValueError("Pilot report has missing, duplicate, or unknown coverage groups.")
        return groups

    policy_groups = indexed(exposure["groups"], "code")
    claim_groups = indexed(comparison["comparison_by_code"], "condominium_code")
    metric_groups = indexed(metrics["metrics_by_condominium_code"], "code")
    snapshots = exposure["source_as_of_dates"]
    claim_snapshots = comparison["claims_audit"]["source_as_of_dates"]
    if (not snapshots or set(snapshots) != set(metrics["source_as_of_dates"])
        or set(snapshots) != set(claim_snapshots) or any(x in (None, "None", "MISSING") for x in snapshots)):
        raise ValueError("Pilot source snapshot dates disagree or are missing.")

    rows = []
    for code, label in PILOT_CODES.items():
        policy = policy_groups[code]
        claims = claim_groups[code]
        metric = metric_groups[code]
        n = count(claims["claim_records"])
        missing = count(claims["all_payment_components_missing"])
        partial = count(claims["partial_payment_records"])
        complete = count(claims["complete_payment_records"])
        if n != missing + partial + complete:
            raise ValueError("Claim payment completeness counts do not reconcile.")
        years = numeric(policy["record_years_excluding_exceptions"])
        extra = numeric(policy["added_record_years_if_flagged_cancellation_ignored"])
        reported = numeric(claims["sum_of_reported_gross_components_usd"])
        exceptions = count(policy["exception_records"])
        if years <= 0 or extra < 0:
            raise ValueError("Pilot coverage duration is zero or invalid.")
        equal_values = [
            (claims["provisional_record_years"], years),
            (metric["record_years_excluding_flagged_dates"], years),
            (metric["sum_of_reported_gross_components_usd"], reported),
            (metric["claim_records"], n),
            (metric["records_with_all_gross_payment_fields_missing"], missing),
            (metric["records_with_partial_gross_payments"], partial),
            (metric["excluded_policy_date_exceptions"], exceptions),
        ]
        if any(numeric(value) != expected for value, expected in equal_values):
            raise ValueError(f"Saved values disagree for coverage code {code}.")
        alternative = metric["sensitivity_if_flagged_cancellations_ignored"]
        rate = Decimal(n) * 1000 / years
        alternative_rate = Decimal(n) * 1000 / (years + extra)
        rate_checks = [
            (metric["claim_records_per_1000_record_years"], rate),
            (metric["reported_gross_components_usd_per_record_year"], reported / years),
            (alternative["claim_records_per_1000_record_years"], alternative_rate),
            (alternative["record_years"], years + extra),
            (alternative["reported_gross_components_usd_per_record_year"], reported / (years + extra)),
        ]
        if any(abs(numeric(value) - expected) > Decimal("0.00001") for value, expected in rate_checks):
            raise ValueError(f"Saved metrics do not reconcile for coverage code {code}.")
        rows.append({"code": code, "Coverage type": label, "Claim records": n,
            "Record-years": float(years), "Claims / 1,000 record-years": float(rate),
            "Reported payments ($)": float(reported),
            "Reported payments / record-year ($)": float(reported / years),
            "Missing all payment fields": missing, "Partial payment records": partial,
            "Policy date exceptions": exceptions, "Sensitivity record-years": float(years + extra),
            "Sensitivity claims / 1,000 record-years": float(alternative_rate),
            "Sensitivity reported payments / record-year ($)": float(reported / (years + extra)),
            "Overlapping policy records": count(policy["overlapping_records"])})

    reconciliation = exposure["record_reconciliation"]
    if reconciliation != comparison["exposure_record_reconciliation"]:
        raise ValueError("Policy record reconciliations disagree.")
    if (sum(count(reconciliation[key]) for key in ("overlapping_records", "no_elapsed_coverage", "date_exceptions"))
        != count(exposure["unique_records"])):
        raise ValueError("Policy record totals do not reconcile.")
    frame = pd.DataFrame(rows)
    exclusions = comparison["claims_audit"]["geography_exclusions"]
    matched = comparison["claims_audit"]["checks"]["matched_claim_records"]
    target = comparison["claims_audit"]["checks"]["target_zip_2024_records"]
    if int(frame["Claim records"].sum()) != count(matched) or count(target) != matched + len(exclusions):
        raise ValueError("Claims and geographic exclusions do not reconcile.")
    if (int(frame["Policy date exceptions"].sum()) != reconciliation["date_exceptions"]
        or int(frame["Overlapping policy records"].sum()) != reconciliation["overlapping_records"]):
        raise ValueError("Policy coverage groups do not reconcile.")
    return frame, reports, {"matched_claims": matched,
        "missing_payments": int(frame["Missing all payment fields"].sum()),
        "date_exceptions": reconciliation["date_exceptions"],
        "geography_exclusions": len(exclusions), "snapshots": snapshots,
        "download": raw["metrics"]}


def render_exposure_pilot():
    st.header("2024 Exposure Pilot")
    st.caption("ZIP 33706 | Pinellas Census GEOIDs | Fixed 2024 study period")
    st.info("This pilot uses its own fixed ZIP, year, and Census geography. The sidebar filters apply to the historical claims views, not this tab.")
    try:
        pilot, reports, quality = load_exposure_pilot(REPORTS_DIR)
    except (ValueError, KeyError, TypeError, OSError, AttributeError) as error:
        st.warning("The exposure pilot is unavailable. Your historical claims views remain available.")
        st.caption(str(error))
        st.caption("This tab needs the three saved 33706 reports: provisional exposure, claims-policy compatibility, and pilot record metrics. Keep them together in RiskMap's reports folder.")
        return

    st.warning("Exploratory results. Independent benchmark validation is pending. These ratios are not the percentage of properties flooded or a prediction of future flood risk.")
    dates = ", ".join(str(value)[:10] for value in quality["snapshots"])
    st.caption(f"FEMA source snapshot: {dates}. Payments relate to 2024 losses and may have been reported after 2024.")

    st.subheader("Coverage type")
    selected_code = st.selectbox("Choose a coverage type", options=list(PILOT_CODES),
        format_func=lambda code: PILOT_CODES[code], key="pilot_coverage_type")
    selected = pilot.loc[pilot["code"].eq(selected_code)].iloc[0]
    if selected["Record-years"] < 10:
        st.warning("This group has fewer than 10 record-years. A handful of records can move its ratio substantially; use it as a small-sample description.")

    cols = st.columns(3)
    cols[0].metric("Claim records", f"{selected['Claim records']:,.0f}")
    cols[1].metric("Recorded coverage-years", f"{selected['Record-years']:,.2f}")
    cols[2].metric("Claims / 1,000 record-years", f"{selected['Claims / 1,000 record-years']:,.1f}")
    st.caption(f"Calculation: {selected['Claim records']:,.0f} claim records / {selected['Record-years']:,.4f} recorded coverage-years × 1,000. A record-year is one year of duration represented by a policy row; it has not been established as one unique property or contract.")

    show_sensitivity = st.checkbox("Show the effect of unresolved cancellation dates", value=False, key="pilot_sensitivity")
    if show_sensitivity:
        st.caption("Alternative scenario: ignore the cancellation dates on flagged records and use their remaining recorded term dates. This is not a correction or a confidence interval.")
        before, after = st.columns(2)
        before.metric("Excluding flagged records", f"{selected['Claims / 1,000 record-years']:,.1f}")
        after.metric("If flagged cancellations are ignored", f"{selected['Sensitivity claims / 1,000 record-years']:,.1f}")
        st.caption(f"{selected['Policy date exceptions']:,.0f} flagged policy records in this coverage type. Alternative recorded coverage-years: {selected['Sensitivity record-years']:,.4f}.")

    st.divider()
    st.subheader("Reported payments for this coverage type")
    dollars, intensity = st.columns(2)
    dollars.metric("Reported payment components", f"${selected['Reported payments ($)']:,.0f}")
    intensity.metric("Reported payments / record-year", f"${selected['Reported payments / record-year ($)']:,.0f}")
    st.caption(f"{selected['Missing all payment fields']:,.0f} claim records have all gross payment fields missing; {selected['Partial payment records']:,.0f} have partial payment information. These unknown values are not reported zeros. Amounts sum known building, contents, and ICC payments in nominal dollars; they are not final losses or cash disbursed exclusively in 2024.")

    st.divider()
    st.subheader("All coverage groups")
    st.caption("Groups stay separate because individual-unit and association coverage can overlap. This table is not a ranking of property risk.")
    display = pilot[["Coverage type", "Claim records", "Record-years", "Claims / 1,000 record-years",
        "Missing all payment fields", "Policy date exceptions"]]
    st.dataframe(display, hide_index=True, width="stretch", column_config={
        "Record-years": st.column_config.NumberColumn(format="%.2f"),
        "Claims / 1,000 record-years": st.column_config.NumberColumn(format="%.1f"),
    })

    with st.expander("Data quality and method"):
        checks = st.columns(4)
        checks[0].metric("Matched claim records", f"{quality['matched_claims']:,}")
        checks[1].metric("Missing all payment fields", f"{quality['missing_payments']:,}")
        checks[2].metric("Policy date exceptions", f"{quality['date_exceptions']:,}")
        checks[3].metric("Claim geography exclusions", f"{quality['geography_exclusions']:,}")
        st.markdown("Coverage intervals are clipped to January 1, 2024 through January 1, 2025 and divided by 366 days. Recorded cancellations truncate coverage. Cancellations before the effective date are excluded and retained as unresolved exceptions.")
        st.markdown("The pilot uses reported ZIP 33706 and valid Pinellas Census block-group GEOIDs beginning 12103. Missing policy GEOIDs are outside the downloaded scope. Four claims with missing GEOIDs are excluded from the comparison.")
        st.markdown("FEMA describes separate renewal records and date-based coverage-in-force selection. It does not provide a shared public key linking individual claims to policies. Endorsement behavior, unique-contract interpretation, and independent coverage benchmarking remain unresolved.")
        st.markdown("[FEMA policy and claims data FAQ](https://agents.floodsmart.gov/flood-maps-and-data/faqs-about-nfip-data)")
        st.download_button("Download exploratory pilot metrics (JSON)", data=quality["download"],
            file_name="pilot_record_metrics_33706_2024.json", mime="application/json", key="pilot_download")


# --------------------------------------------------
# LOAD DATA
# --------------------------------------------------

@st.cache_data
def load_data():
    df = pd.read_csv(DATA_PATH)
    df["year_of_loss"] = df["year_of_loss"].astype(int)
    return df


@st.cache_data
def load_zip_data():
    yearly = pd.read_csv(
        ZIP_DATA_PATH,
        dtype={"reported_zip_code": str},
    )

    status = pd.read_csv(
        ZIP_STATUS_PATH,
        dtype={"reported_zip_5": str},
    )

    return yearly, status


@st.cache_data
def load_hazard_data():
    hazard = pd.read_csv(HAZARD_DATA_PATH, dtype={"zcta5": str})
    metadata = json.loads(HAZARD_METADATA_PATH.read_text(encoding="utf-8"))
    return hazard, metadata


# --------------------------------------------------
# DASHBOARD HEADER
# --------------------------------------------------

st.title("RiskMap")

st.subheader(
    "Pinellas County | Historical Flood Insurance Analytics"
)

st.caption(
    "FEMA NFIP historical claims | Nominal reported payments | "
    "Descriptive analysis, not predicted flood risk"
)

if not DATA_PATH.exists():
    st.error(f"Dataset not found: {DATA_PATH}")
    st.stop()

df = load_data()


# --------------------------------------------------
# SIDEBAR FILTERS
# --------------------------------------------------

st.sidebar.header("Explore the Data")

STATUS_LABELS = {
    "hud_pinellas_link": "Pinellas-Linked ZIP Codes",
    "hud_other_counties_only": "ZIP Codes Linked to Other Counties",
    "not_in_hud_crosswalk": "ZIP Codes Not Found in Reference Data",
    "missing_zip": "Missing ZIP Code",
    "malformed_zip": "Invalid ZIP Code",
}

statuses = sorted(
    df["hud_status"].dropna().unique().tolist()
)

selected_statuses = st.sidebar.multiselect(
    "ZIP Code Geographic Classification",
    options=statuses,
    default=["hud_pinellas_link"],
    format_func=lambda status: STATUS_LABELS.get(
        status, status
    ),
    help=(
        "Classifications use the 2025 HUD ZIP-to-county "
        "crosswalk. A ZIP linked to Pinellas does not "
        "confirm the exact location of every historical claim."
    ),
)

min_year = int(df["year_of_loss"].min())
max_year = int(df["year_of_loss"].max())

selected_years = st.sidebar.slider(
    "Year of loss",
    min_value=min_year,
    max_value=max_year,
    value=(min_year, max_year),
)

filtered = df[
    df["hud_status"].isin(selected_statuses)
    & df["year_of_loss"].between(*selected_years)
].copy()


# --------------------------------------------------
# DASHBOARD NAVIGATION
# --------------------------------------------------

tab_overview, tab_geography, tab_comparison, tab_hazard, tab_pilot, tab_methodology = st.tabs(
    [
        "Overview",
        "Geographic Analysis",
        "2024 ZIP Comparison",
        "Flood Hazard Context",
        "2024 Exposure Pilot",
        "Data & Methodology",
    ]
)


# ==================================================
# TAB 1 — OVERVIEW
# ==================================================

with tab_overview:

    st.header("Historical Loss Overview")

    if filtered.empty:
        st.warning(
            "No records match the selected filters."
        )

    else:

        # Summary metrics

        total_payments = filtered[
            "gross_reported_payments_usd"
        ].sum()

        total_claims = int(
            filtered["claim_records"].sum()
        )

        positive_claims = int(
            filtered["positive_payment_claims"].sum()
        )

        col1, col2, col3 = st.columns(3)

        col1.metric(
            "Reported Payments",
            f"${total_payments / 1e9:,.2f}B",
        )

        col2.metric(
            "Claim Records",
            f"{total_claims:,}",
        )

        col3.metric(
            "Positive-Payment Claims",
            f"{positive_claims:,}",
        )

        # Aggregate by year

        annual = (
            filtered.groupby(
                "year_of_loss",
                as_index=False,
            )[
                [
                    "gross_reported_payments_usd",
                    "claim_records",
                ]
            ]
            .sum()
            .sort_values("year_of_loss")
        )

        # Historical payments chart

        st.markdown(
            "### Historical NFIP Payments by Year"
        )

        payment_chart = px.bar(
            annual,
            x="year_of_loss",
            y="gross_reported_payments_usd",
            labels={
                "year_of_loss": "Year of Loss",
                "gross_reported_payments_usd":
                    "Reported Payments (USD)",
            },
            color_discrete_sequence=["#008C71"],
        )

        payment_chart.update_traces(
            hovertemplate=(
                "Year: %{x}"
                "<br>Payments: $%{y:,.2f}"
                "<extra></extra>"
            )
        )

        payment_chart.update_layout(
            xaxis=dict(type="category"),
            yaxis_tickprefix="$",
            yaxis_tickformat="~s",
        )

        st.plotly_chart(
            payment_chart,
            width="stretch",
        )

        # Claim volume chart

        st.markdown(
            "### Historical Claim Volume"
        )

        claims_chart = px.line(
            annual,
            x="year_of_loss",
            y="claim_records",
            markers=True,
            labels={
                "year_of_loss": "Year of Loss",
                "claim_records": "Claim Records",
            },
            color_discrete_sequence=["#008C71"],
        )

        claims_chart.update_traces(
            hovertemplate=(
                "Year: %{x}"
                "<br>Claim records: %{y:,}"
                "<extra></extra>"
            )
        )

        claims_chart.update_layout(
            xaxis=dict(type="category")
        )

        st.plotly_chart(
            claims_chart,
            width="stretch",
        )

        # Underlying annual data

        with st.expander(
            "View underlying annual data"
        ):
            st.dataframe(
                annual,
                hide_index=True,
                width="stretch",
            )

        st.info(
            "Payments are nominal and are not adjusted "
            "for inflation. Claim counts are not "
            "exposure-adjusted risk rates. Recent years "
            "may contain incomplete records."
        )


# ==================================================
# TAB 2 — GEOGRAPHIC ANALYSIS
# ==================================================

with tab_geography:

    st.header("Geographic Analysis")

    st.markdown(
        "### Geographic Distribution of Historical NFIP Payments"
    )

    if MAP_PATH.exists():

        st.image(
            str(MAP_PATH),
            width="stretch",
        )

        st.caption(
            "2025 Census ZCTA polygons clipped to "
            "Pinellas County. The map shows historical "
            "ZIP-level payments for the full available "
            "period and does not respond to the year "
            "slider. ZIPs and Census ZCTAs are not "
            "identical geographic units. Values are "
            "not flood-risk rates."
        )

    else:

        st.warning(
            "Geographic map not found in the reports folder."
        )

    st.divider()

    # --------------------------------------------------
    # VALIDATED ZIP LOSS SEVERITY — PERIOD COMPARISON
    # --------------------------------------------------

    st.header("Validated ZIP Loss Severity")
    st.caption(
        "Compare HUD Pinellas-linked ZIPs across all available years, "
        "2024 only, or all years excluding 2024. This selector controls "
        "the charts and table below, independently of the sidebar year "
        "slider and geographic classification filter. The map above "
        "remains a static all-years illustration."
    )

    severity_path = DATA_DIR / "nfip_zip_loss_severity.csv"

    if not severity_path.exists():
        st.warning(
            "Validated ZIP severity data not found. Run "
            "scripts/analyze_zip_loss_severity.py first."
        )
    else:
        severity_data = pd.read_csv(
            severity_path,
            dtype={"reported_zip_code": str},
        )

        required_columns = {
            "period",
            "payment_rank",
            "reported_zip_code",
            "claim_records",
            "positive_payment_claims",
            "total_payments",
            "avg_payment_per_positive_claim",
            "payment_share_pct",
        }
        missing_columns = required_columns - set(severity_data.columns)

        if missing_columns:
            st.error(
                "ZIP severity file is missing expected columns: "
                + ", ".join(sorted(missing_columns))
            )
        else:
            period_options = [
                "All Years",
                "2024 Only",
                "Excluding 2024",
            ]
            chosen_period = st.selectbox(
                "Comparison period",
                options=period_options,
                key="severity_comparison_period",
            )

            period_zip = (
                severity_data.loc[
                    severity_data["period"] == chosen_period
                ]
                .sort_values("payment_rank")
                .copy()
            )

            if period_zip.empty:
                st.info("No ZIP severity results for this period.")
            else:
                period_payments = period_zip["total_payments"].sum()
                period_claims = int(period_zip["claim_records"].sum())
                paid_claims = int(
                    period_zip["positive_payment_claims"].sum()
                )
                avg_paid_claim = (
                    period_payments / paid_claims
                    if paid_claims > 0
                    else None
                )
                payments_label = (
                    f"${period_payments / 1e9:,.2f}B"
                    if abs(period_payments) >= 1e9
                    else f"${period_payments / 1e6:,.2f}M"
                )

                metric1, metric2, metric3 = st.columns(3)
                metric1.metric("Reported Payments", payments_label)
                metric2.metric("Claim Records", f"{period_claims:,}")
                metric3.metric(
                    "Avg. Payment per Positive Claim",
                    f"${avg_paid_claim:,.0f}"
                    if avg_paid_claim is not None
                    else "N/A",
                )
                min_paid_claims = st.number_input(
                    "Minimum positive-payment claims for severity ranking",
                    min_value=1,
                    value=25,
                    step=1,
                    help="Only filters the average paid claim chart.",
                )
                top_payments = period_zip.head(10).copy()
                top_severity = (
                    period_zip.loc[
                        (period_zip["positive_payment_claims"] >= min_paid_claims)
                        & period_zip[
                            "avg_payment_per_positive_claim"
                        ].notna()
                    ]
                    .sort_values(
                        "avg_payment_per_positive_claim",
                        ascending=False,
                    )
                    .head(10)
                    .copy()
                )

                chart1, chart2 = st.columns(2)

                with chart1:
                    st.markdown("#### Top ZIPs by Total Payments")
                    payments_fig = px.bar(
                        top_payments,
                        x="total_payments",
                        y="reported_zip_code",
                        orientation="h",
                        labels={
                            "total_payments": "Reported Payments (USD)",
                            "reported_zip_code": "ZIP Code",
                        },
                        category_orders={
                            "reported_zip_code": list(
                                reversed(
                                    top_payments["reported_zip_code"].tolist()
                                )
                            )
                        },
                        custom_data=["payment_share_pct"],
                        color_discrete_sequence=["#008C71"],
                    )
                    payments_fig.update_traces(
                        hovertemplate=(
                            "ZIP: %{y}<br>Payments: $%{x:,.0f}"
                            "<br>Period share: %{customdata[0]:.2f}%"
                            "<extra></extra>"
                        )
                    )
                    payments_fig.update_layout(
                        xaxis_tickprefix="$",
                        xaxis_tickformat="~s",
                    )
                    payments_fig.update_yaxes(type="category")
                    st.plotly_chart(payments_fig, width="stretch")

                with chart2:
                    st.markdown("#### Top ZIPs by Average Paid Claim")
                    if top_severity.empty:
                        st.info("No ZIPs meet the minimum claim count. Lower the threshold.")
                    else:
                        severity_fig = px.bar(
                            top_severity,
                            x="avg_payment_per_positive_claim",
                            y="reported_zip_code",
                            orientation="h",
                            labels={
                                "avg_payment_per_positive_claim":
                                    "Average Payment (USD)",
                                "reported_zip_code": "ZIP Code",
                            },
                            category_orders={
                                "reported_zip_code": list(
                                    reversed(
                                        top_severity[
                                            "reported_zip_code"
                                        ].tolist()
                                    )
                                )
                            },
                            custom_data=["positive_payment_claims"],
                            color_discrete_sequence=["#176B87"],
                        )
                        severity_fig.update_traces(
                            hovertemplate=(
                                "ZIP: %{y}<br>Average: $%{x:,.0f}"
                                "<br>Positive-payment claims: "
                                "%{customdata[0]:,}<extra></extra>"
                            )
                        )
                        severity_fig.update_layout(
                            xaxis_tickprefix="$",
                            xaxis_tickformat="~s",
                        )
                        severity_fig.update_yaxes(type="category")
                        st.plotly_chart(severity_fig, width="stretch")

                st.markdown("#### Full ZIP Rankings")
                severity_display = period_zip.rename(
                    columns={
                        "payment_rank": "Payment Rank",
                        "reported_zip_code": "ZIP Code",
                        "claim_records": "Claim Records",
                        "positive_payment_claims":
                            "Positive-Payment Claims",
                        "total_payments": "Total Payments ($)",
                        "avg_payment_per_positive_claim":
                            "Average per Positive Claim ($)",
                        "payment_share_pct": "Payment Share (%)",
                    }
                )
                st.dataframe(
                    severity_display[
                        [
                            "Payment Rank",
                            "ZIP Code",
                            "Claim Records",
                            "Positive-Payment Claims",
                            "Total Payments ($)",
                            "Average per Positive Claim ($)",
                            "Payment Share (%)",
                        ]
                    ],
                    hide_index=True,
                    width="stretch",
                    column_config={
                        "Total Payments ($)":
                            st.column_config.NumberColumn(format="$%.2f"),
                        "Average per Positive Claim ($)":
                            st.column_config.NumberColumn(format="$%.2f"),
                        "Payment Share (%)":
                            st.column_config.NumberColumn(format="%.2f"),
                    },
                )
                st.caption(
                    "These are historical nominal NFIP payments, not "
                    "exposure-adjusted flood-risk rates. Average paid "
                    "claim amounts can be sensitive to small sample sizes."
                )

    st.divider()

    # --------------------------------------------------
    # ZIP CODE COMPARISON
    # --------------------------------------------------

    st.header("ZIP Code Comparison")

    st.caption(
        "Compare historical NFIP payments and claims "
        "for Pinellas-linked ZIP codes within the "
        "selected years."
    )

    if ZIP_DATA_PATH.exists() and ZIP_STATUS_PATH.exists():

        yearly_zip, zip_status = load_zip_data()

        # Identify Pinellas-linked ZIP codes

        pinellas_zips = set(
            zip_status.loc[
                zip_status["hud_status"] == "hud_pinellas_link",
                "reported_zip_5",
            ]
        )

        # Apply selected year range

        yearly_zip = yearly_zip[
            yearly_zip["year_of_loss"].between(
                *selected_years
            )
            & yearly_zip["reported_zip_code"].isin(
                pinellas_zips
            )
        ].copy()

        # ZIP selection

        zip_options = sorted(
            yearly_zip[
                "reported_zip_code"
            ].dropna().unique()
        )

        default_zips = [
            z
            for z in ["33706", "33703", "33708"]
            if z in zip_options
        ]

        selected_zips = st.multiselect(
            "Select ZIP Codes to Compare",
            options=zip_options,
            default=default_zips,
            key="zip_comparison_selection",
        )

        # Aggregate selected ZIPs

        comparison = (
            yearly_zip[
                yearly_zip[
                    "reported_zip_code"
                ].isin(selected_zips)
            ]
            .groupby(
                "reported_zip_code",
                as_index=False,
            )
            .agg(
                claim_records=(
                    "claim_records",
                    "sum",
                ),
                positive_payment_claims=(
                    "records_with_positive_payments",
                    "sum",
                ),
                gross_reported_payments_usd=(
                    "gross_reported_payments_usd",
                    "sum",
                ),
            )
        )

        if not comparison.empty:

            comparison[
                "avg_positive_claim_payment"
            ] = (
                comparison[
                    "gross_reported_payments_usd"
                ]
                / comparison[
                    "positive_payment_claims"
                ].replace(
                    0,
                    float("nan"),
                )
            )

            col1, col2 = st.columns(2)

            # Payment comparison chart

            with col1:

                payments_fig = px.bar(
                    comparison,
                    x="reported_zip_code",
                    y="gross_reported_payments_usd",
                    title="Historical Payments by ZIP",
                    labels={
                        "reported_zip_code": "ZIP Code",
                        "gross_reported_payments_usd":
                            "Payments (USD)",
                    },
                    color_discrete_sequence=[
                        "#008C71"
                    ],
                )

                payments_fig.update_layout(
                    xaxis_type="category",
                    yaxis_tickprefix="$",
                )

                st.plotly_chart(
                    payments_fig,
                    width="stretch",
                )

            # Claim comparison chart

            with col2:

                claims_fig = px.bar(
                    comparison,
                    x="reported_zip_code",
                    y="claim_records",
                    title="Claim Records by ZIP",
                    labels={
                        "reported_zip_code": "ZIP Code",
                        "claim_records": "Claim Records",
                    },
                    color_discrete_sequence=[
                        "#176B87"
                    ],
                )

                claims_fig.update_layout(
                    xaxis_type="category"
                )

                st.plotly_chart(
                    claims_fig,
                    width="stretch",
                )

            # Detailed comparison table

            st.markdown(
                "### Detailed ZIP Comparison"
            )

            display_df = comparison.rename(
                columns={
                    "reported_zip_code": "ZIP Code",
                    "claim_records": "Claim Records",
                    "positive_payment_claims":
                        "Claims With Positive Payments",
                    "gross_reported_payments_usd":
                        "Total Payments ($)",
                    "avg_positive_claim_payment":
                        "Avg. Payment per Positive-Payment Claim ($)",
                }
            )

            st.dataframe(
                display_df,
                hide_index=True,
                width="stretch",
                column_config={
                    "Total Payments ($)":
                        st.column_config.NumberColumn(
                            format="$%.2f"
                        ),
                    "Avg. Payment per Positive-Payment Claim ($)":
                        st.column_config.NumberColumn(
                            format="$%.2f"
                        ),
                },
            )

        else:

            st.info(
                "Select at least one ZIP code to compare."
            )

        st.caption(
            f"Comparison period: {selected_years[0]}–"
            f"{selected_years[1]}. "
            "ZIP classification uses the 2025 HUD "
            "crosswalk. The ZIP comparison is "
            "restricted to Pinellas-linked ZIPs, "
            "regardless of the Overview geographic "
            "classification filter. Historical "
            "payment totals are not flood-risk rates."
        )

    else:

        st.warning(
            "ZIP comparison data files were not found."
        )


# ==================================================
# TAB 3 — DATA & METHODOLOGY
# ==================================================

with tab_comparison:
    st.header("2024 Historical Claims and Reported Payments")
    st.info("Fixed comparison: ZIPs 33703, 33706 and 33708; year of loss 2024. Sidebar filters do not apply to this tab.")
    try:
        comparison_2024 = pd.DataFrame(claims_comparison(ZIP_DATA_PATH))
    except (OSError, ValueError, KeyError) as error:
        st.warning("The 2024 claims comparison is unavailable.")
        st.caption(str(error))
    else:
        st.dataframe(comparison_2024, hide_index=True, width="stretch", column_config={
            "Nominal reported payments ($)": st.column_config.NumberColumn(format="$%.2f"),
        })
        claim_col, payment_col = st.columns(2)
        with claim_col:
            claim_fig = px.bar(comparison_2024, x="ZIP", y="Claim records",
                title="2024 Claim Records", color_discrete_sequence=["#176B87"],
                custom_data=["All gross payment components missing"])
            claim_fig.update_xaxes(type="category")
            claim_fig.update_traces(hovertemplate="ZIP %{x}<br>Claim records: %{y:,}<br>All gross payment components missing: %{customdata[0]:,}<extra></extra>")
            st.plotly_chart(claim_fig, width="stretch")
        with payment_col:
            payment_fig = px.bar(comparison_2024, x="ZIP", y="Nominal reported payments ($)",
                title="2024 Nominal Reported Payments", color_discrete_sequence=["#008C71"])
            payment_fig.update_xaxes(type="category")
            payment_fig.update_yaxes(tickprefix="$", tickformat="~s")
            payment_fig.update_traces(hovertemplate="ZIP %{x}<br>Nominal reported payments: $%{y:,.2f}<extra></extra>")
            st.plotly_chart(payment_fig, width="stretch")
        st.caption("Payments sum the reported gross building, contents and ICC components for 2024 losses, in nominal dollars. Missing components are unknown, not reported zeros. These are not final losses or cash disbursed only in 2024.")
        st.caption("Claims use reported ZIPs in the reconciled historical dataset. These ZIP-level counts are not exposure-adjusted flood-risk rates.")

    st.divider()
    st.header("33708 Non-condominium Exposure Sensitivity")
    st.warning("Provisional recorded-policy-duration exposure. This separate panel is not a denominator for the claims comparison above; no claim rates are calculated here.")
    try:
        exposure_33708 = noncondo_exposure(BASE_DIR)
    except (OSError, ValueError, KeyError) as error:
        st.warning("The 33708 exposure sensitivity is unavailable.")
        st.caption(str(error))
    else:
        baseline_col, sensitivity_col = st.columns(2)
        baseline_col.metric("Baseline record-years", f"{exposure_33708['baseline']:,.4f}")
        sensitivity_col.metric("Termination-only record-years", f"{exposure_33708['termination_only']:,.4f}")
        st.markdown(f"**Sensitivity change: +{exposure_33708['delta']:,.4f} record-years (+{exposure_33708['percent_change']:.2f}%).**")
        st.write("The baseline ends recorded coverage at the earlier of cancellation and termination. The termination-only scenario uses the termination date instead. Conflicting end dates account for the difference; actual coverage has not been independently resolved.")
        st.caption(f"Calendar year 2024; coverage code N; confirmed Pinellas GEOIDs only. Missing-GEOID records are excluded from both scenarios. The same {exposure_33708['date_exceptions']} cancellations before the effective date are excluded from both. Source snapshot: {exposure_33708['snapshot']}.")
        with st.expander("Exposure method and limitations"):
            st.write("Recorded intervals are clipped to January 1, 2024 through January 1, 2025 and divided by 366 days. A record-year is not established as a unique property or contract. Termination-only is a sensitivity assumption, not a correction or a confidence interval. No matching independent policies-in-force benchmark has been verified.")


with tab_pilot:
    render_exposure_pilot()


with tab_hazard:
    st.header("Mapped Flood Hazard Context")
    st.caption("FEMA National Flood Hazard Layer (NFHL) polygons summarized to Census ZCTAs 33703, 33706, and 33708.")
    st.warning("Mapped flood zones describe FEMA's mapped hazard designations. They are not observed floods, NFIP claims, property-level conditions, or future predictions.")

    if not HAZARD_DATA_PATH.is_file() or not HAZARD_METADATA_PATH.is_file():
        st.info("Flood-hazard summaries are not available. Run scripts/summarize_nfhl_hazard.py to retrieve and summarize the official source data.")
    else:
        try:
            hazard, hazard_metadata = load_hazard_data()
            required_hazard_fields = {
                "zcta5", "zcta_area_km2", "nfhl_mapped_pct_zcta", "sfha_area_km2",
                "sfha_pct_zcta", "sfha_pct_nfhl_mapped", "nfhl_study_effective_dates",
            }
            if not required_hazard_fields.issubset(hazard.columns):
                raise ValueError("The hazard summary is missing expected fields.")
            if (hazard["zcta5"].duplicated().any()
                or set(hazard["zcta5"]) != {"33703", "33706", "33708"}):
                raise ValueError("The hazard summary does not contain one row for each target Census ZCTA.")
            for field in ("nfhl_mapped_pct_zcta", "sfha_pct_zcta", "sfha_pct_nfhl_mapped"):
                if hazard[field].isna().any() or not hazard[field].between(0, 100).all():
                    raise ValueError(f"The hazard summary has invalid percentages in {field}.")
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
            st.warning("The flood-hazard view is unavailable. Historical claims and exposure views remain available.")
            st.caption(str(error))
        else:
            st.markdown("### Share of ZCTA area mapped as a Special Flood Hazard Area")
            st.caption("SFHA area uses NFHL SFHA_TF = T. The percentage is relative to the full 2020 Census ZCTA polygon, not only the NFHL-mapped footprint.")
            hazard_chart = px.bar(
                hazard.sort_values("zcta5"),
                x="zcta5",
                y="sfha_pct_zcta",
                custom_data=["sfha_area_km2", "sfha_pct_nfhl_mapped", "nfhl_mapped_pct_zcta"],
                labels={"zcta5": "Census ZCTA", "sfha_pct_zcta": "ZCTA area in mapped SFHA (%)"},
                color_discrete_sequence=["#D9694A"],
            )
            hazard_chart.update_traces(
                hovertemplate=(
                    "ZCTA %{x}<br>SFHA area: %{customdata[0]:.2f} km2"
                    "<br>Share of full ZCTA: %{y:.2f}%"
                    "<br>Share of mapped NFHL area: %{customdata[1]:.2f}%"
                    "<br>NFHL mapped coverage: %{customdata[2]:.2f}%<extra></extra>"
                )
            )
            hazard_chart.update_xaxes(type="category")
            hazard_chart.update_yaxes(range=[0, 100], ticksuffix="%")
            st.plotly_chart(hazard_chart, width="stretch")

            hazard_display = hazard[[
                "zcta5", "nfhl_mapped_pct_zcta", "sfha_area_km2", "sfha_pct_zcta",
            ]].rename(columns={
                "zcta5": "Census ZCTA",
                "nfhl_mapped_pct_zcta": "NFHL area represented (%)",
                "sfha_area_km2": "Mapped SFHA area (km2)",
                "sfha_pct_zcta": "SFHA share of full ZCTA (%)",
            })
            st.dataframe(hazard_display, hide_index=True, width="stretch", column_config={
                "NFHL area represented (%)": st.column_config.NumberColumn(format="%.2f%%"),
                "Mapped SFHA area (km2)": st.column_config.NumberColumn(format="%.2f"),
                "SFHA share of full ZCTA (%)": st.column_config.NumberColumn(format="%.2f%%"),
            })

            metadata = hazard_metadata.get("source_metadata", {})
            study_versions = metadata.get("study_map_versions", [])
            date_gaps = metadata.get("study_effective_date_gaps", [])
            dates = sorted({item["effective_date"] for item in study_versions if item.get("effective_date")})
            revisions = sorted({item["database_revision_date"] for item in study_versions if item.get("database_revision_date")})
            if date_gaps:
                st.warning(
                    "FEMA Study_Info has no effective-date record for map version(s): "
                    + ", ".join(date_gaps)
                    + ". These polygons remain in the mapped-area summary, but their effective date is unknown."
                )
            st.caption(
                f"NFHL retrieval: {hazard_metadata.get('retrieved_at_utc', 'not recorded')}. "
                f"Effective date(s): {', '.join(dates) or 'not recorded'}; database revision date(s): "
                f"{', '.join(revisions) or 'not recorded'}. Source study/version details are in the metadata report."
            )

            st.markdown("### Interpreting alongside RiskMap's other measures")
            st.write("The 2024 ZIP Comparison tab describes historical claim records and nominal reported payments by reported postal ZIP. The exposure panels describe provisional recorded policy duration for their stated cohort and assumptions. This tab describes mapped NFHL zone area in Census ZCTAs. These are separate measures with different geography and meaning; none is a denominator for another.")
            st.info("Example review workflow: an analyst could flag a ZIP/ZCTA pair for follow-up when its mapped SFHA share and historical claims pattern both merit attention, then inspect the underlying FEMA map panels, claim-geography quality, and exposure scope. That is a prompt for data review, not an underwriting, property eligibility, or pricing recommendation.")
            with st.expander("Hazard source and method"):
                st.write("The workflow clips FEMA NFHL Flood Hazard Zones to each complete Census ZCTA in NAD83 geographic coordinates and measures area geodesically on the GRS80 ellipsoid. A separate EPSG:4269-to-26917-to-4269 coordinate round-trip is checked. NFHL polygons with SFHA_TF = T are counted as mapped Special Flood Hazard Area. The denominator is the full Census polygon, including any parts not represented by an NFHL zone polygon.")
                st.write("FEMA's zone polygons represent mapped regulatory hazard categories, including the 1% annual-chance Special Flood Hazard Area. This is the current NFHL retrieval, not a reconstruction of map panels as of each historical claim's loss date. The mapped percentage is not a probability that a specific property floods, observed inundation, claims experience, or a complete measure of all flood sources. Open water, unmapped coverage, map changes, and boundary approximation can affect the result.")
                st.write("Claims use reported postal ZIPs, while this view uses Census ZCTAs, which approximate but do not equal USPS ZIP delivery areas. No claim has been spatially allocated to a ZCTA, and no policy or property records are joined to these polygons.")


with tab_methodology:

    st.header("Data & Methodology")

    st.markdown(
        """
        ### Project Purpose

        RiskMap explores historical flood insurance
        claims and reported payments in Pinellas
        County, Florida.

        The project is designed to support
        descriptive geographic and insurance
        analytics.

        It does not predict future flooding,
        estimate insurance premiums, or calculate
        property-level risk.

        ### Data Sources

        **FEMA National Flood Insurance Program**

        Historical NFIP claims records provide
        reported payments, claim counts, loss years,
        and reported ZIP codes.

        **HUD–USPS ZIP-to-County Crosswalk**

        The 2025 crosswalk identifies ZIP codes
        associated with Pinellas County.

        **U.S. Census Bureau**

        2025 Census ZCTA boundaries are used
        for geographic visualization.

        ### Key Metrics

        **Reported Payments**

        Sum of reported NFIP building, contents,
        and increased-cost-of-compliance payments.

        **Claim Records**

        Number of historical NFIP claim records
        in the selected dataset.

        **Positive-Payment Claims**

        Records with positive reported payments.

        **Average Payment per Positive-Payment Claim**

        Total reported payments divided by
        the number of positive-payment claims.

        ### Important Limitations

        - Historical payments are nominal and
          are not adjusted for inflation.
        - ZIP codes and Census ZCTAs are not
          identical geographic units.
        - The 2025 ZIP crosswalk does not
          establish exact historical claim locations.
        - Clipped ZCTA polygons are for display;
          payments are not spatially allocated
          within ZIP boundaries.
        - Overview and Geographic Analysis counts
          and payments are not exposure-adjusted.
          The separate 2024 Exposure Pilot shows
          exploratory ratios using recorded coverage
          duration for ZIP 33706 only.
        - Recent claim years may be incomplete.
        - Historical losses should not be
          interpreted as predicted flood-risk rates.
        """
    )

    st.info(
        "RiskMap is an insurance analytics "
        "portfolio project under development."
    )
