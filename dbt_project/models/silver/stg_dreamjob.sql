{{ config(materialized='view') }}

WITH source AS (
    SELECT * FROM {{ source('bronze', 'dreamjob_raw') }}
),

cleaned AS (
    SELECT
        MD5(url)                                         AS job_id,
        TRIM(job_title)                                  AS job_title,
        INITCAP(TRIM(company))                           AS company,
        TRIM(location)                                   AS location_raw,
        -- Sur dreamjob, location est déjà une ville simple
        TRIM(location)                                   AS city,
        TRIM(summary)                                    AS summary,
        TRIM(description)                                AS description,
        TRIM(sector)                                     AS sector,
        TRIM(function)                                   AS function,
        TRIM(experience)                                 AS experience,
        TRIM(education)                                  AS education,
        TRIM(contract_type)                              AS contract_type,
        posted_date                                      AS posted_date_raw,
        url,
        'dreamjob'                                       AS source,
        NULL::text                                       AS search_keyword,
        scraped_at
    FROM source
    WHERE job_title IS NOT NULL AND url IS NOT NULL
)

SELECT * FROM cleaned