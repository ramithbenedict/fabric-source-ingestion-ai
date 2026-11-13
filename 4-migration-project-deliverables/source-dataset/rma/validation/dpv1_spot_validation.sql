/* =====================================================================
   RMA validation, DPV1 side
   Run on: Synapse serverless SQL pool, database SPOT_RMA (lake database).
   Twin file: dpv2_lakehouse_validation.sql (same output shape).
   Run each block on its own. Compare the outputs of both sides.
   If your tables are not in schema dbo, replace 'dbo' / dbo. below.
   If SPOT_RMA is a dedicated pool, the script works unchanged.
   ===================================================================== */

/* ---- 1. TABLE COUNT: expect 18 rows ------------------------------- */
SELECT COUNT(*) AS table_count
FROM   INFORMATION_SCHEMA.TABLES
WHERE  TABLE_SCHEMA = 'dbo' AND TABLE_TYPE = 'BASE TABLE';

SELECT LOWER(TABLE_NAME) AS table_name
FROM   INFORMATION_SCHEMA.TABLES
WHERE  TABLE_SCHEMA = 'dbo' AND TABLE_TYPE = 'BASE TABLE'
ORDER BY 1;


/* ---- 2. ROW COUNT per table --------------------------------------- */
SELECT table_name, row_count FROM (
          SELECT 'actions'                 AS table_name, COUNT_BIG(*) AS row_count FROM dbo.Actions
UNION ALL SELECT 'business_units',          COUNT_BIG(*) FROM dbo.Business_Units
UNION ALL SELECT 'global_business_units',   COUNT_BIG(*) FROM dbo.Global_Business_Units
UNION ALL SELECT 'iso4217_currencies',      COUNT_BIG(*) FROM dbo.Iso4217_Currencies
UNION ALL SELECT 'lookup_values',           COUNT_BIG(*) FROM dbo.Lookup_Values
UNION ALL SELECT 'lookup_types',            COUNT_BIG(*) FROM dbo.Lookup_Types
UNION ALL SELECT 'organizational_entities', COUNT_BIG(*) FROM dbo.organizational_entities
UNION ALL SELECT 'prebids',                 COUNT_BIG(*) FROM dbo.PreBids
UNION ALL SELECT 'projects',                COUNT_BIG(*) FROM dbo.Projects
UNION ALL SELECT 'rbs',                     COUNT_BIG(*) FROM dbo.RBS
UNION ALL SELECT 'risk_registers',          COUNT_BIG(*) FROM dbo.Risk_Registers
UNION ALL SELECT 'risks',                   COUNT_BIG(*) FROM dbo.Risks
UNION ALL SELECT 'risks_history',           COUNT_BIG(*) FROM dbo.Risks_History
UNION ALL SELECT 'rpets',                   COUNT_BIG(*) FROM dbo.RPETS
UNION ALL SELECT 'threat_matrices',         COUNT_BIG(*) FROM dbo.Threat_Matrices
UNION ALL SELECT 'opportunity_matrices',    COUNT_BIG(*) FROM dbo.Opportunity_Matrices
UNION ALL SELECT 'permissions',             COUNT_BIG(*) FROM dbo.Permissions
UNION ALL SELECT 'users',                   COUNT_BIG(*) FROM dbo.Users
) x ORDER BY table_name;


/* ---- 3. FORMAT: one row per table and column ----------------------
   Compare column_name and position first; data types can differ in
   spelling between engines (string vs varchar, bigint vs int). */
SELECT LOWER(TABLE_NAME)  AS table_name,
       ORDINAL_POSITION   AS position,
       LOWER(COLUMN_NAME) AS column_name,
       DATA_TYPE          AS data_type,
       CHARACTER_MAXIMUM_LENGTH AS max_len,
       IS_NULLABLE        AS nullable
FROM   INFORMATION_SCHEMA.COLUMNS
WHERE  TABLE_SCHEMA = 'dbo'
ORDER BY 1, 2;

-- Column count per table
SELECT LOWER(TABLE_NAME) AS table_name, COUNT(*) AS column_count
FROM   INFORMATION_SCHEMA.COLUMNS
WHERE  TABLE_SCHEMA = 'dbo'
GROUP BY LOWER(TABLE_NAME)
ORDER BY 1;


/* ---- 4. COLUMN PROFILE (generator) ---------------------------------
   Returns one SQL text per table. Copy the text, run it, and run the same
   text on the other side. Per column: non-null, distinct, min, max,
   numeric sum and total text length. Identical rows = identical content.
   Run the SQL for one table at a time (big tables: Risks, Risks_History). */
