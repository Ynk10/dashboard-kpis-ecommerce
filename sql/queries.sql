-- ============================================================
-- E-Commerce KPI Dashboard - Requ?tes Analytiques
-- PostgreSQL
-- ============================================================

-- ============================================================
-- 1. CHIFFRE D'AFFAIRES
-- ============================================================

-- CA par jour (30 derniers jours)
CREATE OR REPLACE VIEW v_ca_daily AS
SELECT
    fs.date_id,
    dd.month_name,
    dd.year,
    SUM(fs.quantity * fs.unit_price)                          AS ca_day,
    COUNT(DISTINCT fs.invoice_no)                 AS nb_orders,
    COUNT(DISTINCT fs.customer_id)                AS nb_customers,
    ROUND((SUM(fs.quantity * fs.unit_price) /
          NULLIF(COUNT(DISTINCT fs.invoice_no), 0))::NUMERIC, 2) AS avg_basket
FROM fact_sales fs
JOIN dim_date dd ON fs.date_id = dd.date_id
WHERE fs.is_cancelled = FALSE
GROUP BY fs.date_id, dd.month_name, dd.year
ORDER BY fs.date_id DESC;

-- CA mensuel avec ?volution N-1
CREATE OR REPLACE VIEW v_ca_monthly AS
SELECT
    year,
    month_number,
    month_name,
    ca_month,
    LAG(ca_month) OVER (PARTITION BY month_number ORDER BY year) AS ca_same_month_n1,
    ROUND((
        (ca_month - LAG(ca_month) OVER (PARTITION BY month_number ORDER BY year))
        / NULLIF(LAG(ca_month) OVER (PARTITION BY month_number ORDER BY year), 0) * 100
    )::NUMERIC, 2) AS pct_vs_n1
FROM (
    SELECT
        dd.year,
        dd.month_number,
        dd.month_name,
        SUM(fs.quantity * fs.unit_price) AS ca_month
    FROM fact_sales fs
    JOIN dim_date dd ON fs.date_id = dd.date_id
    WHERE fs.is_cancelled = FALSE
    GROUP BY dd.year, dd.month_number, dd.month_name
) monthly
ORDER BY year, month_number;

-- ============================================================
-- 2. TOP PRODUITS
-- ============================================================

CREATE OR REPLACE VIEW v_top_products AS
SELECT
    dp.stock_code,
    dp.description,
    dp.category,
    SUM(fs.quantity * fs.unit_price)                AS revenue,
    SUM(fs.quantity)                    AS units_sold,
    COUNT(DISTINCT fs.invoice_no)       AS nb_orders,
    RANK() OVER (ORDER BY SUM(fs.quantity * fs.unit_price) DESC) AS revenue_rank
FROM fact_sales fs
JOIN dim_product dp ON fs.product_id = dp.index
WHERE fs.is_cancelled = FALSE
  AND fs.quantity > 0
GROUP BY dp.stock_code, dp.description, dp.category
ORDER BY revenue DESC;

-- ============================================================
-- 3. ANALYSE CLIENTS - Nouveaux vs R?currents
-- ============================================================

CREATE OR REPLACE VIEW v_customer_type_monthly AS
SELECT
    dd.year,
    dd.month_number,
    dd.month_name,
    SUM(CASE WHEN first_orders.date_id = fs.date_id THEN 1 ELSE 0 END) AS new_customers,
    COUNT(DISTINCT fs.customer_id) - 
        SUM(CASE WHEN first_orders.date_id = fs.date_id THEN 1 ELSE 0 END) AS returning_customers,
    COUNT(DISTINCT fs.customer_id)    AS total_customers
FROM fact_sales fs
JOIN dim_date dd ON fs.date_id = dd.date_id
JOIN (
    SELECT customer_id, MIN(date_id) AS date_id
    FROM fact_sales
    WHERE is_cancelled = FALSE
    GROUP BY customer_id
) first_orders ON fs.customer_id = first_orders.customer_id
WHERE fs.is_cancelled = FALSE
GROUP BY dd.year, dd.month_number, dd.month_name
ORDER BY dd.year, dd.month_number;

-- ============================================================
-- 4. RFM SEGMENTATION
-- ============================================================

-- Calcul RFM complet (? ex?cuter p?riodiquement via ETL)
CREATE OR REPLACE VIEW v_rfm_current AS
WITH rfm_raw AS (
    SELECT
        customer_id,
        MAX(date_id)                          AS last_order_date,
        CURRENT_DATE - MAX(date_id)           AS recency_days,
        COUNT(DISTINCT invoice_no)            AS frequency,
        SUM(quantity * unit_price)                     AS monetary
    FROM fact_sales
    WHERE is_cancelled = FALSE
      AND customer_id IS NOT NULL
    GROUP BY customer_id
),
rfm_scores AS (
    SELECT *,
        NTILE(5) OVER (ORDER BY recency_days ASC)  AS r_score,   -- moins r?cent = score faible
        NTILE(5) OVER (ORDER BY frequency DESC)    AS f_score,
        NTILE(5) OVER (ORDER BY monetary DESC)     AS m_score
    FROM rfm_raw
)
SELECT
    dc.customer_code,
    dc.country,
    rs.*,
    CASE
        WHEN rs.r_score >= 4 AND rs.f_score >= 4                  THEN 'Champions'
        WHEN rs.r_score >= 3 AND rs.f_score >= 3                  THEN 'Loyal Customers'
        WHEN rs.r_score >= 4 AND rs.f_score < 3                   THEN 'Recent Customers'
        WHEN rs.r_score >= 3 AND rs.f_score >= 1 AND rs.m_score >= 3 THEN 'Potential Loyalist'
        WHEN rs.r_score < 3 AND rs.f_score >= 4                   THEN 'At Risk'
        WHEN rs.r_score < 2 AND rs.f_score >= 3                   THEN 'Cant Lose Them'
        WHEN rs.r_score < 3 AND rs.f_score < 3 AND rs.m_score < 3 THEN 'Hibernating'
        ELSE 'Needs Attention'
    END AS rfm_segment
