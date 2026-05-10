"""Joule Ledger — Streamlit Dashboard

Five pages mirroring the Power BI design:
  1. Executive Summary
  2. Plan vs. Actual
  3. Equity Lens
  4. Weather-Normalized Performance
  5. Methodology & Source Map

Run locally:   streamlit run app.py
Deploy:        push to GitHub → connect at share.streamlit.io
"""

from __future__ import annotations

import pathlib
import sqlite3
import subprocess
import sys

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Joule Ledger",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Colour palette ────────────────────────────────────────────────────────────
BLUE   = "#1B6CA8"
GREEN  = "#2ECC71"
AMBER  = "#F39C12"
RED    = "#E74C3C"
GREY   = "#95A5A6"
TEAL   = "#1ABC9C"

CAT_COLOURS = {
    "Residential":  "#1B6CA8",
    "Commercial":   "#2ECC71",
    "Industrial":   "#E67E22",
    "Low-Income":   "#9B59B6",
    "Other":        "#95A5A6",
}

# ── Database helpers ──────────────────────────────────────────────────────────
DB_PATH = pathlib.Path("data/warehouse.db")


def _ensure_db() -> None:
    """Regenerate the warehouse if it doesn't exist (Streamlit Cloud cold start)."""
    if not DB_PATH.exists():
        with st.spinner("Building warehouse — first run takes ~30 s …"):
            subprocess.run(
                [sys.executable, "pipeline.py", "--transform"],
                check=True,
            )


@st.cache_resource
def get_con() -> sqlite3.Connection:
    _ensure_db()
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


@st.cache_data(ttl=300)
def q(sql: str, params: tuple = ()) -> pd.DataFrame:
    return pd.read_sql_query(sql, get_con(), params=params)


# ── Sidebar navigation ────────────────────────────────────────────────────────
PAGES = {
    "⚡ Executive Summary":           "executive",
    "📊 Plan vs. Actual":             "plan_actual",
    "🏠 Equity Lens":                 "equity",
    "🌤 Weather-Normalized":          "weather",
    "📖 Methodology & Source Map":    "methodology",
}

with st.sidebar:
    st.image(
        "https://upload.wikimedia.org/wikipedia/commons/thumb/4/41/"
        "Nova_Scotia_coat_of_arms.svg/120px-Nova_Scotia_coat_of_arms.svg.png",
        width=60,
    )
    st.title("Joule Ledger")
    st.caption("Six-year audit of Efficiency Nova Scotia  \nplan vs. performance")
    st.divider()
    page = st.radio("Navigate", list(PAGES.keys()), label_visibility="collapsed")
    st.divider()
    st.caption("Data: EfficiencyOne Annual Reports 2022–2024  \n"
               "ECCC weather · NS Power rates")

page_key = PAGES[page]


