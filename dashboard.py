
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


# Page configuration
st.set_page_config(
    page_title="RiskMap | Insurance Analytics",
    page_icon="🌊",
    layout="wide",
)

# Locate the processed data
DATA_PATH = (
    Path(__file__).resolve().parent
    / "data"
    / "processed"
    / "nfip_payments_by_year_hud_status.csv"
)


@st.cache_data
def load_data():
    df = pd.read_csv(DATA_PATH)
    df["year_of_loss"] = df["year_of_loss"].astype(int)
    return df


# Dashboard header
st.title("RiskMap")
st.subheader("Pinellas County | Historical Flood Insurance Analytics")

st.caption(
    "FEMA NFIP historical claims | Nominal reported payments | "
    "Descriptive analysis, not predicted flood risk"
)

if not DATA_PATH.exists():
    st.error(f"Dataset not found: {DATA_PATH}")
    st.stop()

df = load_data()

# Sidebar filters
st.sidebar.header("Explore the Data")


# User-friendly geographic matching labels
STATUS_LABELS = {
    "hud_pinellas_link": "Pinellas-Linked ZIP Codes",
    "hud_other_counties_only": "ZIP Codes Linked to Other Counties",
    "not_in_hud_crosswalk": "ZIP Codes Not Found in Reference Data",
    "missing_zip": "Missing ZIP Code",
    "malformed_zip": "Invalid ZIP Code",
}

statuses = sorted(df["hud_status"].dropna().unique().tolist())

