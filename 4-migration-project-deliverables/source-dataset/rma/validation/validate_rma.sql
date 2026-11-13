/* =====================================================================
   RMA source dataset: post-run validation (DPV1 vs DPV2)
   Run in: Fabric warehouse WH_CATALOG_COMMON (workspace Platform-Hub).
   It reads the lakehouse LH_SDS_RMA by three-part name (same workspace).
   Run each block on its own (select it, then Run).

   Steps
     1. Block 1-3: checks that need nothing from DPV1 (run first).
     2. Block 4:   paste the DPV1 row counts (block B1 at the end), then run.
     3. Block 5:   generates profile queries; run the output on DPV2, and on
                   DPV1 or the RMA source, then compare the two result sets.
     4. Block 6:   RMA-specific checks (HTML removal, Users email).

   Note: the lakehouse SQL endpoint can be case sensitive. Table names are
   lowercase (catalog TargetName); column names keep the source case.
   ===================================================================== */


/* ---------------------------------------------------------------------
   1. COMPLETENESS: every active catalog table exists in the lakehouse
   Expect: Status = OK for all 18 rows.
   --------------------------------------------------------------------- */
SELECT  c.[SchemaName],
        c.[TableName]   AS DPV1_TableName,
        c.[TargetName]  AS DPV2_Table,
        CASE WHEN t.TABLE_NAME IS NULL THEN 'MISSING' ELSE 'OK' END AS [Status]
FROM    [CATALOG].[rma_catalog] c
LEFT JOIN LH_SDS_RMA.INFORMATION_SCHEMA.TABLES t
       ON t.TABLE_SCHEMA = c.[SchemaName] COLLATE DATABASE_DEFAULT
      AND t.TABLE_NAME   = c.[TargetName] COLLATE DATABASE_DEFAULT
WHERE   c.[Active] = 1
ORDER BY [Status] DESC, c.[TableName];

-- Tables in the lakehouse that are not in the catalog (leftovers, test tables)
SELECT  t.TABLE_SCHEMA, t.TABLE_NAME
FROM    LH_SDS_RMA.INFORMATION_SCHEMA.TABLES t
LEFT JOIN [CATALOG].[rma_catalog] c
       ON t.TABLE_NAME = c.[TargetName] COLLATE DATABASE_DEFAULT
WHERE   t.TABLE_TYPE = 'BASE TABLE' AND c.[TargetName] IS NULL;


/* ---------------------------------------------------------------------
   2. ROW COUNTS of DPV2 (no empty table after a full load)
   --------------------------------------------------------------------- */
SELECT * FROM (
    SELECT 'Actions'                 AS TableName, COUNT_BIG(*) AS DPV2_Rows FROM LH_SDS_RMA.dbo.actions
    UNION ALL SELECT 'Business_Units',            COUNT_BIG(*) FROM LH_SDS_RMA.dbo.business_units
    UNION ALL SELECT 'Global_Business_Units',     COUNT_BIG(*) FROM LH_SDS_RMA.dbo.global_business_units
    UNION ALL SELECT 'Iso4217_Currencies',        COUNT_BIG(*) FROM LH_SDS_RMA.dbo.iso4217_currencies
    UNION ALL SELECT 'Lookup_Values',             COUNT_BIG(*) FROM LH_SDS_RMA.dbo.lookup_values
    UNION ALL SELECT 'Lookup_Types',              COUNT_BIG(*) FROM LH_SDS_RMA.dbo.lookup_types
    UNION ALL SELECT 'organizational_entities',   COUNT_BIG(*) FROM LH_SDS_RMA.dbo.organizational_entities
    UNION ALL SELECT 'PreBids',                   COUNT_BIG(*) FROM LH_SDS_RMA.dbo.prebids
    UNION ALL SELECT 'Projects',                  COUNT_BIG(*) FROM LH_SDS_RMA.dbo.projects
    UNION ALL SELECT 'RBS',                       COUNT_BIG(*) FROM LH_SDS_RMA.dbo.rbs
    UNION ALL SELECT 'Risk_Registers',            COUNT_BIG(*) FROM LH_SDS_RMA.dbo.risk_registers
    UNION ALL SELECT 'Risks',                     COUNT_BIG(*) FROM LH_SDS_RMA.dbo.risks
    UNION ALL SELECT 'Risks_History',             COUNT_BIG(*) FROM LH_SDS_RMA.dbo.risks_history
    UNION ALL SELECT 'RPETS',                     COUNT_BIG(*) FROM LH_SDS_RMA.dbo.rpets
    UNION ALL SELECT 'Threat_Matrices',           COUNT_BIG(*) FROM LH_SDS_RMA.dbo.threat_matrices
    UNION ALL SELECT 'Opportunity_Matrices',      COUNT_BIG(*) FROM LH_SDS_RMA.dbo.opportunity_matrices
    UNION ALL SELECT 'Permissions',               COUNT_BIG(*) FROM LH_SDS_RMA.dbo.permissions
    UNION ALL SELECT 'Users',                     COUNT_BIG(*) FROM LH_SDS_RMA.dbo.users
) x
ORDER BY DPV2_Rows, TableName;


