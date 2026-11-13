# Gap Review: EPTW (Source dataset)

Last update: 2026-11-05

- **Verdict**: ⚠️ ready with warnings
- **Findings**: 34 checks · ✅ 33 good · ⚠️ 1 warnings · ❌ 0 failures · ⚪ 0 waiting for a stage
- **Coverage**: 41 / 41 DPV1 objects built

Status: ✅ good · ⚠️ warning (does not block) · ❌ failure (blocks deployment, the m-bug-fixer acts on it) · ⚪ waiting for its stage

## What has been validated

| ID | Area | Check | Status | Remark | Fix | File |
| --- | --- | --- | --- | --- | --- | --- |
| R01 | Coverage | DPV1 objects to migrate: 41 | ✅ | 41 built, 0 waiting for their stage, 0 missing after their stage completed |  |  |
| R02 | Coverage | Objects not migrated by rule: 7 | ✅ | Dataset, Linked service, Pipeline (ADLS linked services, datasets, Synapse pools, wrappers) |  |  |
| R03 | Name check | Other DPV1 objects named like EPTW: 24 | ✅ | all are in this scope or in another scope |  |  |
| R04 | Catalog | Watermark table CATALOG.catalog_eptw_watermark | ✅ | incremental source: watermark per table in the warehouse |  |  |
| R05 | Catalog | View [CATALOG].[eptw_catalog] rows = catalog script | ✅ | 26 rows in the view, 26 in the script |  | `3-build/fabric-deployment/DP_SDS_QHSES/WH_CATALOG_COMMON.Warehouse/CATALOG/Views/eptw_catalog.sql` |
| R06 | Variable library | Value sets DEV, UAT, PRD | ✅ | DEV, PRD, UAT |  | `3-build/fabric-deployment/DP_SDS_QHSES/VL_MAIN.VariableLibrary` |
| R07 | Variable library | Every value set overrides every variable | ✅ | 12 variables in each set |  | `3-build/fabric-deployment/DP_SDS_QHSES/VL_MAIN.VariableLibrary` |
| R08 | Variable library | Only locating values (no ADLS, DPV1, batch size or catalog details) | ✅ | EPTW_CATALOG_VIEW_NAME, EPTW_CATALOG_WATERMARK_TABLE_NAME, EPTW_KEYVAULT_CONN_ID, EPTW_LH_CONN_ID, EPTW_LH_NAME, EPTW_REST_SERVICE_CONN_ID, EPTW_REST_SERVICE_CONN_NAME, LH_SDS_EPTW_ID (+ 4 variables of other sources or shared, kept from the shared VL_MAIN and not checked here) |  | `3-build/fabric-deployment/DP_SDS_QHSES/VL_MAIN.VariableLibrary` |
| R09 | Deployment | VL_MAIN DEV values set | ✅ | all set |  | `3-build/fabric-deployment/DP_SDS_QHSES/VL_MAIN.VariableLibrary` |
| R10 | Fabric items | 10 items in Fabric Git format | ✅ | LH_SDS_EPTW, NB_EPTW_FLATTEN, NB_EPTW_LIST_ITEMS, NB_EPTW_RAW_TO_DELTA, PL_EPTW_MASTER_ORCHESTRATOR, PL_EPTW_RAW_TO_DELTA, PL_EPTW_SOURCE_TO_RAW, PL_EPTW_SOURCE_TO_RAW_CHILD_API, VL_MAIN, WH_CATALOG_COMMON |  |  |
| R11 | Hardcoding | 17 built files scanned | ✅ | no GUID, ADLS path, secret or if-chain |  |  |
| R12 | Lineage | 10 VL_MAIN variables referenced by pipelines / notebooks | ✅ | all exist |  |  |
| R13 | Lineage | Every library variable used is declared in its pipeline under its VL_MAIN name | ✅ | expressions, declarations and VL_MAIN agree |  |  |
| R14 | Lineage | 6 pipelines / notebooks called | ✅ | all built |  |  |
| R15 | Lineage | Data products that read this source (DPV1) | ✅ | EASYPIPING (1 DPV1 objects); EPTW (2 DPV1 objects). They will read it through LH_INP_SDS_EPTW; nothing of a data product is built here. |  |  |
| R16 | Lineage | Source dataset contract for data products | ✅ | 26 tables with their DPV1 access paths; consumers: EASYPIPING, EPTW |  | `3-build/build-notes/build-notes.md (hand-over)` |
| R17 | Deployment | Pipelines deploy in one Git sync (no item ids or deploy tokens in the files) | ✅ | 4 pipelines: connections resolved at run time from VL_MAIN |  |  |
| R18 | Framing | Key reference questions answered | ✅ | every required question has an answer (1-framing/04-key-reference-questions.md) |  |  |
| R19 | Service rules | No shortcut in a source dataset | ✅ | data is ingested from the source |  |  |
| R20 | Service rules | ADLS linked services and datasets not migrated | ✅ | dropped by rule: OneLake is built into the Lakehouse; datasets do not exist in Fabric |  |  |
| R21 | Ingestion | Incremental REST: the request carries the watermark | ✅ | relativeUrl uses item().WatermarkNow (DPV1 request: PL_RAWDATA_EPTW) |  |  |
| R22 | Ingestion | Notebook only where DPV1 had one, one loader per source | ✅ | 2 notebook(s) (1 FLATTEN); DPV1 had 6 |  | `3-build/fabric-deployment/DP_SDS_QHSES/EPTW/2-RAW_TO_DELTA/NB_EPTW_FLATTEN.Notebook/notebook-content.py` |
| R23 | Ingestion | NB_<SRC>_FLATTEN only for semi-structured sources | ✅ | semi-structured: 1 FLATTEN notebook(s) |  | `3-build/fabric-deployment/DP_SDS_QHSES/EPTW/2-RAW_TO_DELTA/NB_EPTW_FLATTEN.Notebook/notebook-content.py` |
| R24 | Ingestion | Loader reads only the tables that copied, from Files/raw | ✅ | tables_json from LoadedTables, raw parquet only |  |  |
| R25 | Ingestion | S2 lists copied and failed tables and returns them | ✅ | LoadedTables / FailedTables returned |  |  |
| R26 | Ingestion | S3 loads only LoadedTables (no catalog Lookup) and returns loaded / failed | ✅ | parameter LoadedTables, return value set |  |  |
| R27 | Ingestion | Master passes LoadedTables and fails with the failed tables | ✅ | final Fail lists every failed table |  |  |
| R28 | Ingestion | Watermark updated only for the tables loaded in this run | ✅ | loaded list only |  |  |
| R29 | Ingestion | No notebook started per table | ✅ | all tables in one session |  |  |
| R30 | Ingestion | APIs called once per item of a list (DPV1 child pipeline) run once per item | ✅ | child pipeline built for the rows with a ParamName |  |  |
| R31 | Deployment | T-SQL lint on 3 files | ✅ | 0 blocking findings |  |  |
| R32 | Deployment | WH_CATALOG_COMMON.sqlproj targets Fabric Warehouse | ✅ | DSP SqlDwUnifiedDatabaseSchemaProvider |  | `3-build/fabric-deployment/DP_SDS_QHSES/WH_CATALOG_COMMON.Warehouse/WH_CATALOG_COMMON.sqlproj` |
| R33 | Deployment | Framing inputs (workspace, deployment repo path) | ✅ | saved in 0_progress_tracking/progress.json |  |  |
| R34 | Deployment | Deployment repo holds the build | ⚠️ | 10 of 27 files new, changed or in conflict | python -I 0-shared/scripts/deploy_publish.py publish --service sds --id EPTW |  |