FROM rfm_scores rs
JOIN dim_customer dc ON rs.customer_id::text = dc.customer_code;

-- ============================================================
-- 5. COHORTES - R?tention mensuelle
-- ============================================================

CREATE OR REPLACE VIEW v_cohort_retention AS
WITH cohort_base AS (
    SELECT
        customer_id,
        DATE_TRUNC('month', MIN(date_id))::DATE AS cohort_month
    FROM fact_sales
    WHERE is_cancelled = FALSE
    GROUP BY customer_id
),
cohort_activity AS (
    SELECT
        cb.cohort_month,
        DATE_TRUNC('month', fs.date_id)::DATE AS activity_month,
        COUNT(DISTINCT fs.customer_id) AS active_customers
    FROM fact_sales fs
    JOIN cohort_base cb ON fs.customer_id = cb.customer_id
    WHERE fs.is_cancelled = FALSE
    GROUP BY cb.cohort_month, DATE_TRUNC('month', fs.date_id)::DATE
),
cohort_size AS (
    SELECT cohort_month, active_customers AS cohort_size
    FROM cohort_activity
    WHERE cohort_month = activity_month
)
SELECT
    ca.cohort_month,
    ca.activity_month,
    EXTRACT(YEAR FROM AGE(ca.activity_month, ca.cohort_month)) * 12 +
        EXTRACT(MONTH FROM AGE(ca.activity_month, ca.cohort_month)) AS month_number,
    ca.active_customers,
    cs.cohort_size,
    ROUND((ca.active_customers::NUMERIC / cs.cohort_size * 100), 1) AS retention_rate
FROM cohort_activity ca
JOIN cohort_size cs ON ca.cohort_month = cs.cohort_month
ORDER BY ca.cohort_month, ca.activity_month;

-- ============================================================
-- 6. LTV PAR COHORTE
-- ============================================================

CREATE OR REPLACE VIEW v_ltv_cohort AS
SELECT
    cb.cohort_month,
    COUNT(DISTINCT fs.customer_id)              AS nb_customers,
    SUM(fs.quantity * fs.unit_price)                        AS total_revenue,
    ROUND((SUM(fs.quantity * fs.unit_price) /
          COUNT(DISTINCT fs.customer_id))::NUMERIC, 2)    AS avg_ltv,
    ROUND((AVG(fs.quantity * fs.unit_price))::NUMERIC, 2)              AS avg_order_value,
    COUNT(DISTINCT fs.invoice_no) /
        NULLIF(COUNT(DISTINCT fs.customer_id), 0) AS avg_orders_per_customer
FROM fact_sales fs
JOIN (
    SELECT customer_id, DATE_TRUNC('month', MIN(date_id))::DATE AS cohort_month
    FROM fact_sales WHERE is_cancelled = FALSE GROUP BY customer_id
) cb ON fs.customer_id = cb.customer_id
WHERE fs.is_cancelled = FALSE
GROUP BY cb.cohort_month
ORDER BY cb.cohort_month;

-- ============================================================
-- 7. KPIs GLOBAUX - Vue r?sum? pour Power BI
-- ============================================================

CREATE OR REPLACE VIEW v_kpis_summary AS
SELECT
    -- CA Total
    SUM(quantity * unit_price)                                           AS total_revenue,
    -- CA mois courant
    SUM(CASE WHEN date_id >= DATE_TRUNC('month', CURRENT_DATE) THEN quantity * unit_price END) AS revenue_current_month,
    -- Commandes totales
    COUNT(DISTINCT invoice_no)                                  AS total_orders,
    -- Clients uniques
    COUNT(DISTINCT customer_id)                                 AS total_customers,
    -- Panier moyen
    ROUND((SUM(quantity * unit_price) / NULLIF(COUNT(DISTINCT invoice_no), 0))::NUMERIC, 2) AS avg_basket,
    -- Produits vendus
    COUNT(DISTINCT product_id)                                  AS distinct_products,
    -- CA moyen par client
    ROUND((SUM(quantity * unit_price) / NULLIF(COUNT(DISTINCT customer_id), 0))::NUMERIC, 2) AS avg_revenue_per_customer
FROM fact_sales
WHERE is_cancelled = FALSE;
