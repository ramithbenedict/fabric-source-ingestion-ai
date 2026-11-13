# Object Mapping: EPTW

Last update: 2026-11-02

## Summary

| Action | Objects | Meaning |
|---|---|---|
| 🟢 translate | 27 | converted to the Fabric equivalent |
| 🔵 merge | 9 | several objects become one |
| 🔴 drop | 7 | not migrated |
| 🟢 rebuild | 3 | orchestration rebuilt |
| 🟣 replace | 2 | replaced by DACPAC, catalog view or OneLake |

## Objects

| DPV1 type | DPV1 object | Found by | Action | Fabric type | Fabric target | Workspace | Note |
|---|---|---|---|---|---|---|---|
| Pipeline | `PL_CLNDATA_EPTW` | Scope folder: 01_CORE_DATA/05_EPTW | 🔵 merge | 🔗 Pipeline | `2-RAW_TO_DELTA/PL_EPTW_RAW_TO_DELTA` | DP_SDS_QHSES_<ENV> | RAW => Lakehouse tables with history (no cleansed zone) |
| Pipeline | `PL_EPTW_OFFLOAD_SPOT` | Called by: PL_MASTER_EPTW | 🔴 drop | ℹ️ - | - | - | Shared framework, used by several scopes: Copy-back to SPOT_DB not needed: gold views are read in place (SQL endpoint, shortcuts) |
| Pipeline | `PL_MASTER_EPTW` | Entry point: external orchestration folder | 🟢 rebuild | 🔗 Pipeline | `0-ORCHESTRATION/PL_EPTW_MASTER_ORCHESTRATOR` | DP_SDS_QHSES_<ENV> | Rebuilt from the simplified graph |
| Pipeline | `PL_RAWDATA_EPTW` | Scope folder: 01_CORE_DATA/05_EPTW | 🔵 merge | 🔗 Pipeline | `1-SOURCE_TO_RAW/PL_EPTW_SOURCE_TO_RAW` | DP_SDS_QHSES_<ENV> | Source => Files/landing (source format) => Files/raw (parquet) (FULL / INCREMENTAL) |
| Pipeline | `PL_RAWDATA_EPTW_CHILD_API` | Scope folder: 01_CORE_DATA/05_EPTW | 🔵 merge | 🔗 Pipeline | `1-SOURCE_TO_RAW/PL_EPTW_SOURCE_TO_RAW` | DP_SDS_QHSES_<ENV> | Source => Files/landing (source format) => Files/raw (parquet) (FULL / INCREMENTAL) |
| Notebook | `NTBK_COMMON_CHILD_META_RAW_TO_CLEAN` | Scope folder: COMMON | 🔵 merge | 📓 Notebook | `2-RAW_TO_DELTA/NB_EPTW_RAW_TO_DELTA` | DP_SDS_QHSES_<ENV> | Variants merge into one catalog-driven notebook |
| Notebook | `NTBK_COMMON_MASTER_RAW_TO_CLEAN` | Called by: PL_EPTW_OFFLOAD_SPOT | 🔵 merge | 📓 Notebook | `2-RAW_TO_DELTA/NB_EPTW_RAW_TO_DELTA` | DP_SDS_QHSES_<ENV> | Variants merge into one catalog-driven notebook |
| Notebook | `NTBK_EPTW_CHILD_FULL_RAW_TO_CLEAN` | Called by: PL_EPTW_OFFLOAD_SPOT | 🔵 merge | 📓 Notebook | `2-RAW_TO_DELTA/NB_EPTW_RAW_TO_DELTA` | DP_SDS_QHSES_<ENV> | Variants merge into one catalog-driven notebook |
| Notebook | `NTBK_EPTW_CHILD_META_RAW_TO_CLEAN` | Scope folder: EPTW | 🔵 merge | 📓 Notebook | `2-RAW_TO_DELTA/NB_EPTW_RAW_TO_DELTA` | DP_SDS_QHSES_<ENV> | Variants merge into one catalog-driven notebook |
| Notebook | `NTBK_EPTW_CHILD_RAW_TO_CLEANSED` | Called by: PL_CLNDATA_EPTW | 🔵 merge | 📓 Notebook | `2-RAW_TO_DELTA/NB_EPTW_RAW_TO_DELTA` | DP_SDS_QHSES_<ENV> | Variants merge into one catalog-driven notebook |
| Notebook | `NTBK_EPTW_MASTER_RAW_TO_CLEANSED` | Called by: PL_CLNDATA_EPTW | 🔵 merge | 📓 Notebook | `2-RAW_TO_DELTA/NB_EPTW_RAW_TO_DELTA` | DP_SDS_QHSES_<ENV> | Variants merge into one catalog-driven notebook |
| Linked service | `AzureDataLakeStorageRawZone` | Used by: dataset DS_FILE_JSON_RawLayer | 🔴 drop | ℹ️ - | - | DP_SDS_QHSES_<ENV> | ADLS zone of DPV1: OneLake is built into the Lakehouse, no connection needed |
| Linked service | `LS_CORE_REST_EPTW` | Used by: dataset DS_CORE_REST_EPTW_APIM | 🟢 translate | 🔌 Connection | `CONN_EPTW_REST_SERVICE_<ENV> (REST, on-premises data gateway)` | Fabric connections (tenant) | VL_MAIN: EPTW_REST_SERVICE_CONN_ID |
| Linked service | `LS_PROJ_ASQL_METABASE_CATALOG` | Used by: PL_CLNDATA_EPTW | 🟣 replace | ♒ Catalog view | `[CATALOG].[eptw_catalog] in the catalog warehouse` | DP_SDS_QHSES_<ENV> | VL_MAIN: EPTW_CATALOG_VIEW_NAME; warehouse: EPTW_CATALOG_WAREHOUSE_* (CATALOG_WAREHOUSE_* when a common catalog warehouse is chosen in framing) |
| Dataset | `DS_CORE_REST_EPTW_APIM` | Used by: PL_RAWDATA_EPTW | 🔴 drop | ℹ️ - | - | - | Datasets do not exist in Fabric: source / sink settings sit in the activity · RestResource {"value": "@dataset().relativeUrl", "type": "Expr |
| Dataset | `DS_FILE_JSON_RawLayer` | Used by: PL_RAWDATA_EPTW | 🔴 drop | ℹ️ - | - | - | Datasets do not exist in Fabric: source / sink settings sit in the activity · Json {"value": "@dataset().FolderName", "type": "Expression"} |
| Dataset | `DS_GENERIC_ASQL_METABASE_CATALOG` | Used by: PL_EPTW_OFFLOAD_SPOT | 🔴 drop | ℹ️ - | - | - | Datasets do not exist in Fabric: source / sink settings sit in the activity · AzureSqlTable {"value": "@dataset().table", "type": "Expressio |
| Dataset | `rawGenericFolderDataSet` | Used by: PL_RAWDATA_EPTW | 🔴 drop | ℹ️ - | - | - | Datasets do not exist in Fabric: source / sink settings sit in the activity · Parquet {"value": "@dataset().Folder", "type": "Expression"} |
| Dataset | `rawGenericParquetDataSet` | Used by: PL_EPTW_OFFLOAD_SPOT | 🔴 drop | ℹ️ - | - | - | Datasets do not exist in Fabric: source / sink settings sit in the activity · Parquet {"value": "@dataset().DestFolder", "type": "Expression |
| SQL script | `CATALOG_EPTW` | Scope folder: 01_CORE_DATA/05_EPTW | 🟣 replace | ♒ Catalog view | `Catalog warehouse (WH_CATALOG_EPTW, or the common one chosen in framing): [CATALOG].[eptw_catalog] (create_catalog_view.py)` | DP_SDS_QHSES_<ENV> | 37 lines, creates 1 objects; rows and columns carried into the view |
| SQL script | `LOGS_EPTW_INCREMENTAL_LOAD_SP` | Scope folder: 01_CORE_DATA/05_EPTW | 🟢 rebuild | 📂 SQL script | `WH_CATALOG_COMMON: [LOGS].[SP_EPTW_INCREMENTAL_LOAD]` | DP_SDS_QHSES_<ENV> | Owner decision 2026-11-02 (migration owner): Owner keeps the procedure that writes the incremental load log (OPENJSON of the extraction logs into [LOGS].[EPTW_INCREMENTAL_LOAD]). |
| SQL script | `LOGS_EPTW_INCREMENTAL_LOAD_TABLE` | Scope folder: 01_CORE_DATA/05_EPTW | 🟢 rebuild | 📂 SQL script | `WH_CATALOG_COMMON: [LOGS].[EPTW_INCREMENTAL_LOAD]` | DP_SDS_QHSES_<ENV> | Owner decision 2026-11-02 (migration owner): Owner keeps the incremental load log table (process_name, status, start/end time, last_refresh_time, error_message). Lives with the catalog in the common warehouse. |
| Source table | `EPTW.GetPTWProjects_V1` | Catalog table: CATALOG_EPTW | 🟢 translate | ♒ Lakehouse table | `LH_SDS_EPTW: Files/raw (parquet) => dbo.getptwprojects_v1` | DP_SDS_QHSES_<ENV> | incremental, ingested from the source |
| Source table | `EPTW.GetProjectPTW_V1` | Catalog table: CATALOG_EPTW | 🟢 translate | ♒ Lakehouse table | `LH_SDS_EPTW: Files/raw (parquet) => dbo.getprojectptw_v1` | DP_SDS_QHSES_<ENV> | incremental, ingested from the source |
| Source table | `EPTW.GetProjectPTWGeneralPrecautions_V1` | Catalog table: CATALOG_EPTW | 🟢 translate | ♒ Lakehouse table | `LH_SDS_EPTW: Files/raw (parquet) => dbo.getprojectptwgeneralprecautions_v1` | DP_SDS_QHSES_<ENV> | incremental, ingested from the source |
| Source table | `EPTW.GetProjectPTWHazard_V1` | Catalog table: CATALOG_EPTW | 🟢 translate | ♒ Lakehouse table | `LH_SDS_EPTW: Files/raw (parquet) => dbo.getprojectptwhazard_v1` | DP_SDS_QHSES_<ENV> | incremental, ingested from the source |
| Source table | `EPTW.GetProjectPTWTag_V1` | Catalog table: CATALOG_EPTW | 🟢 translate | ♒ Lakehouse table | `LH_SDS_EPTW: Files/raw (parquet) => dbo.getprojectptwtag_v1` | DP_SDS_QHSES_<ENV> | incremental, ingested from the source |
| Source table | `EPTW.GetProjectPTWToolsAndEquipment_V1` | Catalog table: CATALOG_EPTW | 🟢 translate | ♒ Lakehouse table | `LH_SDS_EPTW: Files/raw (parquet) => dbo.getprojectptwtoolsandequipment_v1` | DP_SDS_QHSES_<ENV> | incremental, ingested from the source |
| Source table | `EPTW.GetProjectPTWType_V1` | Catalog table: CATALOG_EPTW | 🟢 translate | ♒ Lakehouse table | `LH_SDS_EPTW: Files/raw (parquet) => dbo.getprojectptwtype_v1` | DP_SDS_QHSES_<ENV> | incremental, ingested from the source |
| Source table | `EPTW.GetProjectPTWWorkClass_V1` | Catalog table: CATALOG_EPTW | 🟢 translate | ♒ Lakehouse table | `LH_SDS_EPTW: Files/raw (parquet) => dbo.getprojectptwworkclass_v1` | DP_SDS_QHSES_<ENV> | incremental, ingested from the source |
| Source table | `EPTW.GetProjectPTWWorkSteps_V1` | Catalog table: CATALOG_EPTW | 🟢 translate | ♒ Lakehouse table | `LH_SDS_EPTW: Files/raw (parquet) => dbo.getprojectptwworksteps_v1` | DP_SDS_QHSES_<ENV> | incremental, ingested from the source |
| Source table | `EPTW.GetProjectActivityType_V1` | Catalog table: CATALOG_EPTW | 🟢 translate | ♒ Lakehouse table | `LH_SDS_EPTW: Files/raw (parquet) => dbo.getprojectactivitytype_v1` | DP_SDS_QHSES_<ENV> | incremental, ingested from the source |
| Source table | `EPTW.GetProjectCompany_V1` | Catalog table: CATALOG_EPTW | 🟢 translate | ♒ Lakehouse table | `LH_SDS_EPTW: Files/raw (parquet) => dbo.getprojectcompany_v1` | DP_SDS_QHSES_<ENV> | incremental, ingested from the source |
| Source table | `EPTW.GetProjectContract_V1` | Catalog table: CATALOG_EPTW | 🟢 translate | ♒ Lakehouse table | `LH_SDS_EPTW: Files/raw (parquet) => dbo.getprojectcontract_v1` | DP_SDS_QHSES_<ENV> | incremental, ingested from the source |
| Source table | `EPTW.GetProjectDepartment_V1` | Catalog table: CATALOG_EPTW | 🟢 translate | ♒ Lakehouse table | `LH_SDS_EPTW: Files/raw (parquet) => dbo.getprojectdepartment_v1` | DP_SDS_QHSES_<ENV> | incremental, ingested from the source |
| Source table | `EPTW.GetProjectDiscipline_V1` | Catalog table: CATALOG_EPTW | 🟢 translate | ♒ Lakehouse table | `LH_SDS_EPTW: Files/raw (parquet) => dbo.getprojectdiscipline_v1` | DP_SDS_QHSES_<ENV> | incremental, ingested from the source |
| Source table | `EPTW.GetProjectFWBS_V1` | Catalog table: CATALOG_EPTW | 🟢 translate | ♒ Lakehouse table | `LH_SDS_EPTW: Files/raw (parquet) => dbo.getprojectfwbs_v1` | DP_SDS_QHSES_<ENV> | incremental, ingested from the source |
| Source table | `EPTW.GetProjectGeneralPrecautions_V1` | Catalog table: CATALOG_EPTW | 🟢 translate | ♒ Lakehouse table | `LH_SDS_EPTW: Files/raw (parquet) => dbo.getprojectgeneralprecautions_v1` | DP_SDS_QHSES_<ENV> | incremental, ingested from the source |
| Source table | `EPTW.GetProjectGWBS_V1` | Catalog table: CATALOG_EPTW | 🟢 translate | ♒ Lakehouse table | `LH_SDS_EPTW: Files/raw (parquet) => dbo.getprojectgwbs_v1` | DP_SDS_QHSES_<ENV> | incremental, ingested from the source |
| Source table | `EPTW.GetProjectHazards_V1` | Catalog table: CATALOG_EPTW | 🟢 translate | ♒ Lakehouse table | `LH_SDS_EPTW: Files/raw (parquet) => dbo.getprojecthazards_v1` | DP_SDS_QHSES_<ENV> | incremental, ingested from the source |
| Source table | `EPTW.GetProjectLocationArea_V1` | Catalog table: CATALOG_EPTW | 🟢 translate | ♒ Lakehouse table | `LH_SDS_EPTW: Files/raw (parquet) => dbo.getprojectlocationarea_v1` | DP_SDS_QHSES_<ENV> | incremental, ingested from the source |
| Source table | `EPTW.GetProjectPhaseOwnership_V1` | Catalog table: CATALOG_EPTW | 🟢 translate | ♒ Lakehouse table | `LH_SDS_EPTW: Files/raw (parquet) => dbo.getprojectphaseownership_v1` | DP_SDS_QHSES_<ENV> | incremental, ingested from the source |
| Source table | `EPTW.GetProjectSupportingDocuments_V1` | Catalog table: CATALOG_EPTW | 🟢 translate | ♒ Lakehouse table | `LH_SDS_EPTW: Files/raw (parquet) => dbo.getprojectsupportingdocuments_v1` | DP_SDS_QHSES_<ENV> | incremental, ingested from the source |
| Source table | `EPTW.GetProjectTag_V1` | Catalog table: CATALOG_EPTW | 🟢 translate | ♒ Lakehouse table | `LH_SDS_EPTW: Files/raw (parquet) => dbo.getprojecttag_v1` | DP_SDS_QHSES_<ENV> | incremental, ingested from the source |
| Source table | `EPTW.GetProjectToolsEquipmentRequired_V1` | Catalog table: CATALOG_EPTW | 🟢 translate | ♒ Lakehouse table | `LH_SDS_EPTW: Files/raw (parquet) => dbo.getprojecttoolsequipmentrequired_v1` | DP_SDS_QHSES_<ENV> | incremental, ingested from the source |
| Source table | `EPTW.GetProjectType_V1` | Catalog table: CATALOG_EPTW | 🟢 translate | ♒ Lakehouse table | `LH_SDS_EPTW: Files/raw (parquet) => dbo.getprojecttype_v1` | DP_SDS_QHSES_<ENV> | incremental, ingested from the source |
| Source table | `EPTW.GetProjectWorkclass_V1` | Catalog table: CATALOG_EPTW | 🟢 translate | ♒ Lakehouse table | `LH_SDS_EPTW: Files/raw (parquet) => dbo.getprojectworkclass_v1` | DP_SDS_QHSES_<ENV> | incremental, ingested from the source |
| Source table | `EPTW.GetUsers_V1` | Catalog table: CATALOG_EPTW | 🟢 translate | ♒ Lakehouse table | `LH_SDS_EPTW: Files/raw (parquet) => dbo.getusers_v1` | DP_SDS_QHSES_<ENV> | incremental, ingested from the source |

