{{ config(materialized='table') }}

-- ====================================================================
-- DIMENSION : dim_source
-- ====================================================================
-- Liste les 4 plateformes de scraping avec leurs métadonnées.
-- Clé primaire : source_id (entier auto-attribué)
-- Clé naturelle : source_key (utilisée pour la jointure depuis fct_jobs)
-- ====================================================================

WITH sources AS (
    SELECT * FROM (VALUES
        (1, 'rekrute',  'ReKrute.com',   'https://www.rekrute.com',   'Maroc'),
        (2, 'dreamjob', 'Dreamjob.ma',   'https://www.dreamjob.ma',   'Maroc'),
        (3, 'indeed',   'Indeed Maroc',  'https://ma.indeed.com',     'International'),
        (4, 'linkedin', 'LinkedIn Jobs', 'https://www.linkedin.com',  'International')
    ) AS s(source_id, source_key, source_name, source_url, source_scope)
)

SELECT
    source_id,
    source_key,
    source_name,
    source_url,
    source_scope
FROM sources