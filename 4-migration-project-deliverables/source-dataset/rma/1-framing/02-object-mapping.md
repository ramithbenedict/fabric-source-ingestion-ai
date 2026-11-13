# Object Mapping: RMA

Last update: 2026-10-27

## Summary

| Action | Objects | Meaning |
|---|---|---|
| 🟢 translate | 19 | converted to the Fabric equivalent |
| 🔵 merge | 5 | several objects become one |
| 🔴 drop | 4 | not migrated |
| 🟣 replace | 2 | replaced by DACPAC, catalog view or OneLake |
| 🟢 rebuild | 1 | orchestration rebuilt |

## Objects

| DPV1 type | DPV1 object | Found by | Action | Fabric type | Fabric target | Workspace | Note |
|---|---|---|---|---|---|---|---|
| Pipeline | `PL_CLNDATA_RMA_TO_ADLS` | Scope folder: 01_CORE_DATA/23_RMA | 🔵 merge | 🔗 Pipeline | `2-RAW_TO_DELTA/PL_RMA_RAW_TO_DELTA` | Platform-Hub | RAW => Lakehouse tables with history (no cleansed zone) |
| Pipeline | `PL_MASTER_RMA` | Entry point: external orchestration folder | 🟢 rebuild | 🔗 Pipeline | `0-ORCHESTRATION/PL_RMA_MASTER_ORCHESTRATOR` | Platform-Hub | Rebuilt from the simplified graph |
| Pipeline | `PL_RAWDATA_RMA_TO_ADLS` | Entry point: not called by any pipeline | 🔵 merge | 🔗 Pipeline | `1-SOURCE_TO_RAW/PL_RMA_SOURCE_TO_RAW` | Platform-Hub | Source => Files/landing (source format) => Files/raw (parquet) (FULL / INCREMENTAL) |
| Notebook | `NTBK_RMA_CHILD_FULL_RAW_TO_CLEAN` | Called by: PL_CLNDATA_RMA_TO_ADLS | 🔵 merge | 📓 Notebook | `2-RAW_TO_DELTA/NB_RMA_RAW_TO_DELTA` | Platform-Hub | Variants merge into one catalog-driven notebook |
| Notebook | `NTBK_RMA_CHILD_META_RAW_TO_CLEAN` | Scope folder: RMA | 🔵 merge | 📓 Notebook | `2-RAW_TO_DELTA/NB_RMA_RAW_TO_DELTA` | Platform-Hub | Variants merge into one catalog-driven notebook |
| Notebook | `NTBK_RMA_MASTER_RAW_TO_CLEAN` | Called by: PL_CLNDATA_RMA_TO_ADLS | 🔵 merge | 📓 Notebook | `2-RAW_TO_DELTA/NB_RMA_RAW_TO_DELTA` | Platform-Hub | Variants merge into one catalog-driven notebook |
| Linked service | `AzureDataLakeStorageRawZone` | Used by: dataset rawGenericParquetDataSet | 🔴 drop | ℹ️ - | - | Platform-Hub | ADLS zone of DPV1: OneLake is built into the Lakehouse, no connection needed |
| Linked service | `LS_CORE_SQLSERVER_RMA` | Used by: dataset DS_SQLSERVER_RMA | 🟢 translate | 🔌 Connection | `CONN_RMA_SQL_SERVER_<ENV> (SQL Server, on-premises data gateway)` | Fabric connections (tenant) | VL_MAIN: RMA_SQL_SERVER_CONN_ID |
| Linked service | `LS_PROJ_ASQL_METABASE_CATALOG` | Used by: dataset DS_GENERIC_ASQL_METABASE_CATALOG | 🟣 replace | ♒ Catalog view | `[CATALOG].[rma_catalog] in the catalog warehouse` | Platform-Hub | VL_MAIN: RMA_CATALOG_VIEW_NAME, CATALOG_WAREHOUSE_NAME, CATALOG_WAREHOUSE_ID |
| Dataset | `DS_GENERIC_ASQL_METABASE_CATALOG` | Used by: PL_MASTER_RMA | 🔴 drop | ℹ️ - | - | - | Datasets do not exist in Fabric: source / sink settings sit in the activity · AzureSqlTable {"value": "@dataset().table", "type": "Expressio |
| Dataset | `DS_SQLSERVER_RMA` | Used by: PL_MASTER_RMA | 🔴 drop | ℹ️ - | - | - | Datasets do not exist in Fabric: source / sink settings sit in the activity · SqlServerTable  |
| Dataset | `rawGenericParquetDataSet` | Used by: PL_MASTER_RMA | 🔴 drop | ℹ️ - | - | - | Datasets do not exist in Fabric: source / sink settings sit in the activity · Parquet {"value": "@dataset().DestFolder", "type": "Expression |
| SQL script | `Catalog_RMA` | Scope folder: 01_CORE_DATA/23_RMA/01_CATALOG | 🟣 replace | ♒ Catalog view | `WH_CATALOG_COMMON: [CATALOG].[rma_catalog] (create_catalog_view.py)` | Platform-Hub | 39 lines, creates 1 objects; rows and columns carried into the view |
| Source table | `dbo.Actions` | Catalog table: Catalog_RMA | 🟢 translate | ♒ Lakehouse table | `LH_SDS_RMA: Files/raw (parquet) => dbo.actions` | Platform-Hub | full, ingested from the source |
| Source table | `dbo.Business_Units` | Catalog table: Catalog_RMA | 🟢 translate | ♒ Lakehouse table | `LH_SDS_RMA: Files/raw (parquet) => dbo.business_units` | Platform-Hub | full, ingested from the source |
| Source table | `dbo.Global_Business_Units` | Catalog table: Catalog_RMA | 🟢 translate | ♒ Lakehouse table | `LH_SDS_RMA: Files/raw (parquet) => dbo.global_business_units` | Platform-Hub | full, ingested from the source |
| Source table | `dbo.Iso4217_Currencies` | Catalog table: Catalog_RMA | 🟢 translate | ♒ Lakehouse table | `LH_SDS_RMA: Files/raw (parquet) => dbo.iso4217_currencies` | Platform-Hub | full, ingested from the source |
| Source table | `dbo.Lookup_Values` | Catalog table: Catalog_RMA | 🟢 translate | ♒ Lakehouse table | `LH_SDS_RMA: Files/raw (parquet) => dbo.lookup_values` | Platform-Hub | full, ingested from the source |
| Source table | `dbo.Lookup_Types` | Catalog table: Catalog_RMA | 🟢 translate | ♒ Lakehouse table | `LH_SDS_RMA: Files/raw (parquet) => dbo.lookup_types` | Platform-Hub | full, ingested from the source |
| Source table | `dbo.organizational_entities` | Catalog table: Catalog_RMA | 🟢 translate | ♒ Lakehouse table | `LH_SDS_RMA: Files/raw (parquet) => dbo.organizational_entities` | Platform-Hub | full, ingested from the source |
| Source table | `dbo.PreBids` | Catalog table: Catalog_RMA | 🟢 translate | ♒ Lakehouse table | `LH_SDS_RMA: Files/raw (parquet) => dbo.prebids` | Platform-Hub | full, ingested from the source |
| Source table | `dbo.Projects` | Catalog table: Catalog_RMA | 🟢 translate | ♒ Lakehouse table | `LH_SDS_RMA: Files/raw (parquet) => dbo.projects` | Platform-Hub | full, ingested from the source |
| Source table | `dbo.RBS` | Catalog table: Catalog_RMA | 🟢 translate | ♒ Lakehouse table | `LH_SDS_RMA: Files/raw (parquet) => dbo.rbs` | Platform-Hub | full, ingested from the source |
| Source table | `dbo.Risk_Registers` | Catalog table: Catalog_RMA | 🟢 translate | ♒ Lakehouse table | `LH_SDS_RMA: Files/raw (parquet) => dbo.risk_registers` | Platform-Hub | full, ingested from the source |
| Source table | `dbo.Risks` | Catalog table: Catalog_RMA | 🟢 translate | ♒ Lakehouse table | `LH_SDS_RMA: Files/raw (parquet) => dbo.risks` | Platform-Hub | full, ingested from the source |
| Source table | `dbo.Risks_History` | Catalog table: Catalog_RMA | 🟢 translate | ♒ Lakehouse table | `LH_SDS_RMA: Files/raw (parquet) => dbo.risks_history` | Platform-Hub | full, ingested from the source |
| Source table | `dbo.RPETS` | Catalog table: Catalog_RMA | 🟢 translate | ♒ Lakehouse table | `LH_SDS_RMA: Files/raw (parquet) => dbo.rpets` | Platform-Hub | full, ingested from the source |
| Source table | `dbo.Threat_Matrices` | Catalog table: Catalog_RMA | 🟢 translate | ♒ Lakehouse table | `LH_SDS_RMA: Files/raw (parquet) => dbo.threat_matrices` | Platform-Hub | full, ingested from the source |
| Source table | `dbo.Opportunity_Matrices` | Catalog table: Catalog_RMA | 🟢 translate | ♒ Lakehouse table | `LH_SDS_RMA: Files/raw (parquet) => dbo.opportunity_matrices` | Platform-Hub | full, ingested from the source |
| Source table | `dbo.Permissions` | Catalog table: Catalog_RMA | 🟢 translate | ♒ Lakehouse table | `LH_SDS_RMA: Files/raw (parquet) => dbo.permissions` | Platform-Hub | full, ingested from the source |
| Source table | `dbo.Users` | Catalog table: Catalog_RMA | 🟢 translate | ♒ Lakehouse table | `LH_SDS_RMA: Files/raw (parquet) => dbo.users` | Platform-Hub | full, ingested from the source |

