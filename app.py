import duckdb
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Seller Early-Warning", layout="wide")
st.title("Seller Early-Warning")
st.caption("Seller yang volum order 90 hari terakhir jatuh berbanding 90 hari sebelumnya.")


@st.cache_data
def load_data(cutoff: str) -> pd.DataFrame:
    con = duckdb.connect("olist.db", read_only=True)
    q = f"""
    SELECT s.seller_id, s.seller_state, s.seller_city,
      COUNT(DISTINCT oi.order_id) FILTER (
        WHERE CAST(o.order_purchase_timestamp AS TIMESTAMP) >= TIMESTAMP '{cutoff}' - INTERVAL 90 DAY
          AND CAST(o.order_purchase_timestamp AS TIMESTAMP) <  TIMESTAMP '{cutoff}') AS recent_90d,
      COUNT(DISTINCT oi.order_id) FILTER (
        WHERE CAST(o.order_purchase_timestamp AS TIMESTAMP) >= TIMESTAMP '{cutoff}' - INTERVAL 180 DAY
          AND CAST(o.order_purchase_timestamp AS TIMESTAMP) <  TIMESTAMP '{cutoff}' - INTERVAL 90 DAY) AS prev_90d,
      SUM(oi.price) FILTER (
        WHERE CAST(o.order_purchase_timestamp AS TIMESTAMP) >= TIMESTAMP '{cutoff}' - INTERVAL 180 DAY
          AND CAST(o.order_purchase_timestamp AS TIMESTAMP) <  TIMESTAMP '{cutoff}' - INTERVAL 90 DAY) AS revenue_at_risk
    FROM order_items oi
    JOIN orders o USING (order_id)
    JOIN sellers s USING (seller_id)
    WHERE o.order_status NOT IN ('canceled', 'unavailable')
    GROUP BY s.seller_id, s.seller_state, s.seller_city
    """
    df = con.execute(q).df()
    con.close()
    return df


# ---- Sidebar ----
st.sidebar.header("Tetapan")
cutoff = st.sidebar.date_input(
    "Tarikh cutoff", value=pd.Timestamp("2018-08-31"),
    min_value=pd.Timestamp("2017-06-01"), max_value=pd.Timestamp("2018-08-31"))
min_orders = st.sidebar.slider("Min order dalam 90 hari sebelum", 5, 50, 20)
drop_pct = st.sidebar.slider("Flag jika jatuh sekurang-kurangnya (%)", 20, 90, 50)

df = load_data(str(cutoff))
all_states = sorted(df.seller_state.unique())
states = st.sidebar.multiselect("Negeri", all_states, default=all_states)

# ---- Logik ----
elig = df[(df.prev_90d >= min_orders) & (df.seller_state.isin(states))].copy()
elig["change_pct"] = (100 * (elig.recent_90d - elig.prev_90d) / elig.prev_90d).round(1)
flagged = elig[elig.recent_90d <= (1 - drop_pct / 100) * elig.prev_90d].copy()
flagged["seller_short"] = flagged.seller_id.str[:8]
flagged["revenue_at_risk"] = flagged.revenue_at_risk.round(0)
flagged = flagged.sort_values("revenue_at_risk", ascending=False)

# ---- KPI ----
c1, c2, c3 = st.columns(3)
c1.metric("Seller layak", len(elig))
c2.metric("Seller flagged", len(flagged))
c3.metric("Revenue at risk (BRL)", f"{flagged.revenue_at_risk.sum():,.0f}")

# ---- Senarai ----
st.subheader("Senarai keutamaan (susun ikut revenue at risk)")
cols = ["seller_short", "seller_state", "seller_city",
        "prev_90d", "recent_90d", "change_pct", "revenue_at_risk"]
st.dataframe(flagged[cols], hide_index=True)
st.download_button("Muat turun CSV", flagged.to_csv(index=False),
                   file_name="priority_list.csv", mime="text/csv")

# ---- Kadar ikut negeri ----
st.subheader("Kadar flagged ikut negeri")
rate = (elig.assign(is_flagged=elig.index.isin(flagged.index))
        .groupby("seller_state")
        .agg(layak=("seller_id", "count"), flagged=("is_flagged", "sum"))
        .reset_index())
rate["kadar_flagged_pct"] = (100 * rate.flagged / rate.layak).round(1)
rate = rate.sort_values("kadar_flagged_pct", ascending=False)
st.bar_chart(rate.set_index("seller_state")["kadar_flagged_pct"])
st.dataframe(rate, hide_index=True)
st.caption("Negeri dengan seller layak sedikit: kadar tak stabil, jangan tafsir berlebihan.")