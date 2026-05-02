{{ config(materialized='table') }}

-- ====================================================================
-- TABLE DE FAITS : fct_jobs
-- ====================================================================
-- 1 ligne = 1 offre d'emploi unique (post-déduplication par URL).
-- Contient :
--   - les FK vers toutes les dimensions (city_id, company_id, ...)
--   - les attributs descriptifs (job_title, description, url)
--   - les flags de complétude (déjà calculés en silver)
--
-- C'est LA table principale que Power BI va consommer.
-- Toutes les dim_* sont reliées à elle via leurs clés primaires.
-- ====================================================================

WITH jobs AS (
    SELECT
        j.job_id,
        j.job_title,
        j.summary,
        j.description,
        j.url,
        j.posted_date_raw,
        j.scraped_at,
        j.search_keyword,
        j.description_length,

        -- Champs bruts (pour rejoindre les dimensions)
        j.company,
        j.city,
        j.source,
        j.contract_type,
        j.education,
        j.experience,

        -- Flags de complétude (déjà calculés en silver)
        j.has_company,
        j.has_city,
        j.has_function,
        j.has_contract,
        j.has_sector,
        j.has_education,
        j.has_experience,

        -- Recalcul de la valeur normalisée pour les jointures (même logique que dans les dim_*)
        TRIM(SPLIT_PART(j.contract_type, '-', 1)) AS contract_main_for_join

    FROM {{ ref('jobs_unified') }} j
),

-- Calcul du score de qualité (0-100) basé sur la complétude
quality AS (
    SELECT
        job_id,
        ROUND(100.0 * (
            COALESCE(has_company, 0)
          + COALESCE(has_city, 0)
          + COALESCE(has_function, 0)
          + COALESCE(has_contract, 0)
          + COALESCE(has_sector, 0)
          + COALESCE(has_education, 0)
          + COALESCE(has_experience, 0)
          + CASE WHEN description_length >= 200 THEN 1 ELSE 0 END
        ) / 8.0)::int AS quality_score
    FROM jobs
),

