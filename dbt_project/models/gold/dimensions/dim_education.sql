{{ config(materialized='table') }}

-- ====================================================================
-- DIMENSION : dim_education
-- ====================================================================
-- Normalise les niveaux d'études en 6 catégories ordonnées.
-- Clé primaire : education_id (ordre logique : Bac+2 → Doctorat)
-- Clé naturelle : education_normalized
-- ====================================================================

WITH raw_education AS (
    SELECT DISTINCT
        education AS education_raw
    FROM {{ ref('jobs_unified') }}
    WHERE education IS NOT NULL AND TRIM(education) <> ''
),

normalized AS (
    SELECT
        education_raw,
        CASE
            WHEN education_raw ILIKE '%doctorat%'
              OR education_raw ILIKE '%phd%'
              OR education_raw ILIKE '%doctorate%'            THEN 'Doctorat'

            WHEN education_raw ILIKE '%bac%+%5%'
              OR education_raw ILIKE '%bac+5%'
              OR education_raw ILIKE '%master%'
              OR education_raw ILIKE '%ing[ée]nieur%'
              OR education_raw ILIKE '%MSc%'
              OR education_raw ILIKE '%engineering degree%'   THEN 'Bac+5 / Master / Ingénieur'

            WHEN education_raw ILIKE '%bac%+%4%'
              OR education_raw ILIKE '%bac+4%'                THEN 'Bac+4'

            WHEN education_raw ILIKE '%bac%+%3%'
              OR education_raw ILIKE '%bac+3%'
              OR education_raw ILIKE '%licence%'
              OR education_raw ILIKE '%bachelor%'
              OR education_raw ILIKE '%BSc%'                  THEN 'Bac+3 / Licence'

            WHEN education_raw ILIKE '%bac%+%2%'
              OR education_raw ILIKE '%bac+2%'
              OR education_raw ILIKE '%BTS%'
              OR education_raw ILIKE '%DUT%'
              OR education_raw ILIKE '%associate%'            THEN 'Bac+2 / BTS / DUT'

            ELSE 'Autre / Non spécifié'
        END AS education_normalized,
        -- Niveau hiérarchique (utile pour trier dans Power BI)
        CASE
            WHEN education_raw ILIKE '%doctorat%'
              OR education_raw ILIKE '%phd%'                  THEN 6
            WHEN education_raw ILIKE '%bac%+%5%'
              OR education_raw ILIKE '%bac+5%'
              OR education_raw ILIKE '%master%'
              OR education_raw ILIKE '%ing[ée]nieur%'         THEN 5
            WHEN education_raw ILIKE '%bac%+%4%'              THEN 4
            WHEN education_raw ILIKE '%bac%+%3%'
              OR education_raw ILIKE '%licence%'
              OR education_raw ILIKE '%bachelor%'             THEN 3
            WHEN education_raw ILIKE '%bac%+%2%'
              OR education_raw ILIKE '%BTS%'
              OR education_raw ILIKE '%DUT%'                  THEN 2
            ELSE 0
        END AS education_level_order
    FROM raw_education
)

SELECT
    DENSE_RANK() OVER (ORDER BY MIN(education_level_order), education_normalized) AS education_id,
    education_normalized,
    MIN(education_level_order) AS education_level_order,
    -- Catégorie haute / basse pour grouper
    CASE
        WHEN MIN(education_level_order) >= 5 THEN 'Études supérieures longues'
        WHEN MIN(education_level_order) >= 3 THEN 'Études supérieures courtes'
        WHEN MIN(education_level_order) >= 2 THEN 'Bac+2'
        ELSE 'Non spécifié'
    END AS education_category,
    STRING_AGG(DISTINCT education_raw, ' | ' ORDER BY education_raw) AS raw_variants,
    COUNT(DISTINCT education_raw) AS nb_raw_variants
FROM normalized
GROUP BY education_normalized
ORDER BY MIN(education_level_order)