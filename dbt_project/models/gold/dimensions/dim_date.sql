{{ config(materialized='table') }}

-- ====================================================================
-- DIMENSION : dim_date
-- ====================================================================
-- Calendrier de référence (~3 ans : 2024-01-01 → 2026-12-31)
-- Permet d'analyser les offres dans le temps : par jour, semaine,
-- mois, trimestre, année. Indispensable pour Power BI.
-- Clé primaire : date_id (format YYYYMMDD entier)
-- Clé naturelle : full_date (date)
-- ====================================================================

WITH date_series AS (
    SELECT generate_series(
        DATE '2024-01-01',
        DATE '2026-12-31',
        INTERVAL '1 day'
    )::date AS full_date
)

SELECT
    -- ID au format YYYYMMDD (entier, recommandé pour les jointures rapides)
    TO_CHAR(full_date, 'YYYYMMDD')::int        AS date_id,
    full_date,

    -- Composantes
    EXTRACT(YEAR    FROM full_date)::int       AS year,
    EXTRACT(QUARTER FROM full_date)::int       AS quarter,
    EXTRACT(MONTH   FROM full_date)::int       AS month,
    EXTRACT(WEEK    FROM full_date)::int       AS week,
    EXTRACT(DAY     FROM full_date)::int       AS day_of_month,
    EXTRACT(DOW     FROM full_date)::int       AS day_of_week,    -- 0 = dimanche
    EXTRACT(DOY     FROM full_date)::int       AS day_of_year,

    -- Libellés français (utiles pour Power BI)
    CASE EXTRACT(MONTH FROM full_date)::int
        WHEN  1 THEN 'Janvier'   WHEN  2 THEN 'Février'  WHEN  3 THEN 'Mars'
        WHEN  4 THEN 'Avril'     WHEN  5 THEN 'Mai'      WHEN  6 THEN 'Juin'
        WHEN  7 THEN 'Juillet'   WHEN  8 THEN 'Août'     WHEN  9 THEN 'Septembre'
        WHEN 10 THEN 'Octobre'   WHEN 11 THEN 'Novembre' WHEN 12 THEN 'Décembre'
    END                                        AS month_name,

    CASE EXTRACT(DOW FROM full_date)::int
        WHEN 0 THEN 'Dimanche'  WHEN 1 THEN 'Lundi'    WHEN 2 THEN 'Mardi'
        WHEN 3 THEN 'Mercredi'  WHEN 4 THEN 'Jeudi'    WHEN 5 THEN 'Vendredi'
        WHEN 6 THEN 'Samedi'
    END                                        AS day_name,

    -- Libellés courts utiles pour Power BI
    TO_CHAR(full_date, 'YYYY-MM')              AS year_month,         -- ex: 2026-04
    TO_CHAR(full_date, 'YYYY-"Q"Q')            AS year_quarter,       -- ex: 2026-Q2

    -- Flags
    CASE
        WHEN EXTRACT(DOW FROM full_date)::int IN (0, 6) THEN TRUE
        ELSE FALSE
    END                                        AS is_weekend,

    -- Période relative à aujourd'hui (utile pour les filtres "30 derniers jours")
    full_date = CURRENT_DATE                   AS is_today,
    full_date >= CURRENT_DATE - INTERVAL '7 days'  AS is_last_7_days,
    full_date >= CURRENT_DATE - INTERVAL '30 days' AS is_last_30_days,
    full_date >= CURRENT_DATE - INTERVAL '90 days' AS is_last_90_days

FROM date_series
ORDER BY full_date