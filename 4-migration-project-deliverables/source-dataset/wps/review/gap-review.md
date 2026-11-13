# Gap Review: WPS (Source dataset)

Last update: 2026-10-29

- **Verdict**: ⚠️ ready with warnings
- **Findings**: 31 checks · ✅ 29 good · ⚠️ 2 warnings · ❌ 0 failures · ⚪ 0 waiting for a stage
- **Coverage**: 38 / 38 DPV1 objects built

Status: ✅ good · ⚠️ warning (does not block) · ❌ failure (blocks deployment, the m-bug-fixer acts on it) · ⚪ waiting for its stage

## What has been validated

| ID | Area | Check | Status | Remark | Fix | File |
| --- | --- | --- | --- | --- | --- | --- |
| R01 | Coverage | DPV1 objects to migrate: 38 | ✅ | 38 built, 0 waiting for their stage, 0 missing after their stage completed |  |  |
| R02 | Coverage | Objects not migrated by rule: 4 | ✅ | Dataset, Linked service (ADLS linked services, datasets, Synapse pools, wrappers) |  |  |
| R03 | Name check | Other DPV1 objects named like WPS: 0 | ✅ | all are in this scope or in another scope |  |  |
| R04 | Catalog | View [CATALOG].[wps_catalog] rows = catalog script | ✅ | 27 rows in the view, 27 in the script |  | `3-build/fabric-deployment/Platform-Hub/WH_CATALOG_COMMON.Warehouse/CATALOG/Views/wps_catalog.sql` |
| R05 | Variable library | Value sets DEV, UAT, PRD | ✅ | DEV, PRD, UAT |  | `3-build/fabric-deployment/Platform-Hub/VL_MAIN.VariableLibrary` |
| R06 | Variable library | Every value set overrides every variable | ✅ | 16 variables in each set |  | `3-build/fabric-deployment/Platform-Hub/VL_MAIN.VariableLibrary` |
| R07 | Variable library | Only locating values (no ADLS, DPV1, batch size or catalog details) | ✅ | LH_SDS_WPS_ID, WPS_CATALOG_VIEW_NAME, WPS_LH_CONN_ID, WPS_LH_NAME, WPS_ORACLE_CONN_ID, WPS_ORACLE_CONN_NAME (+ 10 variables of other sources or shared, kept from the shared VL_MAIN and not checked here) |  | `3-build/fabric-deployment/Platform-Hub/VL_MAIN.VariableLibrary` |
| R08 | Deployment | VL_MAIN DEV values set | ✅ | all set |  | `3-build/fabric-deployment/Platform-Hub/VL_MAIN.VariableLibrary` |
| R09 | Fabric items | 7 items in Fabric Git format | ✅ | LH_SDS_WPS, NB_WPS_RAW_TO_DELTA, PL_WPS_MASTER_ORCHESTRATOR, PL_WPS_RAW_TO_DELTA, PL_WPS_SOURCE_TO_RAW, VL_MAIN, WH_CATALOG_COMMON |  |  |
| R10 | Hardcoding | 13 built files scanned | ✅ | no GUID, ADLS path, secret or if-chain |  |  |
| R11 | Lineage | 8 VL_MAIN variables referenced by pipelines / notebooks | ✅ | all exist |  |  |
| R12 | Lineage | Every library variable used is declared in its pipeline under its VL_MAIN name | ✅ | expressions, declarations and VL_MAIN agree |  |  |
| R13 | Lineage | 3 pipelines / notebooks called | ✅ | all built |  |  |
| R14 | Lineage | Data products that read this source (DPV1) | ⚠️ | no consumer found in DPV1 | Confirm the source is still used before migrating it. |  |
| R15 | Lineage | Source dataset contract for data products | ✅ | 27 tables with their DPV1 access paths; consumers: none |  | `3-build/build-notes/build-notes.md (hand-over)` |
| R16 | Deployment | Pipelines deploy in one Git sync (no item ids or deploy tokens in the files) | ✅ | 3 pipelines: connections resolved at run time from VL_MAIN |  |  |
| R17 | Service rules | No shortcut in a source dataset | ✅ | data is ingested from the source |  |  |
| R18 | Service rules | ADLS linked services and datasets not migrated | ✅ | dropped by rule: OneLake is built into the Lakehouse; datasets do not exist in Fabric |  |  |
| R19 | Ingestion | Notebook only where DPV1 had one, one loader per source | ✅ | 1 notebook(s) (0 FLATTEN); DPV1 had 3 |  | `3-build/fabric-deployment/Platform-Hub/WPS/2-RAW_TO_DELTA/NB_WPS_RAW_TO_DELTA.Notebook/notebook-content.py` |
| R20 | Ingestion | NB_<SRC>_FLATTEN only for semi-structured sources | ✅ | structured: 0 FLATTEN notebook(s) |  |  |
| R21 | Ingestion | Loader reads only the tables that copied, from Files/raw | ✅ | tables_json from LoadedTables, raw parquet only |  |  |
| R22 | Ingestion | S2 lists copied and failed tables and returns them | ✅ | LoadedTables / FailedTables returned |  |  |
| R23 | Ingestion | S3 loads only LoadedTables (no catalog Lookup) and returns loaded / failed | ✅ | parameter LoadedTables, return value set |  |  |
| R24 | Ingestion | Master passes LoadedTables and fails with the failed tables | ✅ | final Fail lists every failed table |  |  |
| R25 | Ingestion | Watermark updated only for the tables loaded in this run | ✅ | loaded list only |  |  |
| R26 | Ingestion | No notebook started per table | ✅ | all tables in one session |  |  |
| R27 | Ingestion | Database extract written once (straight to Files/raw) | ✅ | one parquet write per table |  | `3-build/fabric-deployment/Platform-Hub/WPS/1-SOURCE_TO_RAW/PL_WPS_SOURCE_TO_RAW.DataPipeline/pipeline-content.json` |
| R28 | Deployment | T-SQL lint on 2 files | ✅ | 0 blocking findings |  |  |
| R29 | Deployment | WH_CATALOG_COMMON.sqlproj targets Fabric Warehouse | ✅ | DSP SqlDwUnifiedDatabaseSchemaProvider |  | `3-build/fabric-deployment/Platform-Hub/WH_CATALOG_COMMON.Warehouse/WH_CATALOG_COMMON.sqlproj` |
| R30 | Deployment | Framing inputs (workspace, deployment repo path) | ✅ | saved in 0_progress_tracking/progress.json |  |  |
| R31 | Deployment | Deployment repo holds the build | ⚠️ | 5 of 20 files new, changed or in conflict | python -I 0-shared/scripts/deploy_publish.py publish --service sds --id WPS |  |

