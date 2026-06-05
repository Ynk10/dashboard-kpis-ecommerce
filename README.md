# 📊 Dashboard KPIs E-Commerce

> Pipeline ETL + PostgreSQL + Power BI / Tableau Public pour suivre les performances d'une startup e-commerce en temps réel.

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-336791?logo=postgresql&logoColor=white)
![Power BI](https://img.shields.io/badge/Power%20BI-Desktop-F2C811?logo=powerbi&logoColor=black)
![License](https://img.shields.io/badge/License-MIT-green)

---

## 🧩 Problématique Business

| | Avant | Après |
|---|---|---|
| **Outil** | Excel manuel | Dashboard interactif |
| **Volume** | Limité | 500k+ transactions |
| **Délai** | J+2 | Quasi temps réel |
| **Audience** | Analyste seul | CEO + Marketing |

---

## 📁 Structure du Projet

```
06-dashboard-kpis-ecommerce/
├── src/
│   ├── db_setup.py        # Création du schéma PostgreSQL
│   └── etl_pipeline.py    # ETL : nettoyage + chargement + RFM
├── sql/
│   ├── schema.sql         # Star schema (dim + fact)
│   └── queries.sql        # Vues analytiques (KPIs, cohortes, RFM)
├── dashboards/
│   ├── ecommerce.pbix     # Power BI Desktop
│   └── screenshots/       # Aperçus du dashboard
├── data/
│   └── raw/               # CSV/XLSX brut (non versionné)
├── .env.example           # Template variables d'environnement
├── requirements.txt
└── README.md
```

---

## 🛠️ Stack Technique

| Composant | Outil | Gratuit ? |
|-----------|-------|-----------|
| ETL       | Python (pandas, SQLAlchemy, Faker) | ✅ |
| Base de données | PostgreSQL 15+ | ✅ |
| BI (option 1) | Power BI Desktop | ✅ (Desktop) |
| BI (option 2) | Tableau Public | ✅ |
| IDE       | VS Code | ✅ |

---

## 🚀 Installation Pas à Pas

### 1. Prérequis

- Python 3.10+
- PostgreSQL 15+ (installé et démarré)
- VS Code avec l'extension Python

### 2. Cloner le projet

```bash
git clone https://github.com/tey_10/dashboard-kpis-ecommerce.git
cd dashboard-kpis-ecommerce
```

### 3. Environnement virtuel Python

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# Mac / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 4. Variables d'environnement

```bash
cp .env.example .env
# Ouvrir .env et renseigner vos identifiants PostgreSQL
```

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=ecommerce_kpi
DB_USER=postgres
DB_PASSWORD=votre_mot_de_passe
```

### 5. Télécharger le dataset UCI

1. Aller sur : https://archive.ics.uci.edu/dataset/352/online+retail
2. Télécharger **Online Retail.xlsx**
3. Placer le fichier dans `data/raw/`

### 6. Créer la base de données

```bash
python src/db_setup.py
```

Résultat attendu :
```
✅ Base de données 'ecommerce_kpi' créée.
✅ Schéma créé (tables + index + dim_date peuplée).
📋 Tables : dim_customer, dim_date, dim_product, fact_sales, rfm_scores
```

### 7. Lancer le pipeline ETL

```bash
# Avec enrichissement Faker (18 mois de données récentes) - recommandé
python src/etl_pipeline.py

# Sans enrichissement
python src/etl_pipeline.py --no-enrich

# Enrichissement personnalisé (ex: 24 mois)
python src/etl_pipeline.py --enrich-months 24
```

Durée estimée : **2-5 minutes** selon votre machine.

### 8. Vérifier les données

Ouvrir **pgAdmin** ou **DBeaver** et exécuter :

```sql
SELECT * FROM v_kpis_summary;
SELECT * FROM v_ca_monthly LIMIT 24;
SELECT * FROM v_rfm_current LIMIT 10;
```

---

## 📊 Modèle de Données (Star Schema)

```
                    ┌─────────────┐
                    │  dim_date   │
                    │─────────────│
                    │ date_id PK  │
                    │ year        │
                    │ month       │
                    │ quarter     │
                    │ is_weekend  │
                    └──────┬──────┘
                           │
┌──────────────┐    ┌──────┴──────┐    ┌───────────────┐
│ dim_product  │    │ fact_sales  │    │ dim_customer  │
│──────────────│    │─────────────│    │───────────────│
│ product_id PK│◄───│ product_id  │───►│ customer_id PK│
│ stock_code   │    │ customer_id │    │ customer_code │
│ description  │    │ date_id     │    │ country       │
│ category     │    │ invoice_no  │    │ segment (RFM) │
│ unit_price   │    │ quantity    │    │ first_order.. │
└──────────────┘    │ unit_price  │    └───────────────┘
                    │ total_amount│
                    │ is_cancelled│
                    └─────────────┘
```

---

## 🎯 KPIs Implémentés

### Ventes
| KPI | Vue SQL | Description |
|-----|---------|-------------|
| CA jour/mois/année | `v_ca_daily`, `v_ca_monthly` | Chiffre d'affaires agrégé |
| Évolution vs N-1 | `v_ca_monthly` | `pct_vs_n1` calculé avec `LAG()` |
| Top 10 produits | `v_top_products` | Classés par revenue |
| Panier moyen | `v_ca_daily` | `avg_basket` |

### Clients
| KPI | Vue SQL | Description |
|-----|---------|-------------|
| Nouveaux vs récurrents | `v_customer_type_monthly` | Par mois |
| Segmentation RFM | `v_rfm_current` | 8 segments |
| Scores RFM | `rfm_scores` | R, F, M de 1 à 5 |

### Cohortes
| KPI | Vue SQL | Description |
|-----|---------|-------------|
| Rétention mensuelle | `v_cohort_retention` | % par cohorte |
| LTV par cohorte | `v_ltv_cohort` | Revenue moyen par client |

---

## 🔌 Connexion Power BI

1. Ouvrir Power BI Desktop
2. **Obtenir les données** → PostgreSQL
3. Serveur : `localhost:5432`, Base : `ecommerce_kpi`
4. Importer les vues : `v_ca_monthly`, `v_top_products`, `v_rfm_current`, `v_cohort_retention`, `v_kpis_summary`
5. Créer les relations sur `date_id`, `product_id`, `customer_id`

### Mesures DAX utiles

```dax
// CA Total
CA Total = SUM(fact_sales[quantity*unit_price])

// CA Mois Précédent
CA Mois Précédent = CALCULATE([CA Total], PREVIOUSMONTH(dim_date[date_id]))

// Évolution MoM
Evolution MoM % = DIVIDE([CA Total] - [CA Mois Précédent], [CA Mois Précédent])

// Taux de rétention
Taux Rétention = DIVIDE(
    CALCULATE(COUNTROWS(fact_sales), fact_sales[is_cancelled] = FALSE),
    CALCULATE(COUNTROWS(fact_sales))
)
```

---

## 🌐 Alternative Tableau Public (100% gratuit)

1. Télécharger [Tableau Public](https://public.tableau.com/app/discover)
2. Se connecter à PostgreSQL (même config)
3. Utiliser les vues SQL directement comme sources de données
4. Publier sur Tableau Public → lien partageable pour le portfolio

---

## 📸 Screenshots

> *(À ajouter après création du dashboard Power BI / Tableau)*

```
dashboards/screenshots/
├── overview_kpis.png
├── rfm_segmentation.png
└── cohort_retention.png
```

---

## 🗺️ Roadmap

- [x] Dataset UCI chargé et nettoyé
- [x] Star schema PostgreSQL
- [x] ETL Python complet
- [x] Calcul RFM automatique
- [x] Vues analytiques (KPIs, cohortes, LTV)
- [ ] Dashboard Power BI finalisé
- [ ] Actualisation automatique (Windows Task Scheduler)
- [ ] Export Tableau Public

---

## 📚 Ressources

- [Online Retail UCI Dataset](https://archive.ics.uci.edu/dataset/352/online+retail)
- [Power BI Documentation](https://learn.microsoft.com/power-bi/)
- [DAX Patterns](https://www.daxpatterns.com/)
- [Tableau Public](https://public.tableau.com/)

---

## 👤 Auteur

**Yannick TCHALLA** — Data Analyst  
[LinkedIn]([(https://www.linkedin.com/in/yannick-tchalla-a2b224227/)) · [Portfolio GitHub]([(https://github.com/Ynk10/))

---

*Projet réalisé dans le cadre d'un portfolio Data Analyst — Stack 100% open source/gratuit*