/* ---------------------------------------------------------------------
   3. SCHEMA: columns per table (compare with DPV1 / source column list)
   Expect: same column names, same order, compatible types.
   --------------------------------------------------------------------- */
SELECT  TABLE_NAME,
        COUNT(*) AS ColumnCount,
        STRING_AGG(COLUMN_NAME, ', ') WITHIN GROUP (ORDER BY ORDINAL_POSITION) AS Columns_
FROM    LH_SDS_RMA.INFORMATION_SCHEMA.COLUMNS
WHERE   TABLE_SCHEMA = 'dbo'
GROUP BY TABLE_NAME
ORDER BY TABLE_NAME;


/* ---------------------------------------------------------------------
   4. DPV1 vs DPV2 ROW COUNTS
   Paste the DPV1 counts (query B1 below) in the VALUES list, then run.
   Status: OK | DIFF | PASTE DPV1 COUNT
   --------------------------------------------------------------------- */
WITH dpv1 AS (
    SELECT * FROM (VALUES
        ('Actions',                 CAST(NULL AS bigint)),
        ('Business_Units',          NULL),
        ('Global_Business_Units',   NULL),
        ('Iso4217_Currencies',      NULL),
        ('Lookup_Values',           NULL),
        ('Lookup_Types',            NULL),
        ('organizational_entities', NULL),
        ('PreBids',                 NULL),
        ('Projects',                NULL),
        ('RBS',                     NULL),
        ('Risk_Registers',          NULL),
        ('Risks',                   NULL),
        ('Risks_History',           NULL),
        ('RPETS',                   NULL),
        ('Threat_Matrices',         NULL),
        ('Opportunity_Matrices',    NULL),
        ('Permissions',             NULL),
        ('Users',                   NULL)
    ) v (TableName, DPV1_Rows)
),
dpv2 AS (
    SELECT 'Actions' AS TableName, COUNT_BIG(*) AS DPV2_Rows FROM LH_SDS_RMA.dbo.actions
    UNION ALL SELECT 'Business_Units',          COUNT_BIG(*) FROM LH_SDS_RMA.dbo.business_units
    UNION ALL SELECT 'Global_Business_Units',   COUNT_BIG(*) FROM LH_SDS_RMA.dbo.global_business_units
    UNION ALL SELECT 'Iso4217_Currencies',      COUNT_BIG(*) FROM LH_SDS_RMA.dbo.iso4217_currencies
    UNION ALL SELECT 'Lookup_Values',           COUNT_BIG(*) FROM LH_SDS_RMA.dbo.lookup_values
    UNION ALL SELECT 'Lookup_Types',            COUNT_BIG(*) FROM LH_SDS_RMA.dbo.lookup_types
    UNION ALL SELECT 'organizational_entities', COUNT_BIG(*) FROM LH_SDS_RMA.dbo.organizational_entities
    UNION ALL SELECT 'PreBids',                 COUNT_BIG(*) FROM LH_SDS_RMA.dbo.prebids
    UNION ALL SELECT 'Projects',                COUNT_BIG(*) FROM LH_SDS_RMA.dbo.projects
    UNION ALL SELECT 'RBS',                     COUNT_BIG(*) FROM LH_SDS_RMA.dbo.rbs
    UNION ALL SELECT 'Risk_Registers',          COUNT_BIG(*) FROM LH_SDS_RMA.dbo.risk_registers
    UNION ALL SELECT 'Risks',                   COUNT_BIG(*) FROM LH_SDS_RMA.dbo.risks
    UNION ALL SELECT 'Risks_History',           COUNT_BIG(*) FROM LH_SDS_RMA.dbo.risks_history
    UNION ALL SELECT 'RPETS',                   COUNT_BIG(*) FROM LH_SDS_RMA.dbo.rpets
    UNION ALL SELECT 'Threat_Matrices',         COUNT_BIG(*) FROM LH_SDS_RMA.dbo.threat_matrices
    UNION ALL SELECT 'Opportunity_Matrices',    COUNT_BIG(*) FROM LH_SDS_RMA.dbo.opportunity_matrices
    UNION ALL SELECT 'Permissions',             COUNT_BIG(*) FROM LH_SDS_RMA.dbo.permissions
    UNION ALL SELECT 'Users',                   COUNT_BIG(*) FROM LH_SDS_RMA.dbo.users
)
SELECT  d1.TableName, d1.DPV1_Rows, d2.DPV2_Rows,
        d2.DPV2_Rows - d1.DPV1_Rows AS Diff,
        CASE WHEN d1.DPV1_Rows IS NULL THEN 'PASTE DPV1 COUNT'
             WHEN d1.DPV1_Rows = d2.DPV2_Rows THEN 'OK' ELSE 'DIFF' END AS [Status]