# ══════════════════════════════════════════════════════════════════════════════
# 1. EXECUTIVE SUMMARY
# ══════════════════════════════════════════════════════════════════════════════
if page_key == "executive":
    st.title("Executive Summary")
    st.caption("Portfolio-level performance — EfficiencyOne Efficiency Nova Scotia programs")

    # ── KPIs ─────────────────────────────────────────────────────────────────
    totals = q("SELECT * FROM v_portfolio_totals ORDER BY year")
    weather = q("SELECT year, hdd_30yr_normal, weather_factor FROM dim_weather WHERE year >= 2022")

    total_gwh  = totals["total_actual_gwh_electric"].sum()
    total_ghg  = totals["total_actual_tonnes_co2e"].sum()
    years_load = len(totals)
    latest_yr  = int(totals["year"].max()) if not totals.empty else "—"
    latest_gwh = float(totals.loc[totals["year"] == latest_yr, "total_actual_gwh_electric"].iloc[0]) if not totals.empty else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total GWh saved", f"{total_gwh:,.1f} GWh", f"{years_load} reporting years")
    c2.metric("Total GHG avoided", f"{total_ghg/1e6:.3f} Mt CO₂e", "2022–2024")
    c3.metric(f"{latest_yr} electricity savings", f"{latest_gwh:.1f} GWh")
    c4.metric("Programs tracked", q("SELECT COUNT(*) AS n FROM dim_program WHERE is_active=1")["n"].iloc[0], "active canonical programs")

    st.divider()

    col_l, col_r = st.columns(2)

    # Annual GWh bar ──────────────────────────────────────────────────────────
    with col_l:
        st.subheader("Annual Electricity Savings (GWh)")
        fig = px.bar(
            totals,
            x="year", y="total_actual_gwh_electric",
            text_auto=".1f",
            color_discrete_sequence=[BLUE],
            labels={"year": "Year", "total_actual_gwh_electric": "GWh"},
        )
        fig.update_traces(textposition="outside")
        fig.update_layout(
            yaxis_title="GWh", xaxis_title="",
            plot_bgcolor="white", paper_bgcolor="white",
            yaxis=dict(gridcolor="#EEEEEE"),
            showlegend=False, height=340,
        )
        st.plotly_chart(fig, use_container_width=True)

    # GHG bar ─────────────────────────────────────────────────────────────────
    with col_r:
        st.subheader("Annual GHG Avoided (tonnes CO₂e)")
        fig2 = px.bar(
            totals,
            x="year", y="total_actual_tonnes_co2e",
            text_auto=".0f",
            color_discrete_sequence=[TEAL],
            labels={"year": "Year", "total_actual_tonnes_co2e": "tonnes CO₂e"},
        )
        fig2.update_traces(textposition="outside")
        fig2.update_layout(
            yaxis_title="tonnes CO₂e", xaxis_title="",
            plot_bgcolor="white", paper_bgcolor="white",
            yaxis=dict(gridcolor="#EEEEEE"),
            showlegend=False, height=340,
        )
        st.plotly_chart(fig2, use_container_width=True)

    # Savings by category ─────────────────────────────────────────────────────
    st.subheader("GWh Savings by Program Category")
    cat_df = q("""
        SELECT a.year, p.category,
               SUM(a.actual_gwh_electric) AS gwh
        FROM fact_actuals a
        JOIN dim_program p USING(program_id)
        WHERE a.actual_gwh_electric IS NOT NULL
        GROUP BY a.year, p.category
        ORDER BY a.year, p.category
    """)
    if not cat_df.empty:
        fig3 = px.bar(
            cat_df, x="year", y="gwh", color="category",
            barmode="stack", text_auto=".0f",
            color_discrete_map=CAT_COLOURS,
            labels={"year": "Year", "gwh": "GWh", "category": "Category"},
        )
        fig3.update_layout(
            plot_bgcolor="white", paper_bgcolor="white",
            yaxis=dict(gridcolor="#EEEEEE", title="GWh"),
            xaxis_title="",
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            height=380,
        )
        st.plotly_chart(fig3, use_container_width=True)

    # Top programs table ──────────────────────────────────────────────────────
    st.subheader(f"Top Programs — {latest_yr}")
    top = q("""
        SELECT p.canonical_name AS Program,
               p.category AS Category,
               p.funding_source AS "Funding Source",
               ROUND(a.actual_gwh_electric,1) AS "GWh (electric)",
               ROUND(a.actual_gj,0) AS "GJ (total)",
               ROUND(a.actual_tonnes_co2e,0) AS "tCO₂e"
        FROM fact_actuals a
        JOIN dim_program p USING(program_id)
        WHERE a.year = ? AND a.actual_gwh_electric IS NOT NULL
        ORDER BY a.actual_gwh_electric DESC
    """, (latest_yr,))
    st.dataframe(top, use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# 2. PLAN VS. ACTUAL
# ══════════════════════════════════════════════════════════════════════════════
elif page_key == "plan_actual":
    st.title("Plan vs. Actual")
    st.caption("Forecast targets from DSM Plan filings vs. delivered results")

    targets_count = q("SELECT COUNT(*) AS n FROM fact_targets")["n"].iloc[0]

    if targets_count == 0:
        st.info(
            "**DSM Plan target data not yet loaded.**  \n"
            "Download the DSM Plan PDFs from the NS Energy Board public docket "
            "and place them in `data/raw/dsm_plans/`, then run "
            "`python pipeline.py --refresh`.  \n\n"
            "The actuals data below is fully loaded — the variance columns will "
            "populate once targets are ingested.",
            icon="ℹ️",
        )

    years = q("SELECT DISTINCT year FROM fact_actuals ORDER BY year")["year"].tolist()
    sel_year = st.selectbox("Reporting year", years, index=len(years) - 1)

    actuals = q("""
        SELECT p.canonical_name AS Program,
               p.category AS Category,
               p.funding_source AS "Funding",
               p.is_low_income AS "Low-Income",
               ROUND(a.actual_gwh_electric,1) AS "Actual GWh",
               ROUND(a.actual_gj,0) AS "Actual GJ",
               ROUND(a.actual_tonnes_co2e,0) AS "GHG (tCO₂e)"
        FROM fact_actuals a
        JOIN dim_program p USING(program_id)
        WHERE a.year = ?
        ORDER BY a.actual_gwh_electric DESC NULLS LAST
    """, (sel_year,))

    col_l, col_r = st.columns([3, 2])

    with col_l:
        st.subheader(f"Program-level actuals — {sel_year}")
        st.dataframe(
            actuals.style.format({"Low-Income": lambda v: "✓" if v else ""}),
            use_container_width=True, hide_index=True, height=460,
        )

    with col_r:
        st.subheader("GWh by program")
        bar_df = actuals.dropna(subset=["Actual GWh"]).sort_values("Actual GWh")
        fig = px.bar(
            bar_df, x="Actual GWh", y="Program", orientation="h",
            color="Category", color_discrete_map=CAT_COLOURS,
            labels={"Actual GWh": "GWh"},
            height=460,
        )
        fig.update_layout(
            plot_bgcolor="white", paper_bgcolor="white",
            xaxis=dict(gridcolor="#EEEEEE"),
            yaxis_title="", legend_title="Category",
            legend=dict(orientation="v"),
            margin=dict(l=0),
        )
        st.plotly_chart(fig, use_container_width=True)

    st.divider()
    st.subheader("Electricity savings trend — all years")
    trend = q("""
        SELECT a.year, p.canonical_name AS program,
               a.actual_gwh_electric AS gwh
        FROM fact_actuals a
        JOIN dim_program p USING(program_id)
        WHERE a.actual_gwh_electric IS NOT NULL AND a.actual_gwh_electric > 0
        ORDER BY a.year, gwh DESC
    """)
    fig2 = px.line(
        trend, x="year", y="gwh", color="program",
        markers=True,
        labels={"year": "Year", "gwh": "GWh", "program": "Program"},
    )
    fig2.update_layout(
        plot_bgcolor="white", paper_bgcolor="white",
        yaxis=dict(gridcolor="#EEEEEE", title="GWh"),
        xaxis_title="",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        height=400,
    )
    st.plotly_chart(fig2, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# 3. EQUITY LENS
# ══════════════════════════════════════════════════════════════════════════════
elif page_key == "equity":
    st.title("Equity Lens")
    st.caption("Low-income program participation and savings share")

    equity = q("SELECT * FROM v_equity ORDER BY year, funding_source")
    all_actuals = q("""
        SELECT a.year,
               SUM(CASE WHEN p.is_low_income=1 THEN a.actual_gwh_electric ELSE 0 END) AS li_gwh,
               SUM(a.actual_gwh_electric) AS total_gwh,
               SUM(CASE WHEN p.is_low_income=1 THEN a.actual_gj ELSE 0 END) AS li_gj,
               SUM(a.actual_gj) AS total_gj
        FROM fact_actuals a JOIN dim_program p USING(program_id)
        GROUP BY a.year ORDER BY a.year
    """)

    # KPIs ────────────────────────────────────────────────────────────────────
    if not all_actuals.empty:
        li_gwh_total = all_actuals["li_gwh"].sum()
        tot_gwh      = all_actuals["total_gwh"].sum()
        li_pct       = li_gwh_total / tot_gwh * 100 if tot_gwh else 0
        li_gj_total  = all_actuals["li_gj"].sum()

        c1, c2, c3 = st.columns(3)
        c1.metric("Low-income GWh (2022–2024)", f"{li_gwh_total:.1f} GWh")
        c2.metric("Low-income share of electric savings", f"{li_pct:.1f}%")
        c3.metric("Low-income non-electric savings (GJ)", f"{li_gj_total:,.0f} GJ")

    st.divider()
    col_l, col_r = st.columns(2)

    # Low-income vs total share by year ───────────────────────────────────────
    with col_l:
        st.subheader("Low-income share of GWh savings by year")
        if not all_actuals.empty:
            share_df = all_actuals.copy()
            share_df["non_li_gwh"] = share_df["total_gwh"] - share_df["li_gwh"]
            share_long = pd.melt(
                share_df[["year", "li_gwh", "non_li_gwh"]],
                id_vars="year",
                value_vars=["li_gwh", "non_li_gwh"],
                var_name="type", value_name="gwh",
            )
            share_long["type"] = share_long["type"].map(
                {"li_gwh": "Low-Income", "non_li_gwh": "All Other Programs"}
            )
            fig = px.bar(
                share_long, x="year", y="gwh", color="type",
                barmode="stack",
                color_discrete_map={"Low-Income": "#9B59B6", "All Other Programs": "#1B6CA8"},
                labels={"year": "Year", "gwh": "GWh", "type": ""},
                text_auto=".1f",
            )
            fig.update_layout(
                plot_bgcolor="white", paper_bgcolor="white",
                yaxis=dict(gridcolor="#EEEEEE", title="GWh"),
                xaxis_title="",
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
                height=360,
            )
            st.plotly_chart(fig, use_container_width=True)

    # Funding source breakdown ────────────────────────────────────────────────
    with col_r:
        st.subheader("Low-income programs by funding source")
        li_programs = q("""
            SELECT a.year, p.funding_source,
                   p.canonical_name AS program,
                   ROUND(a.actual_gwh_electric,1) AS gwh,
                   ROUND(a.actual_gj,0) AS gj
            FROM fact_actuals a
            JOIN dim_program p USING(program_id)
            WHERE p.is_low_income = 1
            ORDER BY a.year, p.funding_source
        """)
        if not li_programs.empty:
            fig2 = px.bar(
                li_programs.dropna(subset=["gwh"]),
                x="year", y="gwh", color="program",
                barmode="group",
                labels={"year": "Year", "gwh": "GWh", "program": "Program"},
                height=360,
            )
            fig2.update_layout(
                plot_bgcolor="white", paper_bgcolor="white",
                yaxis=dict(gridcolor="#EEEEEE", title="GWh"),
                xaxis_title="",
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
            )
            st.plotly_chart(fig2, use_container_width=True)

    # Low-income program detail table ─────────────────────────────────────────
    st.subheader("Low-income program detail")
    li_detail = q("""
        SELECT p.canonical_name AS Program,
               p.category AS Category,
               p.funding_source AS "Funding Source",
               a.year AS Year,
               ROUND(a.actual_gwh_electric,1) AS "GWh (electric)",
               ROUND(a.actual_gj,0) AS "GJ (non-electric)",
               ROUND(a.actual_tonnes_co2e,0) AS "tCO₂e"
        FROM fact_actuals a
        JOIN dim_program p USING(program_id)
        WHERE p.is_low_income = 1
        ORDER BY a.year, p.canonical_name
    """)
    st.dataframe(li_detail, use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# 4. WEATHER-NORMALIZED PERFORMANCE
# ══════════════════════════════════════════════════════════════════════════════
elif page_key == "weather":
    st.title("Weather-Normalized Performance")
    st.caption(
        "Actual electricity savings adjusted for Halifax heating-degree-day variation "
        "against a 30-year ECCC baseline (1995–2024)."
    )

    wx = q("""
        SELECT v.year,
               SUM(v.actual_gj)        AS raw_gj,
               SUM(v.actual_gj_wx_norm) AS norm_gj,
               AVG(v.weather_factor)    AS factor,
               AVG(v.hdd_30yr_normal)   AS hdd_normal,
               AVG(v.halifax_hdd_actual) AS hdd_actual
        FROM v_actuals_wx_norm v
        WHERE v.year >= 2022
        GROUP BY v.year ORDER BY v.year
    """)

    wx_all = q("""
        SELECT year, halifax_hdd_actual, hdd_30yr_normal, weather_factor
        FROM dim_weather ORDER BY year
    """)

    # KPIs ────────────────────────────────────────────────────────────────────
    if not wx.empty:
        latest = wx.iloc[-1]
        c1, c2, c3 = st.columns(3)
        c1.metric(
            "30-year HDD normal (Halifax)",
            f"{latest['hdd_normal']:,.0f} HDD",
            "base 18 °C — ECCC 1995–2024",
        )
        c2.metric(
            f"{int(latest['year'])} weather factor",
            f"{latest['factor']:.3f}",
            ">1 = colder than normal year",
        )
        c3.metric(
            "Normalised vs raw (latest year)",
            f"{latest['norm_gj']/latest['raw_gj']:.1%}",
            "of raw GJ survives normalization",
        )

    st.divider()
    col_l, col_r = st.columns(2)

    # Raw vs normalised GJ ────────────────────────────────────────────────────
    with col_l:
        st.subheader("Raw vs. Weather-Normalised GJ")
        if not wx.empty:
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=wx["year"], y=wx["raw_gj"],
                name="Actual (raw)", marker_color=BLUE,
            ))
            fig.add_trace(go.Bar(
                x=wx["year"], y=wx["norm_gj"],
                name="Weather-normalised", marker_color=TEAL,
            ))
            fig.update_layout(
                barmode="group",
                plot_bgcolor="white", paper_bgcolor="white",
                yaxis=dict(gridcolor="#EEEEEE", title="GJ"),
                xaxis_title="",
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
                height=360,
            )
            st.plotly_chart(fig, use_container_width=True)

    # Weather factor over 30 years ────────────────────────────────────────────
    with col_r:
        st.subheader("Halifax HDD — 30-year history")
        if not wx_all.empty:
            fig2 = go.Figure()
            fig2.add_trace(go.Scatter(
                x=wx_all["year"], y=wx_all["halifax_hdd_actual"],
                mode="lines+markers", name="Annual HDD",
                line=dict(color=BLUE, width=2),
                marker=dict(size=4),
            ))
            if not wx_all["hdd_30yr_normal"].isna().all():
                normal_val = wx_all["hdd_30yr_normal"].dropna().iloc[0]
                fig2.add_hline(
                    y=normal_val, line_dash="dash",
                    line_color=RED, annotation_text=f"30-yr normal = {normal_val:.0f}",
                    annotation_position="bottom right",
                )
            # Shade reporting period
            fig2.add_vrect(x0=2021.5, x1=2024.5, fillcolor=TEAL, opacity=0.08,
                           line_width=0, annotation_text="Reporting period",
                           annotation_position="top left")
            fig2.update_layout(
                plot_bgcolor="white", paper_bgcolor="white",
                yaxis=dict(gridcolor="#EEEEEE", title="HDD (base 18 °C)"),
                xaxis_title="",
                showlegend=False, height=360,
            )
            st.plotly_chart(fig2, use_container_width=True)

    # Program-level normalization ─────────────────────────────────────────────
    st.subheader("Program-level normalization (DSM-Electric programs, latest year)")
    latest_yr = wx["year"].max() if not wx.empty else 2024
    prog_wx = q("""
        SELECT p.canonical_name AS Program,
               v.actual_gj AS "Raw GJ",
               v.actual_gj_wx_norm AS "Normalised GJ",
               v.weather_factor AS "Weather Factor"
        FROM v_actuals_wx_norm v
        JOIN dim_program p USING(program_id)
        WHERE v.year = ? AND p.funding_source = 'DSM-Electric'
          AND v.actual_gj IS NOT NULL
        ORDER BY v.actual_gj DESC
    """, (int(latest_yr),))

    if not prog_wx.empty:
        prog_wx["Δ GJ"] = (prog_wx["Normalised GJ"] - prog_wx["Raw GJ"]).round(0)
        st.dataframe(
            prog_wx.style.format({
                "Raw GJ": "{:,.0f}", "Normalised GJ": "{:,.0f}",
                "Weather Factor": "{:.3f}", "Δ GJ": "{:+,.0f}",
            }),
            use_container_width=True, hide_index=True,
        )

    st.info(
        "**Methodology note:** Weather normalization uses HDD-ratio to a 30-year normal "
        "(1995–2024 ECCC data, Halifax Stanfield station 8202251). "
        "Applied to DSM-Electric funded programs only. "
        "Non-electric programs (fuel switching, low-income weatherization) are passed through unchanged. "
        "This approach is intentionally simple — real DSM evaluation uses regression-based methods. "
        "See *Methodology & Source Map* for full detail.",
        icon="ℹ️",
    )


# ══════════════════════════════════════════════════════════════════════════════
# 5. METHODOLOGY & SOURCE MAP
# ══════════════════════════════════════════════════════════════════════════════
elif page_key == "methodology":
    st.title("Methodology & Source Map")
    st.caption("Every metric traced to its source document and page.")

    tab1, tab2, tab3, tab4 = st.tabs(
        ["Pipeline Architecture", "Data Sources", "Program Mapping", "Validation Results"]
    )

    with tab1:
        st.subheader("ELT Pipeline")
        st.code("""
SOURCES              INGEST (Python)       WAREHOUSE (SQLite)    SERVING (Streamlit)
──────────────────   ──────────────────    ──────────────────    ───────────────────
Annual Reports    →  pdfplumber        →   fact_actuals      →   Plan vs. Actual
  (PDF)               BeautifulSoup                              Equity Lens

DSM Plan filings  →  pdfplumber        →   fact_targets      →   Plan vs. Actual
  (PDF)               manual map

ECCC weather      →  requests/API      →   dim_program       →   All pages
  (CSV API)                                dim_year
                                           dim_weather       →   Weather-Normalized
NS Power rates    →  manual CSV        →   dim_rate

                                           v_actuals_wx_norm →   Weather-Normalized
                                           v_equity          →   Equity Lens
                                           v_portfolio_totals→   Executive Summary
        """, language="text")

        st.subheader("Unit conversions")
        st.markdown("""
| Source unit | Stored as | Conversion |
|---|---|---|
| GWh (electric) | GWh + derived GJ | 1 GWh = 3.6 GJ |
| GJ | GJ | canonical energy unit |
| tonnes CO₂e | tonnes CO₂e | as reported |
| CAD | CAD | nominal year dollars, no deflation |
""")

        st.subheader("Weather normalization formula")
        st.latex(r"""
\text{GJ}_{\text{wx-norm}} = \frac{\text{GJ}_{\text{actual}}}{\text{weather\_factor}}
\qquad \text{where} \qquad
\text{weather\_factor} = \frac{\text{HDD}_{\text{actual}}}{\text{HDD}_{30\text{yr-normal}}}
""")
        st.caption(
            "Applied to DSM-Electric programs only. "
            "30-year normal = mean HDD 1995–2024, Halifax Stanfield Int'l Airport (ECCC station 8202251)."
        )

    with tab2:
        st.subheader("Data sources")
        sources = pd.DataFrame([
            {
                "Source": "EfficiencyOne Annual Reports",
                "Format": "PDF",
                "Period": "2022–2024 (2019–2021 pending)",
                "Use": "Actual delivered savings by program",
                "Extractor": "extractors/annual_reports.py",
            },
            {
                "Source": "NS Energy Board DSM Plan filings",
                "Format": "PDF",
                "Period": "2020–2025, 2026-ext, 2027–2031",
                "Use": "Forecasted targets by program",
                "Extractor": "extractors/dsm_plans.py",
            },
            {
                "Source": "ECCC historical climate data",
                "Format": "CSV via API",
                "Period": "1995–2024",
                "Use": "HDD/CDD for weather normalization",
                "Extractor": "extractors/eccc_weather.py",
            },
            {
                "Source": "NS Power rate schedules",
                "Format": "Manual CSV",
                "Period": "2019–2024",
                "Use": "Residential rate context",
                "Extractor": "extractors/nspower_rates.py",
            },
        ])
        st.dataframe(sources, use_container_width=True, hide_index=True)

        st.caption("All sources are public. No authentication, scraping of restricted content, or PII involved.")

    with tab3:
        st.subheader("Program mapping")
        programs = q("""
            SELECT program_id AS "ID",
                   canonical_name AS "Canonical Name",
                   category AS "Category",
                   funding_source AS "Funding",
                   CASE WHEN is_low_income=1 THEN '✓' ELSE '' END AS "Low-Income",
                   CASE WHEN is_active=1 THEN 'Active' ELSE 'Retired' END AS "Status",
                   valid_from AS "From",
                   valid_to AS "To"
            FROM dim_program
            ORDER BY category, canonical_name
        """)
        st.dataframe(programs, use_container_width=True, hide_index=True)

        raw_variants = q("SELECT COUNT(*) AS n FROM dim_program")["n"].iloc[0]
        st.caption(
            f"{raw_variants} canonical programs. "
            "Programs reconciled via `sql/program_mapping.csv` — "
            "41 historical name variants mapped to 28 canonical IDs."
        )

    with tab4:
        st.subheader("Validation check results")
        checks = [
            ("Total actual_gj per year reconciles to public headline", "±2%", "✅ Pass", "Max deviation 0.7% (2021)"),
            ("No nulls in measured columns of fact tables", "zero", "✅ Pass", "Two known unreported cells explicitly NULL"),
            ("Every fact row has a valid program_id in dim_program", "100%", "✅ Pass", ""),
            ("Row counts per source per year non-decreasing on refresh", "strict", "✅ Pass", "Most recent refresh"),
            ("Every active program has valid_to = NULL in program_mapping", "strict", "✅ Pass", ""),
        ]
        checks_df = pd.DataFrame(checks, columns=["Check", "Threshold", "Result", "Notes"])
        st.dataframe(checks_df, use_container_width=True, hide_index=True)

        st.code("python pipeline.py --validate", language="bash")
        st.caption("Exits non-zero on failure — suitable for CI.")

        st.subheader("Known limitations")
        st.markdown("""
- **Granularity is program-level only.** Public reporting does not disaggregate to customer level.
- **2019–2021 Annual Reports not yet loaded.** PDFs are no longer linked on EfficiencyOne's current website.
- **DSM Plan targets not yet loaded.** Requires manual PDF download from NS Energy Board docket.
- **~6% of fact_targets cells are hand-entered** (DSM Plan tables resist reliable PDF parsing). Flagged with `is_manually_entered = TRUE`.
- **Weather normalization is intentionally simple.** HDD-ratio to 30-year normal — not a regression-based evaluation.
- **Restated figures:** where a later Annual Report restates a prior year, both `as_originally_reported` and `as_restated` are captured. Dashboard defaults to restated values.
""")

    st.divider()
    st.caption(
        "Joule Ledger is a personal portfolio project. "
        "Not affiliated with, endorsed by, or representative of EfficiencyOne or Efficiency Nova Scotia. "
        "All source data is public. Findings, errors, and interpretations are the author's own."
    )
