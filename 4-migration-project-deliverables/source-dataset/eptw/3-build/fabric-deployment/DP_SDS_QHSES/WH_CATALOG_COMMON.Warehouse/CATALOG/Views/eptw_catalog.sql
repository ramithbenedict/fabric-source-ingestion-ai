-- Catalog of source dataset EPTW: tables to ingest, load mode, active flag, watermark.
-- Built from DPV1 sqlscript `CATALOG_EPTW` by create_catalog_view.py. Read by PL_EPTW_SOURCE_TO_RAW and PL_EPTW_RAW_TO_DELTA through VL_MAIN.
-- DPV1 columns are kept (schema and table renamed SchemaName, TableName); the standard columns follow.
CREATE VIEW [CATALOG].[eptw_catalog]
AS
WITH c AS (
    SELECT CAST([ApiName] AS varchar(100)) AS [ApiName], CAST([isActive] AS bit) AS [isActive], CAST([ParamName] AS varchar(255)) AS [ParamName], CAST([UnicityKeys] AS varchar(255)) AS [UnicityKeys], CAST([WatermarkVal] AS datetime2(6)) AS [WatermarkVal]
    FROM (VALUES
        ('GetPTWProjects_V1', 1, NULL, ' cpInternalCode', NULL),
        ('GetProjectPTW_V1', 1, 'projectId', 'ptwId', NULL),
        ('GetProjectPTWGeneralPrecautions_V1', 1, 'projectId', 'projectId.generalPrecautionsCode.ptwId', NULL),
        ('GetProjectPTWHazard_V1', 1, 'projectId', 'projectId.hazardCode.ptwId', NULL),
        ('GetProjectPTWTag_V1', 1, 'projectId', 'projectId.tagCode.ptwId', NULL),
        ('GetProjectPTWToolsAndEquipment_V1', 1, 'projectId', 'projectId.toolsAndEquipmentCode.ptwId', NULL),
        ('GetProjectPTWType_V1', 1, 'projectId', 'projectId.typeCode.ptwId', NULL),
        ('GetProjectPTWWorkClass_V1', 1, 'projectId', 'projectId.workClassCode.ptwId', NULL),
        ('GetProjectPTWWorkSteps_V1', 1, 'projectId', 'workStepId.ptwId', NULL),
        ('GetProjectActivityType_V1', 1, 'projectId', 'ProjectId.code', NULL),
        ('GetProjectCompany_V1', 1, 'projectId', 'ProjectId.code', NULL),
        ('GetProjectContract_V1', 1, 'projectId', 'ProjectId.code', NULL),
        ('GetProjectDepartment_V1', 1, 'projectId', 'ProjectId.code', NULL),
        ('GetProjectDiscipline_V1', 1, 'projectId', 'ProjectId.code', NULL),
        ('GetProjectFWBS_V1', 1, 'projectId', 'ProjectId.code', NULL),
        ('GetProjectGeneralPrecautions_V1', 1, 'projectId', 'ProjectId.code', NULL),
        ('GetProjectGWBS_V1', 1, 'projectId', 'ProjectId.code', NULL),
        ('GetProjectHazards_V1', 1, 'projectId', 'ProjectId.code', NULL),
        ('GetProjectLocationArea_V1', 1, 'projectId', 'ProjectId.code', NULL),
        ('GetProjectPhaseOwnership_V1', 1, 'projectId', 'ProjectId.code', NULL),
        ('GetProjectSupportingDocuments_V1', 1, 'projectId', 'ProjectId.code', NULL),
        ('GetProjectTag_V1', 1, 'projectId', 'ProjectId.code', NULL),
        ('GetProjectToolsEquipmentRequired_V1', 1, 'projectId', 'ProjectId.code', NULL),
        ('GetProjectType_V1', 1, 'projectId', 'ProjectId.code', NULL),
        ('GetProjectWorkclass_V1', 1, 'projectId', 'ProjectId.code', NULL),
        ('GetUsers_V1', 1, 'projectId', 'projectId.userId', NULL)
    ) AS v ([ApiName], [isActive], [ParamName], [UnicityKeys], [WatermarkVal])
)
SELECT
    c.[ApiName],
    c.[isActive],
    c.[ParamName],
    c.[UnicityKeys],
    c.[WatermarkVal],
    CAST('eptw' AS varchar(50)) AS [SchemaName],
    CAST(c.[ApiName] AS varchar(200)) AS [TableName],
    -- standard columns read by the pipelines and the notebook (ingestion.py)
    CAST(c.[isActive] AS int) AS [Active],
    CAST('incremental' AS varchar(12)) AS [LoadMethod],
    CAST(c.[UnicityKeys] AS varchar(500)) AS [KeyColumns],
    CAST(NULL AS varchar(128)) AS [WatermarkColumn],
    CAST(c.[WatermarkVal] AS varchar(40)) AS [WatermarkValue],
    CAST(0 AS int) AS [IsDeleteLog],
    CAST(CAST(NULL AS varchar(200)) AS varchar(200)) AS [DeleteTarget],
    CAST(c.[ApiName] AS varchar(200)) AS [SourceName],
    CAST(LOWER(REPLACE(c.[ApiName], ' ', '_')) AS varchar(300)) AS [EntityName],
    CAST(CAST('' AS varchar(20)) AS varchar(20)) AS [FolderTail],
    CAST(LOWER(REPLACE(c.[ApiName], ' ', '_')) AS varchar(200)) AS [TargetName],
    CAST('json' AS varchar(20)) AS [SourceFormat],
    CAST(c.[ApiName] AS varchar(1000)) AS [SourcePath],
    CAST(NULL AS varchar(1000)) AS [FileOptions],
    CAST(NULL AS varchar(200)) AS [RootPath]
FROM c;