FROM    dpv1 d1 JOIN dpv2 d2 ON d1.TableName = d2.TableName
ORDER BY [Status] DESC, d1.TableName;


/* ---------------------------------------------------------------------
   5. COLUMN PROFILE GENERATOR (nulls, distinct, min, max per column)
   Step 1: run this block. It returns one SQL text per table.
   Step 2: copy the column "profile_sql" of a table, run it on DPV2
           (this warehouse) and the equivalent on the RMA source or DPV1.
   Step 3: compare the two result sets (same row = same profile).
   Types without min/max (bit, binary, long text) are counted only.
   --------------------------------------------------------------------- */
SELECT  TABLE_NAME,
        STRING_AGG(CAST(
            'SELECT ''' + COLUMN_NAME + ''' AS column_name, COUNT_BIG(*) AS total_rows, '
          + 'COUNT_BIG(' + QUOTENAME(COLUMN_NAME) + ') AS non_null, '
          + 'COUNT_BIG(DISTINCT ' + QUOTENAME(COLUMN_NAME) + ') AS distinct_values, '
          + CASE WHEN DATA_TYPE IN ('bit','varbinary','binary','image','text','ntext','xml')
                 THEN 'NULL AS min_value, NULL AS max_value '
                 ELSE 'CAST(MIN(' + QUOTENAME(COLUMN_NAME) + ') AS varchar(100)) AS min_value, '
                    + 'CAST(MAX(' + QUOTENAME(COLUMN_NAME) + ') AS varchar(100)) AS max_value ' END
          + 'FROM LH_SDS_RMA.' + QUOTENAME(TABLE_SCHEMA) + '.' + QUOTENAME(TABLE_NAME)
        AS varchar(max)), ' UNION ALL ') WITHIN GROUP (ORDER BY ORDINAL_POSITION) AS profile_sql
FROM    LH_SDS_RMA.INFORMATION_SCHEMA.COLUMNS
WHERE   TABLE_SCHEMA = 'dbo'
GROUP BY TABLE_SCHEMA, TABLE_NAME;


/* ---------------------------------------------------------------------
   6. RMA-SPECIFIC CHECKS
   --------------------------------------------------------------------- */

-- 6a. Duplicate Id (full load: expect 0 in every table that has an Id)
SELECT 'Risks' AS TableName, COUNT_BIG(*) - COUNT_BIG(DISTINCT [Id]) AS DuplicateIds FROM LH_SDS_RMA.dbo.risks
UNION ALL SELECT 'Risks_History', COUNT_BIG(*) - COUNT_BIG(DISTINCT [Id]) FROM LH_SDS_RMA.dbo.risks_history
UNION ALL SELECT 'Actions',       COUNT_BIG(*) - COUNT_BIG(DISTINCT [Id]) FROM LH_SDS_RMA.dbo.actions
UNION ALL SELECT 'Users',         COUNT_BIG(*) - COUNT_BIG(DISTINCT [Id]) FROM LH_SDS_RMA.dbo.users;

-- 6b. HTML removal (dbo.RemoveHTML in the extract queries): expect 0 rows with tags left
SELECT 'Risks.Description' AS ColumnName, COUNT_BIG(*) AS RowsWithTags
FROM LH_SDS_RMA.dbo.risks WHERE [Description] LIKE '%<%>%'
UNION ALL SELECT 'Risks.Causes',        COUNT_BIG(*) FROM LH_SDS_RMA.dbo.risks         WHERE [Causes]        LIKE '%<%>%'
UNION ALL SELECT 'Risks.Consequences',  COUNT_BIG(*) FROM LH_SDS_RMA.dbo.risks         WHERE [Consequences]  LIKE '%<%>%'
UNION ALL SELECT 'RisksHistory.Description', COUNT_BIG(*) FROM LH_SDS_RMA.dbo.risks_history WHERE [Description] LIKE '%<%>%'
UNION ALL SELECT 'Actions.Description', COUNT_BIG(*) FROM LH_SDS_RMA.dbo.actions       WHERE [Description]   LIKE '%<%>%'
UNION ALL SELECT 'Actions.Comment',     COUNT_BIG(*) FROM LH_SDS_RMA.dbo.actions       WHERE [Comment]       LIKE '%<%>%';

-- 6c. Users: the extract joins MDM_Mirror_Person for Email (OUTER APPLY, TOP 1).
--     Row count must equal the source Users count (no fan-out); Email filled for most users.
SELECT  COUNT_BIG(*)                                         AS UserRows,
        COUNT_BIG(DISTINCT [Id])                             AS DistinctIds,
        SUM(CASE WHEN [Email] IS NULL THEN 1 ELSE 0 END)     AS UsersWithoutEmail
FROM    LH_SDS_RMA.dbo.users;

-- 6d. Orphan check: risks whose project/register is missing (adjust the keys to your model)
-- SELECT COUNT_BIG(*) FROM LH_SDS_RMA.dbo.risks r
-- LEFT JOIN LH_SDS_RMA.dbo.risk_registers rr ON rr.[Id] = r.[RiskRegisterId]
-- WHERE rr.[Id] IS NULL;


/* =====================================================================
   B1. DPV1 COUNTS: run on DPV1, paste the result into block 4
   ---------------------------------------------------------------------
   Option A, the RMA source SQL Server (source of truth, same SELECT * tables):
       SELECT 'Actions' AS TableName, COUNT_BIG(*) FROM dbo.Actions
       UNION ALL SELECT 'Business_Units', COUNT_BIG(*) FROM dbo.Business_Units
       ... one line per table ...
   Option B, DPV1 cleansed zone through Synapse serverless:
       SELECT 'Actions', COUNT_BIG(*)
       FROM OPENROWSET(BULK 'https://<account>.dfs.core.windows.net/<container>/<RMA path>/Actions/*/*.parquet',
                       FORMAT = 'PARQUET') AS r
   Compare the DPV1 count with the source at the same moment: if the source
   changed between the DPV1 run and the DPV2 run, small differences are normal.
   ===================================================================== */