## What is good

- ✅ DPV1 objects to migrate: 41: 41 built, 0 waiting for their stage, 0 missing after their stage completed
- ✅ Objects not migrated by rule: 7: Dataset, Linked service, Pipeline (ADLS linked services, datasets, Synapse pools, wrappers)
- ✅ Other DPV1 objects named like EPTW: 24: all are in this scope or in another scope
- ✅ Watermark table CATALOG.catalog_eptw_watermark: incremental source: watermark per table in the warehouse
- ✅ View [CATALOG].[eptw_catalog] rows = catalog script: 26 rows in the view, 26 in the script
- ✅ Value sets DEV, UAT, PRD: DEV, PRD, UAT
- ✅ Every value set overrides every variable: 12 variables in each set
- ✅ Only locating values (no ADLS, DPV1, batch size or catalog details): EPTW_CATALOG_VIEW_NAME, EPTW_CATALOG_WATERMARK_TABLE_NAME, EPTW_KEYVAULT_CONN_ID, EPTW_LH_CONN_ID, EPTW_LH_NAME, EPTW_REST_SERVICE_CONN_ID, EPTW_REST_SERVICE_CONN_NAME, LH_SDS_EPTW_ID (+ 4 variables of other sources or shared, kept from the shared VL_MAIN and not checked here)
- ✅ VL_MAIN DEV values set: all set
- ✅ 10 items in Fabric Git format: LH_SDS_EPTW, NB_EPTW_FLATTEN, NB_EPTW_LIST_ITEMS, NB_EPTW_RAW_TO_DELTA, PL_EPTW_MASTER_ORCHESTRATOR, PL_EPTW_RAW_TO_DELTA, PL_EPTW_SOURCE_TO_RAW, PL_EPTW_SOURCE_TO_RAW_CHILD_API, VL_MAIN, WH_CATALOG_COMMON
- ✅ 17 built files scanned: no GUID, ADLS path, secret or if-chain
- ✅ 10 VL_MAIN variables referenced by pipelines / notebooks: all exist
- ✅ Every library variable used is declared in its pipeline under its VL_MAIN name: expressions, declarations and VL_MAIN agree
- ✅ 6 pipelines / notebooks called: all built
- ✅ Data products that read this source (DPV1): EASYPIPING (1 DPV1 objects); EPTW (2 DPV1 objects). They will read it through LH_INP_SDS_EPTW; nothing of a data product is built here.
- ✅ Source dataset contract for data products: 26 tables with their DPV1 access paths; consumers: EASYPIPING, EPTW
- ✅ Pipelines deploy in one Git sync (no item ids or deploy tokens in the files): 4 pipelines: connections resolved at run time from VL_MAIN
- ✅ Key reference questions answered: every required question has an answer (1-framing/04-key-reference-questions.md)
- ✅ No shortcut in a source dataset: data is ingested from the source
- ✅ ADLS linked services and datasets not migrated: dropped by rule: OneLake is built into the Lakehouse; datasets do not exist in Fabric
- ✅ Incremental REST: the request carries the watermark: relativeUrl uses item().WatermarkNow (DPV1 request: PL_RAWDATA_EPTW)
- ✅ Notebook only where DPV1 had one, one loader per source: 2 notebook(s) (1 FLATTEN); DPV1 had 6
- ✅ NB_<SRC>_FLATTEN only for semi-structured sources: semi-structured: 1 FLATTEN notebook(s)
- ✅ Loader reads only the tables that copied, from Files/raw: tables_json from LoadedTables, raw parquet only
- ✅ S2 lists copied and failed tables and returns them: LoadedTables / FailedTables returned
- ✅ S3 loads only LoadedTables (no catalog Lookup) and returns loaded / failed: parameter LoadedTables, return value set
- ✅ Master passes LoadedTables and fails with the failed tables: final Fail lists every failed table
- ✅ Watermark updated only for the tables loaded in this run: loaded list only
- ✅ No notebook started per table: all tables in one session
- ✅ APIs called once per item of a list (DPV1 child pipeline) run once per item: child pipeline built for the rows with a ParamName
- ✅ T-SQL lint on 3 files: 0 blocking findings
- ✅ WH_CATALOG_COMMON.sqlproj targets Fabric Warehouse: DSP SqlDwUnifiedDatabaseSchemaProvider
- ✅ Framing inputs (workspace, deployment repo path): saved in 0_progress_tracking/progress.json

## What is not good

- ⚠️ **Deployment repo holds the build**: 10 of 27 files new, changed or in conflict

## Missing elements

- None

## How to fix

- **R34** Deployment repo holds the build: python -I 0-shared/scripts/deploy_publish.py publish --service sds --id EPTW

Next: run the **m-bug-fixer** on this review, then run the gap review again.
