-- ============================================================
-- E-Commerce KPI Dashboard - Star Schema
-- PostgreSQL
-- ============================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- DIMENSION TABLES
-- ============================================================

-- Dimension Date
CREATE TABLE IF NOT EXISTS dim_date (
    date_id         DATE PRIMARY KEY,
    day_of_week     SMALLINT,          -- 1=Lundi ... 7=Dimanche
    day_name        VARCHAR(10),
    week_number     SMALLINT,
    month_number    SMALLINT,
    month_name      VARCHAR(10),
    quarter         SMALLINT,
    year            SMALLINT,
    is_weekend      BOOLEAN,
    is_holiday      BOOLEAN DEFAULT FALSE
);

-- Dimension Product
CREATE TABLE IF NOT EXISTS dim_product (
    product_id      SERIAL PRIMARY KEY,
    stock_code      VARCHAR(20) UNIQUE NOT NULL,
    description     VARCHAR(500),
    category        VARCHAR(100),
    unit_price      NUMERIC(10, 2),
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- Dimension Customer
CREATE TABLE IF NOT EXISTS dim_customer (
    customer_id     SERIAL PRIMARY KEY,
    customer_code   VARCHAR(20) UNIQUE NOT NULL,  -- CustomerID original UCI
    country         VARCHAR(100),
    city            VARCHAR(100),
    segment         VARCHAR(50),                   -- 'Champions','Loyal','At Risk', etc.
    first_order_date DATE,
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- ============================================================
-- FACT TABLE
-- ============================================================

CREATE TABLE IF NOT EXISTS fact_sales (
    sale_id         SERIAL PRIMARY KEY,
    invoice_no      VARCHAR(20) NOT NULL,
    date_id         DATE REFERENCES dim_date(date_id),
    product_id      INT REFERENCES dim_product(product_id),
    customer_id     INT REFERENCES dim_customer(customer_id),
    quantity        INT NOT NULL,
    unit_price      NUMERIC(10, 2) NOT NULL,
    total_amount    NUMERIC(12, 2) GENERATED ALWAYS AS (quantity * unit_price) STORED,
    is_cancelled    BOOLEAN DEFAULT FALSE,        -- invoice starts with 'C'
    country         VARCHAR(100),
    created_at      TIMESTAMP DEFAULT NOW()
);

-- ============================================================
-- RFM TABLE (computed via ETL)
-- ============================================================

CREATE TABLE IF NOT EXISTS rfm_scores (
    customer_id     INT REFERENCES dim_customer(customer_id),
    analysis_date   DATE,
    recency_days    INT,
    frequency       INT,
    monetary        NUMERIC(12, 2),
    r_score         SMALLINT CHECK (r_score BETWEEN 1 AND 5),
    f_score         SMALLINT CHECK (f_score BETWEEN 1 AND 5),
    m_score         SMALLINT CHECK (m_score BETWEEN 1 AND 5),
    rfm_segment     VARCHAR(50),
    PRIMARY KEY (customer_id, analysis_date)
);

-- ============================================================
-- INDEXES for performance Power BI / Tableau
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_fact_date       ON fact_sales(date_id);
CREATE INDEX IF NOT EXISTS idx_fact_product    ON fact_sales(product_id);
CREATE INDEX IF NOT EXISTS idx_fact_customer   ON fact_sales(customer_id);
CREATE INDEX IF NOT EXISTS idx_fact_invoice    ON fact_sales(invoice_no);
CREATE INDEX IF NOT EXISTS idx_fact_cancelled  ON fact_sales(is_cancelled);
CREATE INDEX IF NOT EXISTS idx_product_code    ON dim_product(stock_code);
CREATE INDEX IF NOT EXISTS idx_customer_code   ON dim_customer(customer_code);

-- ============================================================
-- POPULATE dim_date (2009-2012 covers UCI dataset + enrichissement)
-- ============================================================

INSERT INTO dim_date
SELECT
    d::DATE                                             AS date_id,
    EXTRACT(ISODOW FROM d)::SMALLINT                   AS day_of_week,
    TO_CHAR(d, 'Day')                                   AS day_name,
    EXTRACT(WEEK FROM d)::SMALLINT                     AS week_number,
    EXTRACT(MONTH FROM d)::SMALLINT                    AS month_number,
    TO_CHAR(d, 'Month')                                 AS month_name,
    EXTRACT(QUARTER FROM d)::SMALLINT                  AS quarter,
    EXTRACT(YEAR FROM d)::SMALLINT                     AS year,
    EXTRACT(ISODOW FROM d) IN (6, 7)                   AS is_weekend
FROM generate_series('2009-01-01'::DATE, '2026-12-31'::DATE, '1 day') d
ON CONFLICT DO NOTHING;
