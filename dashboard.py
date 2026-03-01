"""Portfolio Dashboard — single-file Streamlit app.

Launch:
    uv run streamlit run dashboard.py
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

OUTPUT_DIR = Path("output")

TRADFI_CATEGORIES = {"Japanese Securities", "iDeCo"}
NON_RISK_CATEGORIES = {"JPY Cash", "USD Stables"}
MERGE_CATEGORIES = {"iDeCo": "Japanese Securities"}

# Display name overrides (symbol → label)
DISPLAY_NAMES = {
    "楽天証券": "オルカン (Rakuten Sec)",
}
# Category display names (after merge)
CATEGORY_DISPLAY_NAMES = {
    "Japanese Securities": "Japanese Securities (オルカン + iDeCo)",
}

st.set_page_config(
    page_title="Portfolio Dashboard",
    page_icon="📊",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------


def _parse_jpy(value: str) -> float:
    """Parse a JPY string like '1,234,567' into a float."""
    if isinstance(value, (int, float)):
        return float(value)
    return float(str(value).replace(",", "").replace('"', ""))


def _parse_pct(value: str) -> float:
    """Parse percentage string like '47.35%' or '<0.01%' into a float."""
    s = str(value).strip().rstrip("%")
    if s.startswith("<"):
        return float(s[1:]) / 2  # approximate
    return float(s)


def _parse_amount(value: str) -> float | None:
    """Parse total_amount; returns None for '-'."""
    s = str(value).strip().replace(",", "").replace('"', "")
    if s in ("-", "", "nan"):
        return None
    return float(s)


# ---------------------------------------------------------------------------
# Data loading (cached)
# ---------------------------------------------------------------------------


def _discover_dates() -> list[str]:
    """Return sorted list of YYYYMMDD snapshot directories."""
    if not OUTPUT_DIR.exists():
        return []
    dates = [
        d.name
        for d in OUTPUT_DIR.iterdir()
        if d.is_dir() and re.fullmatch(r"\d{8}", d.name)
    ]
    return sorted(dates)


@st.cache_data
def load_asset_csv(date: str) -> pd.DataFrame:
    path = OUTPUT_DIR / date / "portfolio_by_asset.csv"
    df = pd.read_csv(path, dtype=str)
    df["jpy_value"] = df["total_jpy_value"].apply(_parse_jpy)
    df["pct"] = df["percentage"].apply(_parse_pct)
    df["amount"] = df["total_amount"].apply(_parse_amount)
    return df


@st.cache_data
def load_exposure_csv(date: str) -> pd.DataFrame:
    path = OUTPUT_DIR / date / "portfolio_by_exposure.csv"
    df = pd.read_csv(path, dtype=str)
    df["jpy_value"] = df["total_jpy_value"].apply(_parse_jpy)
    df["pct"] = df["percentage"].apply(_parse_pct)
    return df


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    dates = _discover_dates()
    if not dates:
        st.error("No snapshot directories found under `output/`.")
        st.stop()

    # -- Sidebar ----------------------------------------------------------
    st.sidebar.title("Portfolio Dashboard")
    selected_date = st.sidebar.selectbox(
        "Snapshot date",
        dates,
        index=len(dates) - 1,
        format_func=lambda d: f"{d[:4]}-{d[4:6]}-{d[6:]}",
    )
    st.sidebar.caption(f"{len(dates)} snapshot(s) available")

    asset_df = load_asset_csv(selected_date)
    exposure_df = load_exposure_csv(selected_date)

    formatted_date = f"{selected_date[:4]}-{selected_date[4:6]}-{selected_date[6:]}"
    st.title(f"Portfolio — {formatted_date}")

    # -- Section 1: KPI cards --------------------------------------------
    total_jpy = asset_df["jpy_value"].sum()
    num_assets = len(asset_df)
    top_row = asset_df.iloc[0]
    top_name = DISPLAY_NAMES.get(top_row["symbol"], top_row["symbol"])
    top_pct = top_row["pct"]

    non_risk_value = exposure_df.loc[
        exposure_df["category"].isin(NON_RISK_CATEGORIES), "jpy_value"
    ].sum()
    non_risk_ratio = non_risk_value / total_jpy * 100 if total_jpy else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Value", f"¥{total_jpy:,.0f}")
    c2.metric("Assets", num_assets)
    c3.metric("Top Position", f"{top_name} ({top_pct:.1f}%)")
    c4.metric("Non-risk Ratio", f"{non_risk_ratio:.1f}%")

    # -- Section 2: Donut charts -----------------------------------------
    st.subheader("Allocation")
    left, right = st.columns(2)

    # Merge categories (e.g. iDeCo → Japanese Securities) for display
    merged_exp = exposure_df.copy()
    merged_exp["category"] = merged_exp["category"].replace(MERGE_CATEGORIES)
    merged_exp = merged_exp.groupby("category", as_index=False)["jpy_value"].sum()
    merged_exp["category"] = merged_exp["category"].replace(CATEGORY_DISPLAY_NAMES)

    with left:
        fig_cat = px.pie(
            merged_exp,
            values="jpy_value",
            names="category",
            hole=0.45,
            title="By Category",
        )
        fig_cat.update_traces(textposition="inside", textinfo="label+percent")
        fig_cat.update_layout(showlegend=False, margin=dict(t=40, b=0, l=0, r=0))
        st.plotly_chart(fig_cat, use_container_width=True)

    with right:
        non_risk_val = exposure_df.loc[
            exposure_df["category"].isin(NON_RISK_CATEGORIES), "jpy_value"
        ].sum()
        tradfi_val = exposure_df.loc[
            exposure_df["category"].isin(TRADFI_CATEGORIES), "jpy_value"
        ].sum()
        crypto_val = total_jpy - non_risk_val - tradfi_val
        split_df = pd.DataFrame(
            {
                "type": ["Risk (Crypto)", "Risk (TradFi)", "Non-risk"],
                "jpy_value": [crypto_val, tradfi_val, non_risk_val],
            }
        )
        fig_split = px.pie(
            split_df,
            values="jpy_value",
            names="type",
            hole=0.45,
            title="Risk Breakdown",
            color="type",
            color_discrete_map={
                "Risk (Crypto)": "#636EFA",
                "Risk (TradFi)": "#EF553B",
                "Non-risk": "#00CC96",
            },
        )
        fig_split.update_traces(textposition="inside", textinfo="label+percent")
        fig_split.update_layout(showlegend=False, margin=dict(t=40, b=0, l=0, r=0))
        st.plotly_chart(fig_split, use_container_width=True)

    # -- Section 3: Top 10 holdings bar chart ----------------------------
    st.subheader("Top 10 Holdings")
    top10 = asset_df.nlargest(10, "jpy_value").sort_values("jpy_value").copy()
    top10["label"] = top10["symbol"].replace(DISPLAY_NAMES)
    fig_bar = px.bar(
        top10,
        x="jpy_value",
        y="label",
        orientation="h",
        text=top10["jpy_value"].apply(lambda v: f"¥{v:,.0f}"),
        labels={"jpy_value": "JPY Value", "label": ""},
    )
    fig_bar.update_traces(textposition="outside")
    fig_bar.update_layout(
        yaxis=dict(categoryorder="total ascending"),
        margin=dict(t=10, b=10),
        height=400,
    )
    st.plotly_chart(fig_bar, use_container_width=True)

    # -- Section 4: Concentration risk -----------------------------------
    st.subheader("Concentration Risk")
    sorted_pcts = asset_df["pct"].sort_values(ascending=False).values
    cumulative = sorted_pcts.cumsum()

    top1 = cumulative[0] if len(cumulative) >= 1 else 0
    top3 = cumulative[2] if len(cumulative) >= 3 else cumulative[-1]
    top5 = cumulative[4] if len(cumulative) >= 5 else cumulative[-1]
    top10_pct = cumulative[9] if len(cumulative) >= 10 else cumulative[-1]

    # HHI: sum of squared shares (shares as fractions)
    shares = sorted_pcts / 100
    hhi = (shares**2).sum() * 10000  # scale to 0-10000

    r1, r2, r3, r4, r5 = st.columns(5)
    r1.metric("Top 1", f"{top1:.1f}%")
    r2.metric("Top 3", f"{top3:.1f}%")
    r3.metric("Top 5", f"{top5:.1f}%")
    r4.metric("Top 10", f"{top10_pct:.1f}%")
    r5.metric("HHI", f"{hhi:.0f}")

    if hhi > 2500:
        st.warning("HHI > 2500: highly concentrated portfolio.")
    elif hhi > 1500:
        st.info("HHI 1500–2500: moderately concentrated portfolio.")
    else:
        st.success("HHI < 1500: well-diversified portfolio.")

    # -- Section 5: Full asset table -------------------------------------
    st.subheader("All Assets")
    display_df = asset_df[["symbol", "name", "total_amount", "total_jpy_value", "percentage"]].copy()
    display_df["symbol"] = display_df["symbol"].replace(DISPLAY_NAMES)
    display_df.columns = ["Symbol", "Name", "Amount", "JPY Value", "%"]
    st.dataframe(display_df, use_container_width=True, hide_index=True)

    # -- Section 6: Historical trends ------------------------------------
    st.subheader("Historical Trends")

    if len(dates) < 2:
        st.info("Only one snapshot available. Add more snapshots to see trends.")
    else:
        # Total portfolio value over time
        history_rows: list[dict] = []
        cat_rows: list[dict] = []
        for d in dates:
            try:
                a_df = load_asset_csv(d)
                e_df = load_exposure_csv(d)
            except Exception:
                continue
            label = f"{d[:4]}-{d[4:6]}-{d[6:]}"
            history_rows.append({"date": label, "total_jpy": a_df["jpy_value"].sum()})
            merged = e_df.copy()
            merged["category"] = merged["category"].replace(MERGE_CATEGORIES)
            merged = merged.groupby("category", as_index=False)["jpy_value"].sum()
            merged["category"] = merged["category"].replace(CATEGORY_DISPLAY_NAMES)
            for _, row in merged.iterrows():
                cat_rows.append(
                    {
                        "date": label,
                        "category": row["category"],
                        "jpy_value": row["jpy_value"],
                    }
                )

        hist_df = pd.DataFrame(history_rows)
        cat_df = pd.DataFrame(cat_rows)

        col_l, col_r = st.columns(2)

        with col_l:
            fig_line = px.line(
                hist_df,
                x="date",
                y="total_jpy",
                markers=True,
                title="Total Portfolio Value",
                labels={"total_jpy": "JPY", "date": ""},
            )
            fig_line.update_layout(margin=dict(t=40, b=0))
            st.plotly_chart(fig_line, use_container_width=True)

        with col_r:
            fig_area = px.area(
                cat_df,
                x="date",
                y="jpy_value",
                color="category",
                title="Category Composition",
                labels={"jpy_value": "JPY", "date": ""},
            )
            fig_area.update_layout(margin=dict(t=40, b=0))
            st.plotly_chart(fig_area, use_container_width=True)


if __name__ == "__main__":
    main()
