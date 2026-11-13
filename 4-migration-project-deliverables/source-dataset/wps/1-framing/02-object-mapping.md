# Object Mapping: WPS

Last update: 2026-10-28

## Summary

| Action | Objects | Meaning |
|---|---|---|
| 🟢 translate | 29 | converted to the Fabric equivalent |
| 🔵 merge | 5 | several objects become one |
| 🔴 drop | 4 | not migrated |
| 🟣 replace | 3 | replaced by DACPAC, catalog view or OneLake |
| 🟢 rebuild | 1 | orchestration rebuilt |

## Objects

| DPV1 type | DPV1 object | Found by | Action | Fabric type | Fabric target | Workspace | Note |
|---|---|---|---|---|---|---|---|
| Pipeline | `PL_CLNDATA_WPS_TO_ADLS` | Scope folder: 01_CORE_DATA/20_WPS | 🔵 merge | 🔗 Pipeline | `2-RAW_TO_DELTA/PL_WPS_RAW_TO_DELTA` | DP_SDS_DIG_<ENV> | RAW => Lakehouse tables with history (no cleansed zone) |
| Pipeline | `PL_GENERIC_METABASE_CATALOG_CREATION` | Called by: PL_RAWDATA_WPS_TO_ADLS | 🟣 replace | ♒ Catalog view | `Catalog view [CATALOG].[<source>_catalog] built by create_catalog_view.py` | - | Shared framework, used by several scopes: Catalog view [CATALOG].[<source>_catalog] built by create_catalog_view.py |
| Pipeline | `PL_MASTER_WPS` | Entry point: trigger PL_WPS | 🟢 rebuild | 🔗 Pipeline | `0-ORCHESTRATION/PL_WPS_MASTER_ORCHESTRATOR` | DP_SDS_DIG_<ENV> | Rebuilt from the simplified graph |
| Pipeline | `PL_RAWDATA_WPS_TO_ADLS` | Scope folder: 01_CORE_DATA/20_WPS | 🔵 merge | 🔗 Pipeline | `1-SOURCE_TO_RAW/PL_WPS_SOURCE_TO_RAW` | DP_SDS_DIG_<ENV> | Source => Files/landing (source format) => Files/raw (parquet) (FULL / INCREMENTAL) |
| Notebook | `NTBK_COMMON_CHILD_META_RAW_TO_CLEAN` | Scope folder: COMMON | 🔵 merge | 📓 Notebook | `2-RAW_TO_DELTA/NB_WPS_RAW_TO_DELTA` | DP_SDS_DIG_<ENV> | Variants merge into one catalog-driven notebook |
| Notebook | `NTBK_COMMON_MASTER_RAW_TO_CLEAN` | Called by: PL_CLNDATA_WPS_TO_ADLS | 🔵 merge | 📓 Notebook | `2-RAW_TO_DELTA/NB_WPS_RAW_TO_DELTA` | DP_SDS_DIG_<ENV> | Variants merge into one catalog-driven notebook |
| Notebook | `NTBK_WPS_CHILD_FULL_RAW_TO_CLEAN` | Called by: PL_CLNDATA_WPS_TO_ADLS | 🔵 merge | 📓 Notebook | `2-RAW_TO_DELTA/NB_WPS_RAW_TO_DELTA` | DP_SDS_DIG_<ENV> | Variants merge into one catalog-driven notebook |
| Linked service | `AzureDataLakeStorageRawZone` | Used by: dataset rawGenericParquetDataSet | 🔴 drop | ℹ️ - | - | DP_SDS_DIG_<ENV> | ADLS zone of DPV1: OneLake is built into the Lakehouse, no connection needed |
| Linked service | `LS_CORE_ORACLE_WPS` | Used by: dataset DS_CORE_ORACLE_WPS_RAW | 🟢 translate | 🔌 Connection | `CONN_WPS_ORACLE_<ENV> (Oracle database, on-premises data gateway)` | Fabric connections (tenant) | VL_MAIN: WPS_ORACLE_CONN_ID |
| Linked service | `LS_PROJ_ASQL_METABASE_CATALOG` | Used by: PL_GENERIC_METABASE_CATALOG_CREATION | 🟣 replace | ♒ Catalog view | `[CATALOG].[wps_catalog] in the catalog warehouse` | DP_SDS_DIG_<ENV> | VL_MAIN: WPS_CATALOG_VIEW_NAME, CATALOG_WAREHOUSE_NAME, CATALOG_WAREHOUSE_ID |
| Dataset | `DS_CORE_ORACLE_WPS_RAW` | Used by: PL_RAWDATA_WPS_TO_ADLS | 🔴 drop | ℹ️ - | - | - | Datasets do not exist in Fabric: source / sink settings sit in the activity · OracleTable {"value": "@dataset().TableName", "type": "Express |
| Dataset | `DS_GENERIC_ASQL_METABASE_CATALOG` | Used by: PL_RAWDATA_WPS_TO_ADLS | 🔴 drop | ℹ️ - | - | - | Datasets do not exist in Fabric: source / sink settings sit in the activity · AzureSqlTable {"value": "@dataset().table", "type": "Expressio |
| Dataset | `rawGenericParquetDataSet` | Used by: PL_RAWDATA_WPS_TO_ADLS | 🔴 drop | ℹ️ - | - | - | Datasets do not exist in Fabric: source / sink settings sit in the activity · Parquet {"value": "@dataset().DestFolder", "type": "Expression |
| Trigger | `PL_WPS` | Starts: PL_MASTER_WPS | 🟢 translate | 🔗 Schedule | `Schedule on PL_WPS_MASTER_ORCHESTRATOR` | DP_SDS_DIG_<ENV> | ScheduleTrigger · Stopped · Hour every 12 |
| SQL script | `Catalog_Wps` | Scope folder: 01_CORE_DATA/20_WPS/01_CATALOG | 🟣 replace | ♒ Catalog view | `WH_CATALOG_COMMON: [CATALOG].[wps_catalog] (create_catalog_view.py)` | DP_SDS_DIG_<ENV> | 53 lines, creates 1 objects; rows and columns carried into the view |
| Source table | `DWHADMIN.TBL_RFOEC_PROJECTS` | Catalog table: Catalog_Wps | 🟢 translate | ♒ Lakehouse table | `LH_SDS_WPS: Files/raw (parquet) => dbo.tbl_rfoec_projects` | DP_SDS_DIG_<ENV> | full, ingested from the source |
| Source table | `DWHADMIN.TBL_RFCO_OEC` | Catalog table: Catalog_Wps | 🟢 translate | ♒ Lakehouse table | `LH_SDS_WPS: Files/raw (parquet) => dbo.tbl_rfco_oec` | DP_SDS_DIG_<ENV> | full, ingested from the source |
| Source table | `DWHADMIN.TBL_RFCO_WORKLOADBS` | Catalog table: Catalog_Wps | 🟢 translate | ♒ Lakehouse table | `LH_SDS_WPS: Files/raw (parquet) => dbo.tbl_rfco_workloadbs` | DP_SDS_DIG_<ENV> | full, ingested from the source |
| Source table | `DWHADMIN.TBL_RFCO_PROJECTSCOPE` | Catalog table: Catalog_Wps | 🟢 translate | ♒ Lakehouse table | `LH_SDS_WPS: Files/raw (parquet) => dbo.tbl_rfco_projectscope` | DP_SDS_DIG_<ENV> | full, ingested from the source |
| Source table | `DWHADMIN.TBL_RFOEC_OECBS` | Catalog table: Catalog_Wps | 🟢 translate | ♒ Lakehouse table | `LH_SDS_WPS: Files/raw (parquet) => dbo.tbl_rfoec_oecbs` | DP_SDS_DIG_<ENV> | full, ingested from the source |
| Source table | `DWHADMIN.TBL_RFCO_GROUPDBS` | Catalog table: Catalog_Wps | 🟢 translate | ♒ Lakehouse table | `LH_SDS_WPS: Files/raw (parquet) => dbo.tbl_rfco_groupdbs` | DP_SDS_DIG_<ENV> | full, ingested from the source |
| Source table | `DWHADMIN.TBL_RFCO_BUSINESS_LINE` | Catalog table: Catalog_Wps | 🟢 translate | ♒ Lakehouse table | `LH_SDS_WPS: Files/raw (parquet) => dbo.tbl_rfco_business_line` | DP_SDS_DIG_<ENV> | full, ingested from the source |
| Source table | `DWHADMIN.TBL_RFCO_TECHNOLOGYFIELD` | Catalog table: Catalog_Wps | 🟢 translate | ♒ Lakehouse table | `LH_SDS_WPS: Files/raw (parquet) => dbo.tbl_rfco_technologyfield` | DP_SDS_DIG_<ENV> | full, ingested from the source |
| Source table | `DWHADMIN.TBL_RFCO_SUBBUSINESS_LINE` | Catalog table: Catalog_Wps | 🟢 translate | ♒ Lakehouse table | `LH_SDS_WPS: Files/raw (parquet) => dbo.tbl_rfco_subbusiness_line` | DP_SDS_DIG_<ENV> | full, ingested from the source |
| Source table | `DWHADMIN.TBL_RFCO_SIMPL_PROJECTSCOPE` | Catalog table: Catalog_Wps | 🟢 translate | ♒ Lakehouse table | `LH_SDS_WPS: Files/raw (parquet) => dbo.tbl_rfco_simpl_projectscope` | DP_SDS_DIG_<ENV> | full, ingested from the source |
| Source table | `DWHADMIN.TBL_RFCO_SIMPL_GROUPDBS` | Catalog table: Catalog_Wps | 🟢 translate | ♒ Lakehouse table | `LH_SDS_WPS: Files/raw (parquet) => dbo.tbl_rfco_simpl_groupdbs` | DP_SDS_DIG_<ENV> | full, ingested from the source |
| Source table | `DWHADMIN.TBL_RFCO_REGIONS` | Catalog table: Catalog_Wps | 🟢 translate | ♒ Lakehouse table | `LH_SDS_WPS: Files/raw (parquet) => dbo.tbl_rfco_regions` | DP_SDS_DIG_<ENV> | full, ingested from the source |
| Source table | `DWHADMIN.TBL_RFCO_BILLINGTYPE` | Catalog table: Catalog_Wps | 🟢 translate | ♒ Lakehouse table | `LH_SDS_WPS: Files/raw (parquet) => dbo.tbl_rfco_billingtype` | DP_SDS_DIG_<ENV> | full, ingested from the source |
| Source table | `DWHADMIN.TBL_RFCO_ENERGYTRANSITIONPILAR` | Catalog table: Catalog_Wps | 🟢 translate | ♒ Lakehouse table | `LH_SDS_WPS: Files/raw (parquet) => dbo.tbl_rfco_energytransitionpilar` | DP_SDS_DIG_<ENV> | full, ingested from the source |
| Source table | `DWHADMIN.TBL_RFCO_PROJECT_STATUS` | Catalog table: Catalog_Wps | 🟢 translate | ♒ Lakehouse table | `LH_SDS_WPS: Files/raw (parquet) => dbo.tbl_rfco_project_status` | DP_SDS_DIG_<ENV> | full, ingested from the source |
| Source table | `DWHADMIN.TBL_RFCO_PROBABILITYOFAWARD` | Catalog table: Catalog_Wps | 🟢 translate | ♒ Lakehouse table | `LH_SDS_WPS: Files/raw (parquet) => dbo.tbl_rfco_probabilityofaward` | DP_SDS_DIG_<ENV> | full, ingested from the source |
| Source table | `DWHADMIN.TBL_RFCO_GROUPSEGMENT` | Catalog table: Catalog_Wps | 🟢 translate | ♒ Lakehouse table | `LH_SDS_WPS: Files/raw (parquet) => dbo.tbl_rfco_groupsegment` | DP_SDS_DIG_<ENV> | full, ingested from the source |
| Source table | `DWHADMIN.TBL_RFCO_WORKSHARING` | Catalog table: Catalog_Wps | 🟢 translate | ♒ Lakehouse table | `LH_SDS_WPS: Files/raw (parquet) => dbo.tbl_rfco_worksharing` | DP_SDS_DIG_<ENV> | full, ingested from the source |
| Source table | `DWHADMIN.TBL_RFCO_WORKSHARING_OECHOURS` | Catalog table: Catalog_Wps | 🟢 translate | ♒ Lakehouse table | `LH_SDS_WPS: Files/raw (parquet) => dbo.tbl_rfco_worksharing_oechours` | DP_SDS_DIG_<ENV> | full, ingested from the source |
| Source table | `DWHADMIN.TBL_AUTH_ROLE` | Catalog table: Catalog_Wps | 🟢 translate | ♒ Lakehouse table | `LH_SDS_WPS: Files/raw (parquet) => dbo.tbl_auth_role` | DP_SDS_DIG_<ENV> | full, ingested from the source |
| Source table | `DWHADMIN.TBL_AUTH_USER` | Catalog table: Catalog_Wps | 🟢 translate | ♒ Lakehouse table | `LH_SDS_WPS: Files/raw (parquet) => dbo.tbl_auth_user` | DP_SDS_DIG_<ENV> | full, ingested from the source |
| Source table | `DWHADMIN.TBL_AUTH_USERPROFILE` | Catalog table: Catalog_Wps | 🟢 translate | ♒ Lakehouse table | `LH_SDS_WPS: Files/raw (parquet) => dbo.tbl_auth_userprofile` | DP_SDS_DIG_<ENV> | full, ingested from the source |
| Source table | `DWHADMIN.DP_DETAILEDRESOURCE` | Catalog table: Catalog_Wps | 🟢 translate | ♒ Lakehouse table | `LH_SDS_WPS: Files/raw (parquet) => dbo.dp_detailedresource` | DP_SDS_DIG_<ENV> | full, ingested from the source |
| Source table | `DWHADMIN.DP_SUMMARYRESOURCE` | Catalog table: Catalog_Wps | 🟢 translate | ♒ Lakehouse table | `LH_SDS_WPS: Files/raw (parquet) => dbo.dp_summaryresource` | DP_SDS_DIG_<ENV> | full, ingested from the source |
| Source table | `DWHADMIN.DP_DETAILEDWORKLOAD` | Catalog table: Catalog_Wps | 🟢 translate | ♒ Lakehouse table | `LH_SDS_WPS: Files/raw (parquet) => dbo.dp_detailedworkload` | DP_SDS_DIG_<ENV> | full, ingested from the source |
| Source table | `DWHADMIN.DP_SUMMARYWORKLOAD` | Catalog table: Catalog_Wps | 🟢 translate | ♒ Lakehouse table | `LH_SDS_WPS: Files/raw (parquet) => dbo.dp_summaryworkload` | DP_SDS_DIG_<ENV> | full, ingested from the source |
| Source table | `DWHADMIN.DP_PROJECTMASTERLIST` | Catalog table: Catalog_Wps | 🟢 translate | ♒ Lakehouse table | `LH_SDS_WPS: Files/raw (parquet) => dbo.dp_projectmasterlist` | DP_SDS_DIG_<ENV> | full, ingested from the source |

