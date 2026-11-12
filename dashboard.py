
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


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

tab_overview, tab_geography, tab_methodology = st.tabs(
    [
        "Overview",
        "Geographic Analysis",
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
        - Claim counts and payment totals are
          not adjusted for insured-property exposure.
        - Recent claim years may be incomplete.
        - Historical losses should not be
          interpreted as predicted flood-risk rates.
        """
    )

    st.info(
        "RiskMap is an insurance analytics "
        "portfolio project under development."
    )
