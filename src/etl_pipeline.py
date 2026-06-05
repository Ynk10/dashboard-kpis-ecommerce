

"""Pipeline ETL complet pour le Dashboard KPI E-Commerce.
  1. Téléchargement/lecture du dataset UCI Online Retail
  2. Nettoyage et enrichissement (Faker pour dates récentes)
  3. Chargement dans PostgreSQL (star schema)
  4. Calcul et insertion des scores RFM"""


import os
import sys
import argparse
import logging
from datetime import datetime, timedelta
import random

import pandas as pd
import numpy as np
from faker import Faker
from sqlalchemy import create_engine, engine, engine, text
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
log = logging.getLogger(__name__)

# ── Config ─────────────────────────────────────────────────────────────────────
DB_URL = (
    f"postgresql+psycopg2://{os.getenv('DB_USER','postgres')}:"
    f"{os.getenv('DB_PASSWORD','2002!!')}@"
    f"{os.getenv('DB_HOST','localhost')}:"
    f"{os.getenv('DB_PORT','5432')}/"
    f"{os.getenv('DB_NAME','ecommerce_kpi')}"
)
RAW_DIR   = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
CSV_PATH  = os.path.join(RAW_DIR, "online_retail.csv")
XLSX_PATH = os.path.join(RAW_DIR, "Online Retail.xlsx")
CHUNK_SIZE = 10_000

fake = Faker("fr_FR")
random.seed(42)
np.random.seed(42)


# ══════════════════════════════════════════════════════════════════════════════
# 1. EXTRACTION
# ══════════════════════════════════════════════════════════════════════════════

def load_raw_data() -> pd.DataFrame:
    """Charge le fichier brut (xlsx ou csv)."""
    if os.path.exists(CSV_PATH):
        log.info(f"Lecture CSV : {CSV_PATH}")
        df = pd.read_csv(CSV_PATH, encoding="latin-1", low_memory=False)
    elif os.path.exists(XLSX_PATH):
        log.info(f"Lecture XLSX : {XLSX_PATH}")
        df = pd.read_excel(XLSX_PATH, engine="openpyxl")
    else:
        raise FileNotFoundError(
            "Dataset introuvable.\n"
            "  → Téléchargez 'Online Retail.xlsx' depuis "
            "https://archive.ics.uci.edu/dataset/352/online+retail\n"
            f"  → Placez-le dans : {RAW_DIR}"
        )
    log.info(f"Données brutes chargées : {len(df):,} lignes")
    return df


# ══════════════════════════════════════════════════════════════════════════════
# 2. TRANSFORMATION / NETTOYAGE
# ══════════════════════════════════════════════════════════════════════════════

CATEGORY_MAP = {
    "GLASS":      "Home & Decoration",
    "WOODEN":     "Home & Decoration",
    "METAL":      "Home & Decoration",
    "CERAMIC":    "Home & Decoration",
    "SET":        "Sets & Bundles",
    "BAG":        "Bags & Accessories",
    "BOX":        "Storage",
    "CARD":       "Stationery",
    "CANDLE":     "Home & Decoration",
    "CHRISTMAS":  "Seasonal",
    "HEART":      "Gifts",
    "VINTAGE":    "Collectibles",
}

