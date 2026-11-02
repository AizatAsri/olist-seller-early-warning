from itertools import count

import duckdb
from pathlib import Path

con = duckdb.connect("olist.db")

tables = {
    "orders": "olist_orders_dataset.csv",
    "order_items": "olist_order_items_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "products": "olist_products_dataset.csv",
    "customers": "olist_customers_dataset.csv",
    "payments": "olist_order_payments_dataset.csv",
    "reviews": "olist_order_reviews_dataset.csv",
    "category_translation": "product_category_name_translation.csv"
}

for name, file in tables.items():
    matches = list(Path("data").rglob(file))
    if not matches:
        print("TIADA fail:", file)
        continue
    path = matches[0].as_posix()
    con.execute(f"""
        CREATE OR REPLACE TABLE {name} AS
        SELECT * FROM read_csv_auto('{path}')
    """)
    count = con.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
    print(name, count)
