-- Catalog of source dataset WPS: tables to ingest, load mode, active flag, watermark.
-- Built from DPV1 sqlscript `Catalog_Wps` by create_catalog_view.py. Read by PL_WPS_SOURCE_TO_RAW and PL_WPS_RAW_TO_DELTA through VL_MAIN.
-- DPV1 columns are kept (schema and table renamed SchemaName, TableName); the standard columns follow.
CREATE VIEW [CATALOG].[wps_catalog]
AS
WITH c AS (
    SELECT CAST([schemaName] AS varchar(50)) AS [schemaName], CAST([tableName] AS varchar(200)) AS [tableName], CAST([isIncLoad] AS bit) AS [isIncLoad], CAST([DeltaMode] AS varchar(10)) AS [DeltaMode], CAST([isActive] AS bit) AS [isActive], CAST([watermark] AS datetime2(6)) AS [watermark], CAST([TableProvenance] AS varchar(20)) AS [TableProvenance], CAST([Comment] AS varchar(500)) AS [Comment]
    FROM (VALUES
        ('DWHADMIN', 'TBL_RFOEC_PROJECTS', 0, '', 1, NULL, 'Project', ''),
        ('DWHADMIN', 'TBL_RFCO_OEC', 0, '', 1, NULL, 'Project', ''),
        ('DWHADMIN', 'TBL_RFCO_WORKLOADBS', 0, '', 1, NULL, 'Project', ''),
        ('DWHADMIN', 'TBL_RFCO_PROJECTSCOPE', 0, '', 1, NULL, 'Project', ''),
        ('DWHADMIN', 'TBL_RFOEC_OECBS', 0, '', 1, NULL, 'Project', ''),
        ('DWHADMIN', 'TBL_RFCO_GROUPDBS', 0, '', 1, NULL, 'Project', ''),
        ('DWHADMIN', 'TBL_RFCO_BUSINESS_LINE', 0, '', 1, NULL, 'Project', ''),
        ('DWHADMIN', 'TBL_RFCO_TECHNOLOGYFIELD', 0, '', 1, NULL, 'Project', ''),
        ('DWHADMIN', 'TBL_RFCO_SUBBUSINESS_LINE', 0, '', 1, NULL, 'Project', ''),
        ('DWHADMIN', 'TBL_RFCO_SIMPL_PROJECTSCOPE', 0, '', 1, NULL, 'Project', ''),
        ('DWHADMIN', 'TBL_RFCO_SIMPL_GROUPDBS', 0, '', 1, NULL, 'Project', ''),
        ('DWHADMIN', 'TBL_RFCO_REGIONS', 0, '', 1, NULL, 'Project', ''),
        ('DWHADMIN', 'TBL_RFCO_BILLINGTYPE', 0, '', 1, NULL, 'Project', ''),
        ('DWHADMIN', 'TBL_RFCO_ENERGYTRANSITIONPILAR', 0, '', 1, NULL, 'Project', ''),
        ('DWHADMIN', 'TBL_RFCO_PROJECT_STATUS', 0, '', 1, NULL, 'Project', ''),
        ('DWHADMIN', 'TBL_RFCO_PROBABILITYOFAWARD', 0, '', 1, NULL, 'Project', ''),
        ('DWHADMIN', 'TBL_RFCO_GROUPSEGMENT', 0, '', 1, NULL, 'Project', ''),
        ('DWHADMIN', 'TBL_RFCO_WORKSHARING', 0, '', 1, NULL, 'Project', ''),
        ('DWHADMIN', 'TBL_RFCO_WORKSHARING_OECHOURS', 0, '', 1, NULL, 'Project', ''),
        ('DWHADMIN', 'TBL_AUTH_ROLE', 0, '', 1, NULL, 'Project', ''),
        ('DWHADMIN', 'TBL_AUTH_USER', 0, '', 1, NULL, 'Project', ''),
        ('DWHADMIN', 'TBL_AUTH_USERPROFILE', 0, '', 1, NULL, 'Project', ''),
        ('DWHADMIN', 'DP_DETAILEDRESOURCE', 0, '', 1, NULL, 'Project', ''),
        ('DWHADMIN', 'DP_SUMMARYRESOURCE', 0, '', 1, NULL, 'Project', ''),
        ('DWHADMIN', 'DP_DETAILEDWORKLOAD', 0, '', 1, NULL, 'Project', ''),
        ('DWHADMIN', 'DP_SUMMARYWORKLOAD', 0, '', 1, NULL, 'Project', ''),
        ('DWHADMIN', 'DP_PROJECTMASTERLIST', 0, '', 1, NULL, 'Project', '')
    ) AS v ([schemaName], [tableName], [isIncLoad], [DeltaMode], [isActive], [watermark], [TableProvenance], [Comment])
)
SELECT
    c.[schemaName] AS [SchemaName],
    c.[tableName] AS [TableName],
    c.[isIncLoad],
    c.[DeltaMode],
    c.[isActive],
    c.[watermark],
    c.[TableProvenance],
    c.[Comment],
    -- standard columns read by the pipelines and the notebook (ingestion.py)
    CAST(c.[isActive] AS int) AS [Active],
    CAST('full' AS varchar(12)) AS [LoadMethod],
    CAST(NULL AS varchar(500)) AS [KeyColumns],
    CAST(NULL AS varchar(128)) AS [WatermarkColumn],
    CAST(c.[watermark] AS varchar(40)) AS [WatermarkValue],
    CAST(0 AS int) AS [IsDeleteLog],
    CAST(CAST(NULL AS varchar(200)) AS varchar(200)) AS [DeleteTarget],
    CAST(c.[tableName] AS varchar(200)) AS [SourceName],
    CAST(LOWER(CASE WHEN CAST(0 AS int) = 1 THEN CAST(NULL AS varchar(200)) WHEN 1 = 0 THEN LEFT(c.[tableName], LEN(c.[tableName]) - 8) ELSE c.[tableName] END) AS varchar(300)) AS [EntityName],
    CAST(CAST('' AS varchar(20)) AS varchar(20)) AS [FolderTail],
    CAST(LOWER(REPLACE(c.[tableName], ' ', '_')) AS varchar(200)) AS [TargetName],
    CAST('table' AS varchar(20)) AS [SourceFormat],
    CAST(c.[tableName] AS varchar(1000)) AS [SourcePath],
    CAST(NULL AS varchar(1000)) AS [FileOptions],
    CAST(NULL AS varchar(200)) AS [RootPath]
FROM c;