def infer_category(description: str) -> str:
    if pd.isna(description):
        return "Uncategorized"
    desc_upper = str(description).upper()
    for keyword, category in CATEGORY_MAP.items():
        if keyword in desc_upper:
            return category
    return "Other"


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """Nettoyage complet du dataset UCI."""
    log.info("Nettoyage en cours...")

    # Renommage colonnes -> snake_case
    df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")
    rename_map = {
        "invoiceno":  "invoice_no",
        "stockcode":  "stock_code",
        "description":"description",
        "quantity":   "quantity",
        "invoicedate":"invoice_date",
        "unitprice":  "unit_price",
        "customerid": "customer_id",
        "country":    "country",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

    # Types
    df["invoice_date"] = pd.to_datetime(df["invoice_date"], errors="coerce")
    df["quantity"]     = pd.to_numeric(df["quantity"],    errors="coerce")
    df["unit_price"]   = pd.to_numeric(df["unit_price"],  errors="coerce")

    # Suppression lignes invalides
    initial = len(df)
    df = df.dropna(subset=["invoice_no", "stock_code", "invoice_date"])
    df = df[df["unit_price"] > 0]
    df = df[df["stock_code"].str.match(r"^[A-Z0-9]{3,}", na=False)]  # codes produits valides
    log.info(f"Lignes supprimées (invalides) : {initial - len(df):,}")

    # Commandes annulées
    """df["is_cancelled"] = df["invoice_no"].str.startswith("C")- Nan Pas boolean"""
    df["is_cancelled"] = df["invoice_no"].str.startswith("C").fillna(False).astype(bool)

    # Catégories produits
    df["category"] = df["description"].apply(infer_category)

    # Customer ID -> string propre
    df["customer_id"] = df["customer_id"].fillna(0).astype(int).astype(str)
    df["customer_id"] = df["customer_id"].replace("0", np.nan)

    log.info(f"Données nettoyées : {len(df):,} lignes")
    return df


def enrich_with_faker(df: pd.DataFrame, n_extra_months: int = 18) -> pd.DataFrame:
    """
    Génère des transactions récentes avec Faker pour simuler
    des données jusqu'à aujourd'hui (le dataset UCI s'arrête en 2011).
    """
    log.info(f"Enrichissement Faker : +{n_extra_months} mois de données...")

    # Récupère un échantillon représentatif (10% du dataset)
    sample = df[~df["is_cancelled"]].sample(frac=0.10, random_state=42).copy()

    end_date   = datetime.today()
    start_date = end_date - timedelta(days=30 * n_extra_months)

    # Génère des dates aléatoires dans la fenêtre récente
    date_range = (end_date - start_date).days
    sample["invoice_date"] = [
        start_date + timedelta(days=random.randint(0, date_range))
        for _ in range(len(sample))
    ]
    # Nouveaux numéros de facture
    sample["invoice_no"] = [f"SYN{random.randint(100000, 999999)}" for _ in range(len(sample))]
    # Légère variation des prix et quantités (+/- 15%)
    sample["unit_price"] = sample["unit_price"] * np.random.uniform(0.85, 1.15, len(sample))
    sample["quantity"]   = (sample["quantity"]   * np.random.uniform(0.80, 1.20, len(sample))).astype(int)
    sample["quantity"]   = sample["quantity"].clip(lower=1)

    enriched = pd.concat([df, sample], ignore_index=True)
    log.info(f"Après enrichissement : {len(enriched):,} lignes")
    return enriched


# ══════════════════════════════════════════════════════════════════════════════
# 3. CHARGEMENT DANS POSTGRESQL
# ══════════════════════════════════════════════════════════════════════════════

def load_to_postgres(df: pd.DataFrame, engine):
    """Charge les données dans le star schema PostgreSQL."""

    log.info("Chargement des dimensions et de la table de faits...")

    # DROP dans le bon ordre avec CASCADE
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS rfm_scores   CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS fact_sales   CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS dim_product  CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS dim_customer CASCADE"))
        conn.commit()
    log.info("  Anciennes tables supprimees")

    # ── dim_product ────────────────────────────────────────────────────────────
    products = (
        df[["stock_code", "description", "category", "unit_price"]]
        .dropna(subset=["stock_code"])
        .drop_duplicates(subset=["stock_code"])
        .copy()
    )
    # Prix médian par produit (plus représentatif)
    median_price = df.groupby("stock_code")["unit_price"].median().reset_index()
    median_price.columns = ["stock_code", "unit_price"]
    products = products.drop(columns=["unit_price"]).merge(median_price, on="stock_code")

    products.to_sql("dim_product", engine, if_exists="append", index=True,
                    method="multi", chunksize=CHUNK_SIZE)
    log.info(f"  ✅ dim_product : {len(products):,} produits")

    # ── dim_customer ───────────────────────────────────────────────────────────
    cust_df = df.dropna(subset=["customer_id"]).copy()
    first_orders = cust_df.groupby("customer_id")["invoice_date"].min().reset_index()
    first_orders.columns = ["customer_id", "first_order_date"]
    first_orders["first_order_date"] = first_orders["first_order_date"].dt.date

    customers = (
        cust_df[["customer_id", "country"]]
        .drop_duplicates(subset=["customer_id"])
        .merge(first_orders, on="customer_id")
        .rename(columns={"customer_id": "customer_code"})
    )
    customers["city"]    = [fake.city() for _ in range(len(customers))]
    customers["segment"] = "Unknown"  # sera mis à jour après RFM

    customers.to_sql("dim_customer", engine, if_exists="append", index=True,
                     method="multi", chunksize=CHUNK_SIZE)
    log.info(f"  ✅ dim_customer : {len(customers):,} clients")

    # ── fact_sales ─────────────────────────────────────────────────────────────
 # Récupère les IDs générés (pandas crée son propre index, on utilise index=False)
    # Récupère les mappings
    with engine.connect() as conn:
        prod_map = pd.read_sql("SELECT ROW_NUMBER() OVER () AS product_id, stock_code FROM dim_product", conn)
        cust_map = pd.read_sql("SELECT customer_code FROM dim_customer", conn)

    facts = df.copy()
    facts["date_id"] = facts["invoice_date"].dt.date

    facts = facts.merge(prod_map, on="stock_code", how="left")
    facts = facts.merge(
        cust_map,
        left_on="customer_id", right_on="customer_code", how="left"
    )

    fact_cols = [
        "invoice_no", "date_id", "product_id", "customer_code",
        "quantity", "unit_price", "is_cancelled", "country"
    ]
    facts_clean = facts[fact_cols].rename(columns={"customer_code": "customer_id"})
    facts_clean = facts_clean.dropna(subset=["product_id"])

    facts_clean.to_sql("fact_sales", engine, if_exists="append", index=False,
                       method="multi", chunksize=CHUNK_SIZE)
    log.info(f"  ✅ fact_sales  : {len(facts_clean):,} transactions")


# ══════════════════════════════════════════════════════════════════════════════
# 4. CALCUL RFM
# ══════════════════════════════════════════════════════════════════════════════

def compute_rfm(engine):
    """Calcule les scores RFM et met à jour dim_customer.segment."""
    log.info("Calcul des scores RFM...")

    rfm_query = """
        SELECT
            customer_id::text,
            CURRENT_DATE - MAX(date_id)            AS recency_days,
            COUNT(DISTINCT invoice_no)             AS frequency,
            SUM(quantity * unit_price)             AS monetary
        FROM fact_sales
        WHERE is_cancelled = FALSE
        AND customer_id IS NOT NULL
        AND customer_id != '0'
        GROUP BY customer_id
    """
    with engine.connect() as conn:
        rfm = pd.read_sql(rfm_query, conn)

    # Scores 1-5 (5 = meilleur)
    rfm["r_score"] = pd.qcut(rfm["recency_days"], 5, labels=[5,4,3,2,1]).astype(int)
    rfm["f_score"] = pd.qcut(rfm["frequency"].rank(method="first"), 5, labels=[1,2,3,4,5]).astype(int)
    rfm["m_score"] = pd.qcut(rfm["monetary"].rank(method="first"),  5, labels=[1,2,3,4,5]).astype(int)

    def segment(row):
        r, f, m = row["r_score"], row["f_score"], row["m_score"]
        if r >= 4 and f >= 4:            return "Champions"
        if r >= 3 and f >= 3:            return "Loyal Customers"
        if r >= 4 and f < 3:             return "Recent Customers"
        if r >= 3 and m >= 3:            return "Potential Loyalist"
        if r < 3 and f >= 4:             return "At Risk"
        if r < 2 and f >= 3:             return "Cant Lose Them"
        if r < 3 and f < 3 and m < 3:   return "Hibernating"
        return "Needs Attention"

    rfm["rfm_segment"] = rfm.apply(segment, axis=1)
    rfm["analysis_date"] = datetime.today().date()

    rfm.rename(columns={"customer_id": "customer_code"}, inplace=True)
    rfm.to_sql("rfm_scores", engine, if_exists="append", index=False,
               method="multi", chunksize=CHUNK_SIZE)

    # Met à jour le segment dans dim_customer
    with engine.connect() as conn:
        for _, row in rfm.iterrows():
            conn.execute(
                text("UPDATE dim_customer SET segment = :seg WHERE customer_code = :cid"),
                {"seg": row["rfm_segment"], "cid": str(row["customer_code"])}
            )
        conn.commit()

    log.info(f"  ✅ rfm_scores  : {len(rfm):,} clients segmentés")
    seg_counts = rfm["rfm_segment"].value_counts()
    for seg, count in seg_counts.items():
        log.info(f"     {seg:<22} : {count:,}")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="ETL Pipeline E-Commerce KPI")
    parser.add_argument("--no-enrich", action="store_true",
                        help="Ne pas enrichir avec Faker")
    parser.add_argument("--enrich-months", type=int, default=18,
                        help="Nombre de mois supplémentaires à générer (défaut: 18)")
    args = parser.parse_args()

    start = datetime.now()
    log.info("═" * 60)
    log.info("  ETL Pipeline E-Commerce KPI - Démarrage")
    log.info("═" * 60)

    # 1. Extraction
    df = load_raw_data()

    # 2. Nettoyage
    df = clean_data(df)

    # 3. Enrichissement
    if not args.no_enrich:
        df = enrich_with_faker(df, n_extra_months=args.enrich_months)

    # 4. Connexion DB
    engine = create_engine(DB_URL, echo=False)
    log.info(f"Connexion DB : {DB_URL.split('@')[1]}")

    # 5. Chargement
    load_to_postgres(df, engine)

    # 6. RFM
    compute_rfm(engine)

    elapsed = (datetime.now() - start).seconds
    log.info("═" * 60)
    log.info(f"  ✅ ETL terminé en {elapsed}s")
    log.info("═" * 60)


if __name__ == "__main__":
    main()
