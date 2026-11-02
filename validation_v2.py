import math
import duckdb
import pandas as pd

con = duckdb.connect("olist.db")
pd.set_option("display.width", 200)
pd.set_option("display.max_columns", None)


def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    denom = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return (100 * (centre - half), 100 * (centre + half))


def load(cutoff):
    q = f"""
    WITH so AS (
      SELECT DISTINCT oi.seller_id, o.order_id,
             CAST(o.order_purchase_timestamp AS TIMESTAMP) AS ts
      FROM order_items oi JOIN orders o USING (order_id)
      WHERE o.order_status NOT IN ('canceled','unavailable')
    )
    SELECT seller_id,
      COUNT(*) FILTER (WHERE ts >= TIMESTAMP '{cutoff}' - INTERVAL 90 DAY
                         AND ts <  TIMESTAMP '{cutoff}') AS recent_90d,
      COUNT(*) FILTER (WHERE ts >= TIMESTAMP '{cutoff}' - INTERVAL 180 DAY
                         AND ts <  TIMESTAMP '{cutoff}' - INTERVAL 90 DAY) AS prev_90d,
      COUNT(*) FILTER (WHERE ts >= TIMESTAMP '{cutoff}'
                         AND ts <  TIMESTAMP '{cutoff}' + INTERVAL 90 DAY) AS next_90d
    FROM so GROUP BY seller_id
    """
    df = con.execute(q).df()
    df = df[df.prev_90d >= 20].copy()
    df["flagged"] = df.recent_90d <= 0.5 * df.prev_90d
    df["still_low"] = df.next_90d <= 0.5 * df.prev_90d
    df["zero_orders"] = df.next_90d == 0
    return df


rows = []
for cutoff in ["2018-03-31", "2018-04-30", "2018-05-31"]:
    df = load(cutoff)
    for flagged, g in df.groupby("flagged"):
        n = len(g)
        for metric in ["still_low", "zero_orders"]:
            k = int(g[metric].sum())
            lo, hi = wilson(k, n)
            rows.append({
                "cutoff": cutoff, "flagged": flagged, "metric": metric,
                "n": n, "k": k,
                "pct": round(100 * k / n, 1),
                "ci95": f"{lo:.0f}-{hi:.0f}",
            })

out = pd.DataFrame(rows)
print(out.to_string(index=False))
out.to_csv("validation_results.csv", index=False)