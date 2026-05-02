{{ config(materialized='table') }}

-- ====================================================================
-- DIMENSION : dim_skill
-- ====================================================================
-- Liste des compétences techniques avec :
--   - skill_name : nom canonique (ex: "Python")
--   - skill_pattern : regex utilisée pour détecter la skill dans une description
--   - skill_category : famille de la compétence (langage, cloud, BI, etc.)
-- Cette table est UTILISÉE par bridge_job_skill pour faire le matching.
--
-- Clé primaire : skill_id
-- Clé naturelle : skill_name
-- ====================================================================

WITH skills AS (
    SELECT * FROM (VALUES
        -- Langages de programmation
        ('Python',          '\mPython\M',                                'Langage'),
        ('SQL',             '\mSQL\M',                                   'Langage'),
        ('Java',            '\mJava\M',                                  'Langage'),
        ('Scala',           '\mScala\M',                                 'Langage'),
        ('R',               '\mR\M',                                     'Langage'),

        -- Big Data & Streaming
        ('Spark',           '\m(Apache\s+)?Spark\M',                     'Big Data'),
        ('Hadoop',          '\mHadoop\M',                                'Big Data'),
        ('Kafka',           '\mKafka\M',                                 'Big Data'),
        ('Hive',            '\mHive\M',                                  'Big Data'),

        -- Orchestration & Transformation
        ('Airflow',         '\mAirflow\M',                               'Orchestration'),
        ('dbt',             '\mdbt\M',                                   'Transformation'),
        ('Talend',          '\mTalend\M',                                'ETL'),
        ('Informatica',     '\mInformatica\M',                           'ETL'),
        ('SSIS',            '\mSSIS\M',                                  'ETL'),
        ('ETL',             '\mETL\M|\mELT\M',                           'ETL'),

        -- Cloud
        ('AWS',             '\mAWS\M|\mAmazon\s+Web\s+Services\M',       'Cloud'),
        ('Azure',           '\mAzure\M',                                 'Cloud'),
        ('GCP',             '\mGCP\M|\mGoogle\s+Cloud\M',                'Cloud'),

        -- Data warehouses
        ('Snowflake',       '\mSnowflake\M',                             'Data Warehouse'),
        ('Databricks',      '\mDatabricks\M',                            'Data Warehouse'),
        ('Redshift',        '\mRedshift\M',                              'Data Warehouse'),
        ('BigQuery',        '\mBigQuery\M',                              'Data Warehouse'),

        -- Bases de données
        ('PostgreSQL',      '\mPostgreSQL\M|\mPostgres\M',               'Base de données'),
        ('MySQL',           '\mMySQL\M',                                 'Base de données'),
        ('MongoDB',         '\mMongoDB\M',                               'Base de données'),
        ('Oracle',          '\mOracle\M',                                'Base de données'),

        -- BI & Visualisation
        ('Power BI',        '\mPower\s*BI\M',                            'BI / Visualisation'),
        ('Tableau',         '\mTableau\M',                               'BI / Visualisation'),
        ('Looker',          '\mLooker\M',                                'BI / Visualisation'),
        ('Excel',           '\mExcel\M',                                 'BI / Visualisation'),

        -- Machine Learning & Data Science
        ('Machine Learning','\mMachine\s+Learning\M|\bML\M',             'Machine Learning'),
        ('Deep Learning',   '\mDeep\s+Learning\M',                       'Machine Learning'),
        ('NLP',             '\mNLP\M|\bNatural\s+Language\b',            'Machine Learning'),
        ('TensorFlow',      '\mTensorFlow\M',                            'Machine Learning'),
        ('PyTorch',         '\mPyTorch\M',                               'Machine Learning'),
        ('Scikit-learn',    '\mScikit[- ]learn\M|\msklearn\M',           'Machine Learning'),
        ('Pandas',          '\mPandas\M',                                'Machine Learning'),
        ('NumPy',           '\mNumPy\M',                                 'Machine Learning'),

        -- DevOps / Infra
        ('Docker',          '\mDocker\M',                                'DevOps'),
        ('Kubernetes',      '\mKubernetes\M|\mK8s\M',                    'DevOps'),
        ('Git',             '\mGit\M|\mGitHub\M|\mGitLab\M',             'DevOps'),
        ('Linux',           '\mLinux\M|\mUnix\M',                        'DevOps')
    ) AS s(skill_name, skill_pattern, skill_category)
)

SELECT
    ROW_NUMBER() OVER (ORDER BY skill_category, skill_name) AS skill_id,
    skill_name,
    skill_pattern,
    skill_category
FROM skills
ORDER BY skill_category, skill_name