{{ config(materialized='table') }}

-- ====================================================================
-- DIMENSION : dim_experience
-- ====================================================================
-- Normalise les niveaux d'expérience hétérogènes en 5 catégories
-- ordonnées (Junior < Intermédiaire < Confirmé < Senior < Expert).
-- Clé primaire : experience_id
-- Clé naturelle : experience_normalized
-- ====================================================================

WITH raw_experience AS (
    SELECT DISTINCT
        experience AS experience_raw
    FROM {{ ref('jobs_unified') }}
    WHERE experience IS NOT NULL AND TRIM(experience) <> ''
),

normalized AS (
    SELECT
        experience_raw,
        CASE
            -- Catégories explicites par mots-clés
            WHEN experience_raw ILIKE '%débutant%'
              OR experience_raw ILIKE '%junior%'
              OR experience_raw ILIKE '%entry%'
              OR experience_raw ILIKE '%stagiaire%'
              OR experience_raw ILIKE '%internship%'          THEN 'Junior / Débutant'

            WHEN experience_raw ILIKE '%mid%'
              OR experience_raw ILIKE '%associate%'
              OR experience_raw ILIKE '%intermediate%'        THEN 'Intermédiaire'

            WHEN experience_raw ILIKE '%senior%'
              OR experience_raw ILIKE '%confirm%'             THEN 'Senior / Confirmé'

            WHEN experience_raw ILIKE '%lead%'
              OR experience_raw ILIKE '%director%'
              OR experience_raw ILIKE '%executive%'
              OR experience_raw ILIKE '%expert%'              THEN 'Lead / Expert'

            -- Catégories numériques (plages d'années)
            WHEN experience_raw ~ '^\s*0\s*[-à]\s*[12]'        THEN 'Junior / Débutant'
            WHEN experience_raw ~ '^\s*[12]\s*[-à]\s*[34]'     THEN 'Intermédiaire'
            WHEN experience_raw ~ '^\s*[34]\s*[-à]\s*[5-9]'    THEN 'Senior / Confirmé'
            WHEN experience_raw ~ '\m([5-9]|1[0-9])\s*ans?'    THEN 'Senior / Confirmé'
            WHEN experience_raw ~ '\m[1-2]\s*ans?'             THEN 'Junior / Débutant'
            WHEN experience_raw ~ '\m[3-4]\s*ans?'             THEN 'Intermédiaire'

            ELSE 'Non spécifié'
        END AS experience_normalized,
        -- Niveau hiérarchique (utile pour trier dans Power BI)
        CASE
            WHEN experience_raw ILIKE '%lead%'
              OR experience_raw ILIKE '%director%'
              OR experience_raw ILIKE '%executive%'
              OR experience_raw ILIKE '%expert%'              THEN 5
            WHEN experience_raw ILIKE '%senior%'
              OR experience_raw ILIKE '%confirm%'
              OR experience_raw ~ '\m([5-9]|1[0-9])\s*ans?'   THEN 4
            WHEN experience_raw ILIKE '%mid%'
              OR experience_raw ILIKE '%associate%'
              OR experience_raw ILIKE '%intermediate%'
              OR experience_raw ~ '\m[3-4]\s*ans?'            THEN 3
            WHEN experience_raw ILIKE '%débutant%'
              OR experience_raw ILIKE '%junior%'
              OR experience_raw ILIKE '%entry%'
              OR experience_raw ILIKE '%stagiaire%'
              OR experience_raw ILIKE '%internship%'
              OR experience_raw ~ '\m[1-2]\s*ans?'            THEN 2
            ELSE 0
        END AS experience_level_order
    FROM raw_experience
)

SELECT
    DENSE_RANK() OVER (ORDER BY MIN(experience_level_order), experience_normalized) AS experience_id,
    experience_normalized,
    MIN(experience_level_order) AS experience_level_order,
    -- Catégorie macro
    CASE
        WHEN MIN(experience_level_order) >= 4 THEN 'Senior'
        WHEN MIN(experience_level_order) >= 2 THEN 'Junior / Mid'
        ELSE 'Non spécifié'
    END AS experience_category,
    STRING_AGG(DISTINCT experience_raw, ' | ' ORDER BY experience_raw) AS raw_variants,
    COUNT(DISTINCT experience_raw) AS nb_raw_variants
FROM normalized
GROUP BY experience_normalized
ORDER BY MIN(experience_level_order)