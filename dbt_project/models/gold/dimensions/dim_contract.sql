{{ config(materialized='table') }}

-- ====================================================================
-- DIMENSION : dim_contract
-- ====================================================================
-- Normalise les types de contrat hétérogènes :
--   "CDI - Télétravail Hybride" → CDI
--   "Temps plein" / "Full-time" → CDI (synonymes pour LinkedIn)
--   "Stage" / "Internship" → Stage
-- Clé primaire : contract_id
-- Clé naturelle : contract_normalized
-- ====================================================================

WITH raw_contracts AS (
    SELECT DISTINCT
        TRIM(SPLIT_PART(contract_type, '-', 1)) AS contract_main
    FROM {{ ref('jobs_unified') }}
    WHERE contract_type IS NOT NULL AND TRIM(contract_type) <> ''
),

normalized AS (
    SELECT
        contract_main,
        CASE
            WHEN contract_main ILIKE '%CDI%'                  THEN 'CDI'
            WHEN contract_main ILIKE '%CDD%'                  THEN 'CDD'
            WHEN contract_main ILIKE '%stage%'
              OR contract_main ILIKE '%intern%'               THEN 'Stage'
            WHEN contract_main ILIKE '%PFE%'                  THEN 'PFE'
            WHEN contract_main ILIKE '%alternance%'
              OR contract_main ILIKE '%apprentice%'           THEN 'Alternance'
            WHEN contract_main ILIKE '%freelance%'
              OR contract_main ILIKE '%contract%'             THEN 'Freelance'
            WHEN contract_main ILIKE '%temps plein%'
              OR contract_main ILIKE '%full%time%'            THEN 'Temps plein'
            WHEN contract_main ILIKE '%temps partiel%'
              OR contract_main ILIKE '%part%time%'            THEN 'Temps partiel'
            ELSE 'Autre'
        END AS contract_normalized,
        -- Catégorie de durée (utile pour Power BI)
        CASE
            WHEN contract_main ILIKE '%CDI%'
              OR contract_main ILIKE '%temps plein%'
              OR contract_main ILIKE '%full%time%'            THEN 'Long terme'
            WHEN contract_main ILIKE '%CDD%'                  THEN 'Moyen terme'
            WHEN contract_main ILIKE '%stage%'
              OR contract_main ILIKE '%intern%'
              OR contract_main ILIKE '%PFE%'
              OR contract_main ILIKE '%alternance%'
              OR contract_main ILIKE '%apprentice%'           THEN 'Formation'
            WHEN contract_main ILIKE '%freelance%'
              OR contract_main ILIKE '%contract%'
              OR contract_main ILIKE '%temps partiel%'
              OR contract_main ILIKE '%part%time%'            THEN 'Flexible'
            ELSE 'Autre'
        END AS contract_category
    FROM raw_contracts
)

SELECT
    ROW_NUMBER() OVER (ORDER BY contract_normalized) AS contract_id,
    contract_normalized,
    contract_category,
    -- Liste des libellés bruts regroupés (debugging)
    STRING_AGG(DISTINCT contract_main, ' | ' ORDER BY contract_main) AS raw_variants,
    COUNT(DISTINCT contract_main) AS nb_raw_variants
FROM normalized
GROUP BY contract_normalized, contract_category
ORDER BY contract_normalized