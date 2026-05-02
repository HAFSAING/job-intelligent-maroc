{{ config(materialized='table') }}

-- Jobs Unified : union des 4 sources avec déduplication par URL
WITH unioned AS (
    SELECT * FROM {{ ref('stg_rekrute') }}
    UNION ALL
    SELECT * FROM {{ ref('stg_dreamjob') }}
    UNION ALL
    SELECT * FROM {{ ref('stg_indeed') }}
    UNION ALL
    SELECT * FROM {{ ref('stg_linkedin') }}
),

-- Déduplication : on garde la 1ère occurrence par URL
deduped AS (
    SELECT *,
        ROW_NUMBER() OVER (
            PARTITION BY url
            ORDER BY scraped_at DESC
        ) AS rn
    FROM unioned
),

final AS (
    SELECT
        job_id,
        job_title,
        company,
        location_raw,
        city,
        summary,
        description,
        sector,
        function,
        experience,
        education,
        contract_type,
        posted_date_raw,
        url,
        source,
        search_keyword,
        scraped_at,

        -- Indicateurs de complétude utiles pour Power BI
        CASE WHEN company IS NOT NULL THEN 1 ELSE 0 END        AS has_company,
        CASE WHEN city IS NOT NULL THEN 1 ELSE 0 END           AS has_city,
        CASE WHEN function IS NOT NULL THEN 1 ELSE 0 END       AS has_function,
        CASE WHEN contract_type IS NOT NULL THEN 1 ELSE 0 END  AS has_contract,
        CASE WHEN sector IS NOT NULL THEN 1 ELSE 0 END         AS has_sector,
        CASE WHEN education IS NOT NULL THEN 1 ELSE 0 END      AS has_education,
        CASE WHEN experience IS NOT NULL THEN 1 ELSE 0 END     AS has_experience,
        LENGTH(COALESCE(description, ''))                       AS description_length

    FROM deduped
    WHERE rn = 1
)

SELECT * FROM final