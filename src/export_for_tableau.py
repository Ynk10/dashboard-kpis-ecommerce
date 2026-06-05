"""
Exportation des vues PostgreSQL en CSV pour Tableau Public.
Usage : python src/export_for_tableau.py
"""

import os
import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv()

DB_URL = (
    f"postgresql+psycopg2://{os.getenv('DB_USER','postgres')}:"
    f"{os.getenv('DB_PASSWORD','')}@"
    f"{os.getenv('DB_HOST','localhost')}:"
    f"{os.getenv('DB_PORT','5432')}/"
    f"{os.getenv('DB_NAME','ecommerce_kpi')}"
)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "tableau")
os.makedirs(OUTPUT_DIR, exist_ok=True)

VIEWS = {
    "kpis_summary":       "SELECT * FROM v_kpis_summary",
    "ca_monthly":         "SELECT * FROM v_ca_monthly",
    "ca_daily":           "SELECT * FROM v_ca_daily LIMIT 365",
    "top_products":       "SELECT * FROM v_top_products LIMIT 50",
    "rfm_current":        "SELECT * FROM v_rfm_current",
    "cohort_retention":   "SELECT * FROM v_cohort_retention",
    "ltv_cohort":         "SELECT * FROM v_ltv_cohort",
    "customer_type":      "SELECT * FROM v_customer_type_monthly",
}

def export_all():
    engine = create_engine(DB_URL)
    print("📤 Export CSV pour Tableau Public...\n")
    for name, query in VIEWS.items():
        df = pd.read_sql(query, engine)
        path = os.path.join(OUTPUT_DIR, f"{name}.csv")
        df.to_csv(path, index=False, encoding="utf-8-sig")
        print(f"  ✅ {name}.csv — {len(df):,} lignes")
    print(f"\n📁 Fichiers dans : {OUTPUT_DIR}")
    print("Ouvrez Tableau Public et connectez-vous à ces CSV.")

if __name__ == "__main__":
    export_all()
