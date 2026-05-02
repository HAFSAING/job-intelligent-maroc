{{ config(materialized='table') }}

-- ====================================================================
-- DIMENSION : dim_city
-- ====================================================================
-- Normalise les villes :
--   "Casablanca 20040" → "Casablanca"
--   "Mâchouar de Casablanca" → "Casablanca"
--   "Casablanca et périphérie" → "Casablanca"
-- Clé primaire : city_id
-- Clé naturelle : city_normalized (utilisée pour la jointure)
-- ====================================================================

WITH raw_cities AS (
    SELECT DISTINCT
        city AS city_raw
    FROM {{ ref('jobs_unified') }}
    WHERE city IS NOT NULL AND TRIM(city) <> ''
),

normalized AS (
    SELECT
        city_raw,
        CASE
            WHEN city_raw ILIKE '%casablanca%'                THEN 'Casablanca'
            WHEN city_raw ILIKE '%rabat%'                     THEN 'Rabat'
            WHEN city_raw ILIKE '%marrakech%'                 THEN 'Marrakech'
            WHEN city_raw ILIKE '%tanger%'                    THEN 'Tanger'
            WHEN city_raw ILIKE '%fès%'
              OR city_raw ILIKE '%fes%'
              OR city_raw ILIKE '%fez%'                       THEN 'Fès'
            WHEN city_raw ILIKE '%agadir%'                    THEN 'Agadir'
            WHEN city_raw ILIKE '%meknès%'
              OR city_raw ILIKE '%meknes%'                    THEN 'Meknès'
            WHEN city_raw ILIKE '%oujda%'                     THEN 'Oujda'
            WHEN city_raw ILIKE '%kénitra%'
              OR city_raw ILIKE '%kenitra%'                   THEN 'Kénitra'
            WHEN city_raw ILIKE '%tétouan%'
              OR city_raw ILIKE '%tetouan%'                   THEN 'Tétouan'
            WHEN city_raw ILIKE '%salé%'
              OR city_raw ILIKE '%sale%'                      THEN 'Salé'
            WHEN city_raw ILIKE '%mohammedia%'                THEN 'Mohammedia'
            WHEN city_raw ILIKE '%el jadida%'                 THEN 'El Jadida'
            WHEN city_raw ILIKE '%nador%'                     THEN 'Nador'
            WHEN city_raw ILIKE '%settat%'
             AND city_raw NOT ILIKE '%casablanca%'            THEN 'Settat'
            WHEN city_raw ILIKE '%berrechid%'                 THEN 'Berrechid'
            WHEN city_raw ILIKE '%khouribga%'                 THEN 'Khouribga'
            WHEN city_raw ILIKE '%beni mellal%'               THEN 'Beni Mellal'
            WHEN city_raw ILIKE '%temara%'
              OR city_raw ILIKE '%témara%'                    THEN 'Témara'
            WHEN city_raw ILIKE '%safi%'                      THEN 'Safi'
            WHEN city_raw ILIKE '%essaouira%'                 THEN 'Essaouira'
            WHEN city_raw ILIKE '%ifrane%'                    THEN 'Ifrane'
            WHEN city_raw ILIKE '%ouarzazate%'                THEN 'Ouarzazate'
            WHEN city_raw ILIKE '%laâyoune%'
              OR city_raw ILIKE '%laayoune%'                  THEN 'Laâyoune'
            WHEN city_raw ILIKE '%dakhla%'                    THEN 'Dakhla'
            WHEN city_raw ILIKE '%maroc%'
              OR city_raw ILIKE '%morocco%'                   THEN 'Maroc (national)'
            ELSE INITCAP(TRIM(city_raw))
        END AS city_normalized,
        -- Région (regroupement de plus haut niveau pour Power BI)
        CASE
            WHEN city_raw ILIKE '%casablanca%'
              OR city_raw ILIKE '%mohammedia%'
              OR city_raw ILIKE '%berrechid%'
              OR city_raw ILIKE '%settat%'
              OR city_raw ILIKE '%el jadida%'                 THEN 'Casablanca-Settat'
            WHEN city_raw ILIKE '%rabat%'
              OR city_raw ILIKE '%salé%'
              OR city_raw ILIKE '%sale%'
              OR city_raw ILIKE '%temara%'
              OR city_raw ILIKE '%témara%'
              OR city_raw ILIKE '%kénitra%'
              OR city_raw ILIKE '%kenitra%'                   THEN 'Rabat-Salé-Kénitra'
            WHEN city_raw ILIKE '%marrakech%'
              OR city_raw ILIKE '%safi%'
              OR city_raw ILIKE '%essaouira%'                 THEN 'Marrakech-Safi'
            WHEN city_raw ILIKE '%tanger%'
              OR city_raw ILIKE '%tétouan%'
              OR city_raw ILIKE '%tetouan%'                   THEN 'Tanger-Tétouan-Al Hoceïma'
            WHEN city_raw ILIKE '%fès%'
              OR city_raw ILIKE '%fes%'
              OR city_raw ILIKE '%meknès%'
              OR city_raw ILIKE '%meknes%'                    THEN 'Fès-Meknès'
            WHEN city_raw ILIKE '%oujda%'
              OR city_raw ILIKE '%nador%'                     THEN 'Oriental'
            WHEN city_raw ILIKE '%agadir%'                    THEN 'Souss-Massa'
            WHEN city_raw ILIKE '%beni mellal%'
              OR city_raw ILIKE '%khouribga%'                 THEN 'Béni Mellal-Khénifra'
            WHEN city_raw ILIKE '%ifrane%'                    THEN 'Fès-Meknès'
            WHEN city_raw ILIKE '%ouarzazate%'
              OR city_raw ILIKE '%laâyoune%'
              OR city_raw ILIKE '%laayoune%'
              OR city_raw ILIKE '%dakhla%'                    THEN 'Sud'
            ELSE 'Non spécifiée'
        END AS region
    FROM raw_cities
)

SELECT
    ROW_NUMBER() OVER (ORDER BY city_normalized) AS city_id,
    city_normalized,
    region,
    -- Liste des variantes brutes regroupées (utile pour Power BI / debugging)
    STRING_AGG(DISTINCT city_raw, ' | ' ORDER BY city_raw) AS raw_variants,
    COUNT(DISTINCT city_raw) AS nb_raw_variants
FROM normalized
GROUP BY city_normalized, region
ORDER BY city_normalized