{{ config(materialized='view') }}

WITH source AS (
    SELECT * FROM {{ source('bronze', 'linkedin_raw') }}
),

cleaned AS (
    SELECT
        -- LinkedIn a déjà un job_id natif, on l'utilise en priorité
        COALESCE(job_id, MD5(url))                       AS job_id,
        TRIM(job_title)                                  AS job_title,
        INITCAP(TRIM(company))                           AS company,
        TRIM(location)                                   AS location_raw,
        -- LinkedIn location ex: "Casablanca, Casablanca-Settat, Maroc"
        TRIM(SPLIT_PART(location, ',', 1))               AS city,
        TRIM(summary)                                    AS summary,
        TRIM(description)                                AS description,
        TRIM(sector)                                     AS sector,
        TRIM(function)                                   AS function,
        TRIM(experience)                                 AS experience,
        TRIM(education)                                  AS education,
        TRIM(contract_type)                              AS contract_type,
        -- LinkedIn posted_date est au format ISO YYYY-MM-DD, on garde texte
        posted_date                                      AS posted_date_raw,
        url,
        'linkedin'                                       AS source,
        TRIM(search_keyword)                             AS search_keyword,
        scraped_at
    FROM source
    WHERE job_title IS NOT NULL AND url IS NOT NULL
)

SELECT * FROM cleaned