SELECT LOWER(TABLE_NAME) AS table_name,
       STRING_AGG(CAST(
         'SELECT ''' + LOWER(COLUMN_NAME) + ''' AS column_name, '
       + 'COUNT_BIG(' + QUOTENAME(COLUMN_NAME) + ') AS non_null, '
       + 'COUNT_BIG(DISTINCT ' + QUOTENAME(COLUMN_NAME) + ') AS distinct_values, '
       + CASE WHEN DATA_TYPE IN ('bit','varbinary','binary','image','text','ntext','xml','uniqueidentifier')
              THEN 'NULL AS min_value, NULL AS max_value, '
              ELSE 'CAST(MIN(' + QUOTENAME(COLUMN_NAME) + ') AS varchar(60)) AS min_value, '
                 + 'CAST(MAX(' + QUOTENAME(COLUMN_NAME) + ') AS varchar(60)) AS max_value, ' END
       + CASE WHEN DATA_TYPE IN ('int','bigint','smallint','tinyint','decimal','numeric','float','real','money')
              THEN 'CAST(SUM(CAST(' + QUOTENAME(COLUMN_NAME) + ' AS float)) AS decimal(38,4)) AS sum_value, '
              ELSE 'NULL AS sum_value, ' END
       + CASE WHEN DATA_TYPE IN ('varchar','nvarchar','char','nchar','string')
              THEN 'SUM(CAST(LEN(' + QUOTENAME(COLUMN_NAME) + ') AS bigint)) AS total_len '
              ELSE 'NULL AS total_len ' END
       + 'FROM dbo.' + QUOTENAME(TABLE_NAME)
       AS varchar(max)), ' UNION ALL ') WITHIN GROUP (ORDER BY ORDINAL_POSITION) AS profile_sql
FROM   INFORMATION_SCHEMA.COLUMNS
WHERE  TABLE_SCHEMA = 'dbo'
GROUP BY LOWER(TABLE_NAME)
ORDER BY 1;


/* ---- 5. SAMPLE DATA (generator) -------------------------------------
   One SQL text per table: first 10 rows ordered by the first column.
   Run the text here and on the other side, then compare by eye. */
SELECT LOWER(c.TABLE_NAME) AS table_name,
       'SELECT TOP 10 * FROM dbo.' + QUOTENAME(c.TABLE_NAME)
     + ' ORDER BY ' + QUOTENAME(c.COLUMN_NAME) AS sample_sql
FROM   INFORMATION_SCHEMA.COLUMNS c
WHERE  c.TABLE_SCHEMA = 'dbo' AND c.ORDINAL_POSITION = 1
ORDER BY 1;

-- Same rows for a given key, for quick spot checks
-- SELECT * FROM dbo.Risks WHERE [Id] IN (1, 2, 3) ORDER BY [Id];


/* ---- 6. QUALITY CHECKS --------------------------------------------- */
-- 6a. Duplicate Id (expect 0)
SELECT 'risks' AS table_name, COUNT_BIG(*) - COUNT_BIG(DISTINCT [Id]) AS duplicate_ids FROM dbo.Risks
UNION ALL SELECT 'risks_history', COUNT_BIG(*) - COUNT_BIG(DISTINCT [Id]) FROM dbo.Risks_History
UNION ALL SELECT 'actions',       COUNT_BIG(*) - COUNT_BIG(DISTINCT [Id]) FROM dbo.Actions
UNION ALL SELECT 'users',         COUNT_BIG(*) - COUNT_BIG(DISTINCT [Id]) FROM dbo.Users;

-- 6b. HTML tags left in the cleaned text columns (expect 0 on both sides)
SELECT 'risks.description' AS column_name, COUNT_BIG(*) AS rows_with_tags FROM dbo.Risks WHERE [Description] LIKE '%<%>%'
UNION ALL SELECT 'risks.causes',               COUNT_BIG(*) FROM dbo.Risks         WHERE [Causes]      LIKE '%<%>%'
UNION ALL SELECT 'risks_history.description',  COUNT_BIG(*) FROM dbo.Risks_History WHERE [Description] LIKE '%<%>%'
UNION ALL SELECT 'actions.description',        COUNT_BIG(*) FROM dbo.Actions       WHERE [Description] LIKE '%<%>%';

-- 6c. Users with an email (the extract joins MDM_Mirror_Person)
SELECT COUNT_BIG(*) AS users,
       SUM(CASE WHEN [Email] IS NULL THEN 1 ELSE 0 END) AS without_email
FROM   dbo.Users;
