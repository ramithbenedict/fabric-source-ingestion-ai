/* =====================================================================
   RMA validation, DPV2 side
   Run on: SQL analytics endpoint of lakehouse LH_SDS_RMA (Platform-Hub).
   Twin file: dpv1_spot_validation.sql (same output shape, run in SPOT_RMA).
   Run each block on its own. Compare the outputs of both sides.
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
          SELECT 'actions'                 AS table_name, COUNT_BIG(*) AS row_count FROM dbo.actions
UNION ALL SELECT 'business_units',          COUNT_BIG(*) FROM dbo.business_units
UNION ALL SELECT 'global_business_units',   COUNT_BIG(*) FROM dbo.global_business_units
UNION ALL SELECT 'iso4217_currencies',      COUNT_BIG(*) FROM dbo.iso4217_currencies
UNION ALL SELECT 'lookup_values',           COUNT_BIG(*) FROM dbo.lookup_values
UNION ALL SELECT 'lookup_types',            COUNT_BIG(*) FROM dbo.lookup_types
UNION ALL SELECT 'organizational_entities', COUNT_BIG(*) FROM dbo.organizational_entities
UNION ALL SELECT 'prebids',                 COUNT_BIG(*) FROM dbo.prebids
UNION ALL SELECT 'projects',                COUNT_BIG(*) FROM dbo.projects
UNION ALL SELECT 'rbs',                     COUNT_BIG(*) FROM dbo.rbs
UNION ALL SELECT 'risk_registers',          COUNT_BIG(*) FROM dbo.risk_registers
UNION ALL SELECT 'risks',                   COUNT_BIG(*) FROM dbo.risks
UNION ALL SELECT 'risks_history',           COUNT_BIG(*) FROM dbo.risks_history
UNION ALL SELECT 'rpets',                   COUNT_BIG(*) FROM dbo.rpets
UNION ALL SELECT 'threat_matrices',         COUNT_BIG(*) FROM dbo.threat_matrices
UNION ALL SELECT 'opportunity_matrices',    COUNT_BIG(*) FROM dbo.opportunity_matrices
UNION ALL SELECT 'permissions',             COUNT_BIG(*) FROM dbo.permissions
UNION ALL SELECT 'users',                   COUNT_BIG(*) FROM dbo.users
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
-- SELECT * FROM dbo.risks WHERE [Id] IN (1, 2, 3) ORDER BY [Id];


/* ---- 6. QUALITY CHECKS --------------------------------------------- */
-- 6a. Duplicate Id (expect 0)
SELECT 'risks' AS table_name, COUNT_BIG(*) - COUNT_BIG(DISTINCT [Id]) AS duplicate_ids FROM dbo.risks
UNION ALL SELECT 'risks_history', COUNT_BIG(*) - COUNT_BIG(DISTINCT [Id]) FROM dbo.risks_history
UNION ALL SELECT 'actions',       COUNT_BIG(*) - COUNT_BIG(DISTINCT [Id]) FROM dbo.actions
UNION ALL SELECT 'users',         COUNT_BIG(*) - COUNT_BIG(DISTINCT [Id]) FROM dbo.users;

-- 6b. HTML tags left in the cleaned text columns (expect 0 on both sides)
SELECT 'risks.description' AS column_name, COUNT_BIG(*) AS rows_with_tags FROM dbo.risks WHERE [Description] LIKE '%<%>%'
UNION ALL SELECT 'risks.causes',               COUNT_BIG(*) FROM dbo.risks         WHERE [Causes]      LIKE '%<%>%'
UNION ALL SELECT 'risks_history.description',  COUNT_BIG(*) FROM dbo.risks_history WHERE [Description] LIKE '%<%>%'
UNION ALL SELECT 'actions.description',        COUNT_BIG(*) FROM dbo.actions       WHERE [Description] LIKE '%<%>%';

-- 6c. Users with an email (the extract joins MDM_Mirror_Person)
SELECT COUNT_BIG(*) AS users,
       SUM(CASE WHEN [Email] IS NULL THEN 1 ELSE 0 END) AS without_email
FROM   dbo.users;


/* ---- 7. FRESHNESS (notebook, not SQL) --------------------------------
   Last write per table, run in a Fabric notebook on LH_SDS_RMA:
       spark.sql("DESCRIBE HISTORY dbo.risks").select("timestamp","operation").show(3, False)
   Expect: today, operation WRITE / OVERWRITE. */
