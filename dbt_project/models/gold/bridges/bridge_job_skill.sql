{{ config(materialized='table') }}

-- ====================================================================
-- BRIDGE TABLE : bridge_job_skill
-- ====================================================================
-- Relation many-to-many entre fct_jobs et dim_skill.
-- 1 ligne = (1 offre + 1 compétence détectée dans sa description/titre)
--
-- La détection se fait par regex (skill_pattern de dim_skill) sur
-- le texte combiné job_title + description.
--
-- Clé primaire composite : (job_id, skill_id)
-- ====================================================================

WITH jobs_text AS (
    SELECT
        job_id,
        COALESCE(description, '') || ' ' || COALESCE(job_title, '') AS searchable_text
    FROM {{ ref('fct_jobs') }}
),

-- On joint chaque offre à chaque skill et on garde les matches
matches AS (
    SELECT
        j.job_id,
        s.skill_id,
        s.skill_name,
        s.skill_category
    FROM jobs_text j
    CROSS JOIN {{ ref('dim_skill') }} s
    WHERE j.searchable_text ~* s.skill_pattern
)

SELECT
    job_id,
    skill_id,
    skill_name,        -- dénormalisé pour faciliter les requêtes / debug
    skill_category     -- idem
FROM matches
ORDER BY job_id, skill_id