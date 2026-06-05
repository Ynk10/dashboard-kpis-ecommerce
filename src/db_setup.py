"""
db_setup.py
Création du schéma PostgreSQL pour le Dashboard KPI E-Commerce.
Usage : python db_setup.py
"""

import os
import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv

load_dotenv()

# ── Connexion ──────────────────────────────────────────────────────────────────
DB_CONFIG = {
    "host":     os.getenv("DB_HOST",     "localhost"),
    "port":     os.getenv("DB_PORT",     "5432"),
    "dbname":   os.getenv("DB_NAME",     "ecommerce_kpi"),
    "user":     os.getenv("DB_USER",     "postgres"),
    "password": os.getenv("DB_PASSWORD", "password"),
}

SCHEMA_FILE = os.path.join(os.path.dirname(__file__), "..", "sql", "schema.sql")


def create_database_if_not_exists():
    """Crée la base de données si elle n'existe pas encore."""
    conn = psycopg2.connect(**{**DB_CONFIG, "dbname": "postgres"})
    conn.autocommit = True
    cur = conn.cursor()
    db_name = DB_CONFIG["dbname"]
    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
    if not cur.fetchone():
        cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db_name)))
        print(f"✅ Base de données '{db_name}' créée.")
    else:
        print(f"ℹ️  Base de données '{db_name}' déjà existante.")
    cur.close()
    conn.close()


def run_schema():
    """Exécute le fichier schema.sql sur la base cible."""
    # encoding='utf-8-sig' gère le BOM Windows ; fallback latin-1 si besoin
    try:
        with open(SCHEMA_FILE, "r", encoding="utf-8-sig") as f:
            schema_sql = f.read()
    except UnicodeDecodeError:
        with open(SCHEMA_FILE, "r", encoding="latin-1") as f:
            schema_sql = f.read()

    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True
    cur = conn.cursor()
    try:
        cur.execute(schema_sql)
        print("✅ Schéma créé (tables + index + dim_date peuplée).")
    except Exception as e:
        print(f"❌ Erreur lors de la création du schéma : {e}")
        raise
    finally:
        cur.close()
        conn.close()


def verify_tables():
    """Affiche les tables créées pour vérification."""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        ORDER BY table_name;
    """)
    tables = [row[0] for row in cur.fetchall()]
    print(f"\n📋 Tables présentes dans '{DB_CONFIG['dbname']}' :")
    for t in tables:
        print(f"   • {t}")
    cur.close()
    conn.close()


if __name__ == "__main__":
    print("🚀 Initialisation de la base PostgreSQL...")
    create_database_if_not_exists()
    run_schema()
    verify_tables()
    print("\n✅ Setup terminé. Nous pouvons lancer la phase ETL")