selected_statuses = st.sidebar.multiselect(
    "ZIP Code Geographic Classification",
    options=statuses,
    default=["hud_pinellas_link"],
    format_func=lambda status: STATUS_LABELS.get(status, status),
    help=(
        "Classifications use the 2025 HUD ZIP-to-county crosswalk. "
        "A ZIP linked to Pinellas does not confirm the exact location "
        "of every historical claim."
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

if filtered.empty:
    st.warning("No records match the selected filters.")
    st.stop()

# Summary metrics
total_payments = filtered["gross_reported_payments_usd"].sum()
total_claims = int(filtered["claim_records"].sum())
positive_claims = int(filtered["positive_payment_claims"].sum())

st.markdown("### Historical Loss Overview")

col1, col2, col3 = st.columns(3)

col1.metric("Reported Payments", f"${total_payments / 1e9:,.2f}B")
col2.metric("Claim Records", f"{total_claims:,}")
col3.metric("Positive-Payment Claims", f"{positive_claims:,}")

# Aggregate selected years
annual = (
    filtered.groupby("year_of_loss", as_index=False)[
        ["gross_reported_payments_usd", "claim_records"]
    ]
    .sum()
    .sort_values("year_of_loss")
)

# Payment trend chart
st.markdown("### Historical NFIP Payments by Year")

payment_chart = px.bar(
    annual,
    x="year_of_loss",
    y="gross_reported_payments_usd",
    labels={
        "year_of_loss": "Year of Loss",
        "gross_reported_payments_usd": "Reported Payments (USD)",
    },
    color_discrete_sequence=["#008C71"],
)

payment_chart.update_traces(
    hovertemplate="Year: %{x}<br>Payments: $%{y:,.2f}<extra></extra>"
)

payment_chart.update_layout(
    xaxis=dict(type="category"),
    yaxis_tickprefix="$",
    yaxis_tickformat="~s",
)

st.plotly_chart(payment_chart, width="stretch")

# Claim count chart
st.markdown("### Historical Claim Volume")

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
    hovertemplate="Year: %{x}<br>Claim records: %{y:,}<extra></extra>"
)

claims_chart.update_layout(
    xaxis=dict(type="category"),
)

st.plotly_chart(claims_chart, width="stretch")

# Underlying data
with st.expander("View underlying annual data"):
    st.dataframe(
        annual,
        hide_index=True,
        width="stretch",
    )

# Data limitations
st.info(
    "Geographic matching uses a 2025 HUD ZIP-to-county crosswalk. "
    "A Pinellas-linked ZIP does not establish the exact historical "
    "location of every claim. Payments are nominal and are not "
    "adjusted for inflation. Claim counts are not exposure-adjusted "
    "risk rates. Recent years may contain incomplete records."
)


# Geographic visualization
st.markdown("---")
st.markdown("### Geographic Distribution of Historical NFIP Payments")

MAP_PATH = (
    Path(__file__).resolve().parent
    / "reports"
    / "nfip_pinellas_zcta_map.svg"
)

if MAP_PATH.exists():
    st.image(str(MAP_PATH), width="stretch")
    st.caption(
        "2025 Census ZCTA polygons clipped to Pinellas County. "
        "Historical ZIP-level payments are shown for geographic illustration; "
        "these are not flood-risk rates."
    )
else:
    st.warning("Geographic map not found in the reports folder.")

# --------------------------------------------------
# ZIP Code Comparison
# --------------------------------------------------

st.divider()
st.header("ZIP Code Comparison")

st.caption(
    "Compare historical NFIP claim payments across ZIP codes "
    "linked to Pinellas County."
)

ZIP_DATA_PATH = (
    Path(__file__).resolve().parent
    / "data"
    / "processed"
    / "nfip_payments_by_zip_hud.csv"
)


@st.cache_data
def load_zip_data():
    return pd.read_csv(
        ZIP_DATA_PATH,
        dtype={"reported_zip_5": str},
    )


if ZIP_DATA_PATH.exists():
    zip_df = load_zip_data()

    # Only include ZIPs linked to Pinellas County
    zip_df = zip_df[
        zip_df["hud_status"] == "hud_pinellas_link"
    ].copy()

    zip_options = sorted(
        zip_df["reported_zip_5"].dropna().unique().tolist()
    )

    default_zips = [
        z for z in ["33706", "33703", "33708"]
        if z in zip_options
    ]

    selected_zips = st.multiselect(
        "Select ZIP Codes to Compare",
        options=zip_options,
        default=default_zips,
    )

    comparison = zip_df[
        zip_df["reported_zip_5"].isin(selected_zips)
    ].copy()

    if not comparison.empty:

        # Average payment per claim with a positive payment
        comparison["avg_positive_claim_payment"] = (
            comparison["gross_reported_payments_usd"]
            / comparison["positive_payment_claims"].replace(0, float("nan"))
        )

        col1, col2 = st.columns(2)

        with col1:
            payments_fig = px.bar(
                comparison,
                x="reported_zip_5",
                y="gross_reported_payments_usd",
                title="Total Historical Payments by ZIP",
                labels={
                    "reported_zip_5": "ZIP Code",
                    "gross_reported_payments_usd": "Payments (USD)",
                },
                color_discrete_sequence=["#008C71"],
            )

            st.plotly_chart(payments_fig, width="stretch")

        with col2:
            claims_fig = px.bar(
                comparison,
                x="reported_zip_5",
                y="claim_records",
                title="Historical Claim Records by ZIP",
                labels={
                    "reported_zip_5": "ZIP Code",
                    "claim_records": "Claim Records",
                },
                color_discrete_sequence=["#176B87"],
            )

            st.plotly_chart(claims_fig, width="stretch")

        st.markdown("### Detailed ZIP Comparison")

        display_df = comparison[
            [
                "reported_zip_5",
                "claim_records",
                "positive_payment_claims",
                "gross_reported_payments_usd",
                "avg_positive_claim_payment",
            ]
        ].rename(
            columns={
                "reported_zip_5": "ZIP Code",
                "claim_records": "Claim Records",
                "positive_payment_claims": "Claims With Positive Payments",
                "gross_reported_payments_usd": "Total Payments ($)",
                "avg_positive_claim_payment": "Avg. Payment per Positive-Payment Claim ($)",
            }
        )

        st.dataframe(
            display_df,
            hide_index=True,
            width="stretch",
            column_config={
                "Total Payments ($)": st.column_config.NumberColumn(
                    format="$%.2f"
                ),
                "Avg. Payment per Positive-Payment Claim ($)":
                    st.column_config.NumberColumn(format="$%.2f"),
            },
        )

    else:
        st.info("Select at least one ZIP code to view comparisons.")

    st.caption(
        "ZIP-level totals cover all available years in the source summary. "
        "They do not respond to the year filter above. "
        "ZIP codes are linked to Pinellas using the 2025 HUD crosswalk; "
        "the values are not exposure-adjusted flood-risk rates."
    )

else:
    st.warning("ZIP comparison dataset was not found.")