## What is good

- ✅ DPV1 objects to migrate: 38: 38 built, 0 waiting for their stage, 0 missing after their stage completed
- ✅ Objects not migrated by rule: 4: Dataset, Linked service (ADLS linked services, datasets, Synapse pools, wrappers)
- ✅ Other DPV1 objects named like WPS: 0: all are in this scope or in another scope
- ✅ View [CATALOG].[wps_catalog] rows = catalog script: 27 rows in the view, 27 in the script
- ✅ Value sets DEV, UAT, PRD: DEV, PRD, UAT
- ✅ Every value set overrides every variable: 16 variables in each set
- ✅ Only locating values (no ADLS, DPV1, batch size or catalog details): LH_SDS_WPS_ID, WPS_CATALOG_VIEW_NAME, WPS_LH_CONN_ID, WPS_LH_NAME, WPS_ORACLE_CONN_ID, WPS_ORACLE_CONN_NAME (+ 10 variables of other sources or shared, kept from the shared VL_MAIN and not checked here)
- ✅ VL_MAIN DEV values set: all set
- ✅ 7 items in Fabric Git format: LH_SDS_WPS, NB_WPS_RAW_TO_DELTA, PL_WPS_MASTER_ORCHESTRATOR, PL_WPS_RAW_TO_DELTA, PL_WPS_SOURCE_TO_RAW, VL_MAIN, WH_CATALOG_COMMON
- ✅ 13 built files scanned: no GUID, ADLS path, secret or if-chain
- ✅ 8 VL_MAIN variables referenced by pipelines / notebooks: all exist
- ✅ Every library variable used is declared in its pipeline under its VL_MAIN name: expressions, declarations and VL_MAIN agree
- ✅ 3 pipelines / notebooks called: all built
- ✅ Source dataset contract for data products: 27 tables with their DPV1 access paths; consumers: none
- ✅ Pipelines deploy in one Git sync (no item ids or deploy tokens in the files): 3 pipelines: connections resolved at run time from VL_MAIN
- ✅ No shortcut in a source dataset: data is ingested from the source
- ✅ ADLS linked services and datasets not migrated: dropped by rule: OneLake is built into the Lakehouse; datasets do not exist in Fabric
- ✅ Notebook only where DPV1 had one, one loader per source: 1 notebook(s) (0 FLATTEN); DPV1 had 3
- ✅ NB_<SRC>_FLATTEN only for semi-structured sources: structured: 0 FLATTEN notebook(s)
- ✅ Loader reads only the tables that copied, from Files/raw: tables_json from LoadedTables, raw parquet only
- ✅ S2 lists copied and failed tables and returns them: LoadedTables / FailedTables returned
- ✅ S3 loads only LoadedTables (no catalog Lookup) and returns loaded / failed: parameter LoadedTables, return value set
- ✅ Master passes LoadedTables and fails with the failed tables: final Fail lists every failed table
- ✅ Watermark updated only for the tables loaded in this run: loaded list only
- ✅ No notebook started per table: all tables in one session
- ✅ Database extract written once (straight to Files/raw): one parquet write per table
- ✅ T-SQL lint on 2 files: 0 blocking findings
- ✅ WH_CATALOG_COMMON.sqlproj targets Fabric Warehouse: DSP SqlDwUnifiedDatabaseSchemaProvider
- ✅ Framing inputs (workspace, deployment repo path): saved in 0_progress_tracking/progress.json

## What is not good

- ⚠️ **Data products that read this source (DPV1)**: no consumer found in DPV1
- ⚠️ **Deployment repo holds the build**: 5 of 20 files new, changed or in conflict

## Missing elements

- None

## How to fix

- **R14** Data products that read this source (DPV1): Confirm the source is still used before migrating it.
- **R31** Deployment repo holds the build: python -I 0-shared/scripts/deploy_publish.py publish --service sds --id WPS

Next: run the **m-bug-fixer** on this review, then run the gap review again.
