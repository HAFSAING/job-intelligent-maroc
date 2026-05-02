{{ config(materialized='table') }}

-- ====================================================================
-- DIMENSION : dim_company
-- ====================================================================
-- Liste les entreprises uniques avec quelques métadonnées calculées
-- (nb total d'offres, sources où elle apparaît, etc.)
-- Clé primaire : company_id
-- Clé naturelle : company (utilisée pour la jointure)
--
-- Note : on ne fait PAS de fuzzy matching (Capgemini vs Capgemini Engineering
-- vs Capgemini Maroc) car ce sont parfois de vraies entités différentes.
-- ====================================================================

WITH companies AS (
    SELECT
        company,
        COUNT(*)                                              AS nb_offers,
        COUNT(DISTINCT source)                                AS nb_sources,
        COUNT(DISTINCT city)                                  AS nb_cities,
        STRING_AGG(DISTINCT source, ', ' ORDER BY source)     AS sources_list,
        MIN(scraped_at)                                       AS first_seen,
        MAX(scraped_at)                                       AS last_seen
    FROM {{ ref('jobs_unified') }}
    WHERE company IS NOT NULL AND TRIM(company) <> ''
    GROUP BY company
)

SELECT
    ROW_NUMBER() OVER (ORDER BY nb_offers DESC, company) AS company_id,
    company,
    nb_offers,
    nb_sources,
    nb_cities,
    sources_list,
    first_seen,
    last_seen,
    -- Catégorie (utile pour filtrer dans Power BI)
    CASE
        WHEN nb_offers >= 10 THEN 'Grand recruteur (10+)'
        WHEN nb_offers >= 5  THEN 'Recruteur actif (5-9)'
        WHEN nb_offers >= 2  THEN 'Recruteur régulier (2-4)'
        ELSE 'Recruteur ponctuel (1)'
    END AS recruiter_category
FROM companies
ORDER BY nb_offers DESC