-- Jointures avec les dimensions pour récupérer les FK
final AS (
    SELECT
        -- Clé primaire
        j.job_id,

        -- ====== Foreign keys vers les dimensions ======
        ds.source_id,
        dc.city_id,
        dco.company_id,
        dct.contract_id,
        de.education_id,
        dex.experience_id,
        dd.date_id           AS scraped_date_id,    -- date de scraping

        -- ====== Attributs descriptifs (degenerate dimensions) ======
        j.job_title,
        j.summary,
        j.description,
        j.url,
        j.posted_date_raw,
        j.search_keyword,

        -- ====== Mesures (pour agrégations) ======
        j.description_length,
        q.quality_score,
        1                    AS offer_count,         -- toujours 1 (compteur d'offres)

        -- ====== Flags de complétude ======
        j.has_company,
        j.has_city,
        j.has_function,
        j.has_contract,
        j.has_sector,
        j.has_education,
        j.has_experience,

        -- ====== Dates ======
        j.scraped_at

    FROM jobs j

    LEFT JOIN quality q
        ON j.job_id = q.job_id

    -- Source (jointure simple sur le nom)
    LEFT JOIN {{ ref('dim_source') }} ds
        ON j.source = ds.source_key

    -- City (jointure via la même logique de normalisation que dim_city)
    LEFT JOIN {{ ref('dim_city') }} dc
        ON dc.city_normalized = CASE
            WHEN j.city ILIKE '%casablanca%'                        THEN 'Casablanca'
            WHEN j.city ILIKE '%rabat%'                             THEN 'Rabat'
            WHEN j.city ILIKE '%marrakech%'                         THEN 'Marrakech'
            WHEN j.city ILIKE '%tanger%'                            THEN 'Tanger'
            WHEN j.city ILIKE '%fès%'
              OR j.city ILIKE '%fes%'
              OR j.city ILIKE '%fez%'                               THEN 'Fès'
            WHEN j.city ILIKE '%agadir%'                            THEN 'Agadir'
            WHEN j.city ILIKE '%meknès%'
              OR j.city ILIKE '%meknes%'                            THEN 'Meknès'
            WHEN j.city ILIKE '%oujda%'                             THEN 'Oujda'
            WHEN j.city ILIKE '%kénitra%'
              OR j.city ILIKE '%kenitra%'                           THEN 'Kénitra'
            WHEN j.city ILIKE '%tétouan%'
              OR j.city ILIKE '%tetouan%'                           THEN 'Tétouan'
            WHEN j.city ILIKE '%salé%'
              OR j.city ILIKE '%sale%'                              THEN 'Salé'
            WHEN j.city ILIKE '%mohammedia%'                        THEN 'Mohammedia'
            WHEN j.city ILIKE '%el jadida%'                         THEN 'El Jadida'
            WHEN j.city ILIKE '%nador%'                             THEN 'Nador'
            WHEN j.city ILIKE '%settat%'
             AND j.city NOT ILIKE '%casablanca%'                    THEN 'Settat'
            WHEN j.city ILIKE '%berrechid%'                         THEN 'Berrechid'
            WHEN j.city ILIKE '%khouribga%'                         THEN 'Khouribga'
            WHEN j.city ILIKE '%beni mellal%'                       THEN 'Beni Mellal'
            WHEN j.city ILIKE '%temara%'
              OR j.city ILIKE '%témara%'                            THEN 'Témara'
            WHEN j.city ILIKE '%safi%'                              THEN 'Safi'
            WHEN j.city ILIKE '%essaouira%'                         THEN 'Essaouira'
            WHEN j.city ILIKE '%ifrane%'                            THEN 'Ifrane'
            WHEN j.city ILIKE '%ouarzazate%'                        THEN 'Ouarzazate'
            WHEN j.city ILIKE '%laâyoune%'
              OR j.city ILIKE '%laayoune%'                          THEN 'Laâyoune'
            WHEN j.city ILIKE '%dakhla%'                            THEN 'Dakhla'
            WHEN j.city ILIKE '%maroc%'
              OR j.city ILIKE '%morocco%'                           THEN 'Maroc (national)'
            ELSE INITCAP(TRIM(j.city))
        END

    -- Company (jointure simple par nom)
    LEFT JOIN {{ ref('dim_company') }} dco
        ON j.company = dco.company

    -- Contract (jointure via le contrat normalisé)
    LEFT JOIN {{ ref('dim_contract') }} dct
        ON dct.contract_normalized = CASE
            WHEN j.contract_main_for_join ILIKE '%CDI%'                 THEN 'CDI'
            WHEN j.contract_main_for_join ILIKE '%CDD%'                 THEN 'CDD'
            WHEN j.contract_main_for_join ILIKE '%stage%'
              OR j.contract_main_for_join ILIKE '%intern%'              THEN 'Stage'
            WHEN j.contract_main_for_join ILIKE '%PFE%'                 THEN 'PFE'
            WHEN j.contract_main_for_join ILIKE '%alternance%'
              OR j.contract_main_for_join ILIKE '%apprentice%'          THEN 'Alternance'
            WHEN j.contract_main_for_join ILIKE '%freelance%'
              OR j.contract_main_for_join ILIKE '%contract%'            THEN 'Freelance'
            WHEN j.contract_main_for_join ILIKE '%temps plein%'
              OR j.contract_main_for_join ILIKE '%full%time%'           THEN 'Temps plein'
            WHEN j.contract_main_for_join ILIKE '%temps partiel%'
              OR j.contract_main_for_join ILIKE '%part%time%'           THEN 'Temps partiel'
            ELSE 'Autre'
        END

    -- Education (jointure via le niveau normalisé)
    LEFT JOIN {{ ref('dim_education') }} de
        ON de.education_normalized = CASE
            WHEN j.education ILIKE '%doctorat%'
              OR j.education ILIKE '%phd%'
              OR j.education ILIKE '%doctorate%'                        THEN 'Doctorat'
            WHEN j.education ILIKE '%bac%+%5%'
              OR j.education ILIKE '%bac+5%'
              OR j.education ILIKE '%master%'
              OR j.education ILIKE '%ing[ée]nieur%'
              OR j.education ILIKE '%MSc%'                              THEN 'Bac+5 / Master / Ingénieur'
            WHEN j.education ILIKE '%bac%+%4%'
              OR j.education ILIKE '%bac+4%'                            THEN 'Bac+4'
            WHEN j.education ILIKE '%bac%+%3%'
              OR j.education ILIKE '%bac+3%'
              OR j.education ILIKE '%licence%'
              OR j.education ILIKE '%bachelor%'                         THEN 'Bac+3 / Licence'
            WHEN j.education ILIKE '%bac%+%2%'
              OR j.education ILIKE '%bac+2%'
              OR j.education ILIKE '%BTS%'
              OR j.education ILIKE '%DUT%'                              THEN 'Bac+2 / BTS / DUT'
            ELSE 'Autre / Non spécifié'
        END

    -- Experience (jointure via le niveau normalisé)
    LEFT JOIN {{ ref('dim_experience') }} dex
        ON dex.experience_normalized = CASE
            WHEN j.experience ILIKE '%débutant%'
              OR j.experience ILIKE '%junior%'
              OR j.experience ILIKE '%entry%'
              OR j.experience ILIKE '%stagiaire%'
              OR j.experience ILIKE '%internship%'                      THEN 'Junior / Débutant'
            WHEN j.experience ILIKE '%mid%'
              OR j.experience ILIKE '%associate%'
              OR j.experience ILIKE '%intermediate%'                    THEN 'Intermédiaire'
            WHEN j.experience ILIKE '%senior%'
              OR j.experience ILIKE '%confirm%'                         THEN 'Senior / Confirmé'
            WHEN j.experience ILIKE '%lead%'
              OR j.experience ILIKE '%director%'
              OR j.experience ILIKE '%executive%'
              OR j.experience ILIKE '%expert%'                          THEN 'Lead / Expert'
            WHEN j.experience ~ '\m([5-9]|1[0-9])\s*ans?'                THEN 'Senior / Confirmé'
            WHEN j.experience ~ '\m[3-4]\s*ans?'                         THEN 'Intermédiaire'
            WHEN j.experience ~ '\m[1-2]\s*ans?'                         THEN 'Junior / Débutant'
            ELSE 'Non spécifié'
        END

    -- Date (jointure sur la date de scraping)
    LEFT JOIN {{ ref('dim_date') }} dd
        ON dd.full_date = DATE(j.scraped_at)
)

SELECT * FROM final