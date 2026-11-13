# Build notes: EPTW

What each build stage generated and what changed. Long reference tables, when a stage writes them: `../analysis/build-details.md`. Sections are rewritten when their stage runs again.

[S1-catalog-view](#catalog-view-eptw) · [S1-lakehouse](#s1-lakehouse-eptw) · [S2-source-to-raw](#s2-source-to-raw-eptw-semi-structured-incremental) · [S3-raw-to-tables](#s3-raw-to-lakehouse-tables-eptw) · [S4-orchestration](#s4-orchestration-and-variable-library-eptw) · [hand-over](#hand-over-to-data-product-migration-source-dataset-contract-eptw)

<!-- note: S1-catalog-view -->
## Catalog view: EPTW

- **Warehouse**: `WH_CATALOG_COMMON` in `DP_SDS_QHSES_<ENV>` (same_workspace)
- **View**: `[CATALOG].[eptw_catalog]`
- **Built from**: DPV1 sqlscript `CATALOG_EPTW`
- **Rows**: 26 tables, 26 active, 0 incremental, 26 full (script has 26 INSERT rows)
- **Load profile (from the DPV1 pipelines)**: incremental, watermark per table
- **Watermark table**: `[CATALOG].[catalog_eptw_watermark]` (read with the view, updated after each successful run; replaces `SP_COMMON_UpdateWatermark`)

### VL_MAIN variables used by the pipelines

Only the location of the view is in VL_MAIN. Tables, load mode, active flag and watermark stay in the view.

| Variable | Value |
| --- | --- |
| `EPTW_CATALOG_VIEW_NAME` | `CATALOG.eptw_catalog` |
| `EPTW_CATALOG_WATERMARK_TABLE_NAME` | `CATALOG.catalog_eptw_watermark` |
| `CATALOG_WAREHOUSE_NAME` | `WH_CATALOG_COMMON` |
| `CATALOG_WAREHOUSE_ID` | item ID per environment (DEV / UAT / PRD) |

Columns: 5 DPV1 columns plus the standard columns (list: `../analysis/build-details.md`).

### Standard columns (read by the pipelines and the notebook)

`Active`, `LoadMethod` (full / incremental), `KeyColumns`, `WatermarkColumn`, `WatermarkValue`, `IsDeleteLog`, `DeleteTarget`, `SourceName`, `EntityName` and `FolderTail` (DPV1 folder tree), `TargetName`, `SourceFormat`, `SourcePath`, `FileOptions`, `RootPath`.
Load method: from the DPV1 catalog flags.
<!-- /note -->
<!-- note: S1-lakehouse -->
## S1 Lakehouse: EPTW

- **Item**: `DP_SDS_QHSES/EPTW/LH_SDS_EPTW.Lakehouse` (logicalId `ac80f0c2-0136-5c03-9ac7-38d1694e7c8f`)
- **Schemas**: default schema `dbo` (schemas enabled)
- **Files**: `Files/landing/eptw/<yyyy>/<mm>/<dd>/<HHhMM>/` (all tables as delivered) and `Files/raw/eptw/<yyyy>/<mm>/<dd>/<HHhMM>/<table>/` (parquet)
- **Shortcuts**: none. The source dataset ingests directly from the source.
- **Replaces (DPV1)**: ADLS RAW and CLEANSED zones `DATASOURCE=EPTW_MAIN` and the SPOT_DB source views
<!-- /note -->
<!-- note: S2-source-to-raw -->
## S2 Source to RAW: EPTW (semi-structured, incremental)

- **Item**: `DP_SDS_QHSES/EPTW/1-SOURCE_TO_RAW/PL_EPTW_SOURCE_TO_RAW`
- **Replaces (DPV1)**: `PL_RAWDATA_EPTW`, `PL_RAWDATA_EPTW_CHILD_API`
- **Source**: RestService through `LS_CORE_REST_EPTW` => Fabric connection `EPTW_REST_SERVICE_CONN_ID`

### Activities

1. Set run partition (from the master, so both children use the same folder)
2. Lookup on the catalog view: active rows, `Since`
3. ForEach (20 in parallel): one Copy per row => `Files/landing/eptw/<yyyy>/<mm>/<dd>/<HHhMM>/ (all tables, as delivered)`; a table that copied goes to `LoadedTables`, one that failed to `FailedTables` (with its error)
4. Return both lists to the master: only `LoadedTables` goes on to the lakehouse; `FailedTables` ends the run with a failure message

### Kept from DPV1

- Table list and load mode from the catalog; watermark minus 1 day for incremental rows; the DPV1 folder tree
### Removed (no effect on the data)

- Copy landing => raw for databases (the extract is written once, as parquet)
- "is there data?" calls and "clear landing" deletes: run folders make them unnecessary (DPV1 success list kept: `LoadedTables`)

### REST request with the watermark

DPV1 `PL_RAWDATA_EPTW` builds the request in the dataset parameter `relativeUrl`. The Copy uses it as `relativeUrl`, with `item().WatermarkVal` replaced by `item().WatermarkNow` (the live watermark from the watermark table). File: `2-config/migration/request-urls/EPTW.json`.

### Check against DPV1

- API pagination: copied from DPV1 `PL_RAWDATA_EPTW`
- `SourcePath` of each catalog row: the API path or the file wildcard (from the DPV1 catalog or the DPV1 dataset)

### API key header from Key Vault (DPV1 linked service)

The DPV1 linked service `LS_CORE_REST_EPTW` sends `ocp-apim-subscription-key` (Key Vault secret `AZ-REST-EPTW-APIM-SUBKEY`). A Fabric REST connection cannot carry a header, so: a Web activity reads the secret through the Web v2 connection `EPTW_KEYVAULT_CONN_ID` (vault https://az-kv-ne07we-synapseprd.vault.azure.net/, https://az-kv-ne08we-synapse-dev.vault.azure.net/, https://az-kv-ne08we-synapseuat.vault.azure.net/, per environment), and every REST Copy sends it as an additional header. The secret activity has secure input and output: the key is not in the run log or the repository.

### APIs called once per item of a list (DPV1 child pipeline)

DPV1 `PL_RAWDATA_EPTW` gets `GetPTWProjects_V1/` (filter `@greater(length(item().cpInternalCode), 0)`), then runs `PL_RAWDATA_EPTW_CHILD_API` for every catalog row that has a `ParamName`: one REST Copy per `cpInternalCode` (50 in parallel). File: `2-config/migration/rest-loops/EPTW.json`.

- `Land list of items` (Copy through the same REST connection, so the API key is in the connection) and `Valid items` (`NB_EPTW_LIST_ITEMS` reads the landed list, same filter) once per run
- `Has a parameter` in the ForEach: rows without a ParamName run the single Copy; rows with one run `PL_EPTW_SOURCE_TO_RAW_CHILD_API`, one Copy per `cpInternalCode`: `@{pipeline().parameters.apiMetadata.ApiName}/?@{pipeline().parameters.apiMetadata.ParamName}=@{item().cpInternalCode}&LastSyncDate=@{pipeline().parameters.apiMetadata.WatermarkNow}`
- The child lands `<EntityName>~<cpInternalCode>.json` in the run folder; `NB_EPTW_FLATTEN` reads `<EntityName>.json` and `<EntityName>~*.json`
- A failed item fails the API (DPV1 INGESTION FAILURE): the API goes to `FailedTables` with the error
- The notebook returns `[{cpInternalCode: …}]`; the child gets it as `projectMetadata`
<!-- /note -->
<!-- note: S3-raw-to-tables -->
## S3 RAW to Lakehouse tables: EPTW

- **Items**: `NB_EPTW_FLATTEN`, `NB_EPTW_RAW_TO_DELTA`, `PL_EPTW_RAW_TO_DELTA`
- **Replaces (DPV1)**: `PL_CLNDATA_EPTW`, `NTBK_COMMON_CHILD_META_RAW_TO_CLEAN`, `NTBK_COMMON_MASTER_RAW_TO_CLEAN`, `NTBK_EPTW_CHILD_FULL_RAW_TO_CLEAN`, `NTBK_EPTW_CHILD_META_RAW_TO_CLEAN`, `NTBK_EPTW_CHILD_RAW_TO_CLEANSED`, `NTBK_EPTW_MASTER_RAW_TO_CLEANSED`
- **Method**: semi-structured, incremental (MERGE on KeyColumns, newest WatermarkColumn wins, delete logs)
- **Tables**: only those that copied in this run (`LoadedTables` of S2, DPV1 "Append Success Files"); a failed table is reported, the others still load

### Steps

1. `NB_EPTW_FLATTEN`: landing files of the tables that copied => explode => flatten => `Files/raw/eptw/<run>/<table>/`
2. `NB_EPTW_RAW_TO_DELTA`: the tables it flattened => clean => write
3. Return `LoadedTables` and `FailedTables` to the master

### Keys for MERGE

- Incremental rows need `KeyColumns` and `WatermarkColumn` in the catalog; a row without keys is overwritten at every run.
- When DPV1 took the key from the notebook (for example a `sys_id` column), add it to the catalog script.

### DPV1 cleaning steps (one line each in `clean()`)

| Rule | Value | Meaning | Found in |
| --- | --- | --- | --- |
| `clamp_1900` | True | timestamps before 1900-01-01 set to 1900-01-01 | `NTBK_EPTW_CHILD_FULL_RAW_TO_CLEAN` |
| `parquet_vectorized_off` | True | parquet vectorised reader off (DPV1 decimal workaround) | `NTBK_COMMON_MASTER_RAW_TO_CLEAN` |

### Faster than DPV1

- One notebook run per step, tables in a thread pool of one session (DPV1: a child notebook and a META notebook per table)
- No lake database registration: `saveAsTable` / `MERGE` on Lakehouse managed tables
- Row counts from the Delta operation metrics, not a second read
<!-- /note -->
<!-- note: S4-orchestration -->
## S4 Orchestration and variable library: EPTW

- **Items**: `DP_SDS_QHSES/EPTW/0-ORCHESTRATION/PL_EPTW_MASTER_ORCHESTRATOR`, and `DP_SDS_QHSES/VL_MAIN`
- **Replaces (DPV1)**: `PL_MASTER_EPTW`, and the chaining of `PL_CLNDATA_*` inside `PL_RAWDATA_*`

### Run order

0. Set the run folder once; both children get it (`RunPartition`)
1. `PL_EPTW_SOURCE_TO_RAW`: catalog view => landing
2. `PL_EPTW_RAW_TO_DELTA`: only the tables that copied (`LoadedTables` returned by step 1) => `dbo` tables
   - then **Update watermarks**: `EPTW_CATALOG_WATERMARK_TABLE_NAME` = start of this run (CET, as DPV1) for the incremental tables loaded in this run only; replaces `SP_COMMON_UpdateWatermark`
3. **Any table failed**: the failed tables of both steps, with their errors, end the run as Failed; the other tables are loaded.
4. A Fail activity names the child that did not run to the end.

### Parallel loads and waiting

- One Spark session per notebook run, whatever the number of tables; the tables run in a thread pool inside it.
- `MaxParallel` (master parameter, default 8): tables loaded at the same time; the others wait in the queue. Start with the Spark pool cores ÷ 4; lower it when the source has a few very large tables, raise it (16–32) for many small ones. Set it per schedule or manual run.
- The master has concurrency 1: a second run of EPTW waits until the first has finished. Notebook timeout: `0.04:00:00` (`notebook_timeout` in `shared-platform.json`, or per project in `progress.json` `project_inputs`).
- FLATTEN and the loader share one session (session tag) when *high concurrency for pipelines* is on in the workspace Spark settings: turn it on once.

### Schedule (documented, not activated)

| DPV1 trigger | State in DPV1 | Recurrence | Days | Time | Time zone | Started |
| --- | --- | --- | --- | --- | --- | --- |
| none | - | - | - | - | - | - |

- In Fabric: open `PL_EPTW_MASTER_ORCHESTRATOR` => Schedule, and enter the same recurrence. Leave it **off** until the data phase and the cut-over are agreed.
- The DPV1 trigger also started pipelines that are dropped (owner decisions); the Fabric schedule starts only the master orchestrator.

### VL_MAIN shared by the workspace

- `DP_SDS_QHSES/VL_MAIN` is one item for every source of the workspace. Names that differ per source carry it (`EPTW_CATALOG_VIEW_NAME`, `EPTW_LH_CONN_ID`…), and each pipeline declares them under the same name.

### Connections

- `connections.md` (next to this page): each Fabric connection to create, its name per environment, type, gateway, DPV1 values, secret and VL_MAIN variable.

### Alerts instead of mail wrappers

- On `PL_EPTW_MASTER_ORCHESTRATOR`: add an Activator job alert for **Failed** (and **Succeeded** if the owner wants it), sent to the source owner.
- Use workspace monitoring for run history. No DPV1 mail or log child pipeline is migrated.

### Hand-over to Data Product Migration

- `source-dataset-contract.json` / `.md` (project root) lists the Lakehouse, every table with its DPV1 access paths, the VL_MAIN names and the data products that read EPTW.
- Data Product Migration reads it to build its input Lakehouse (`build_input_lakehouse.py`) and to re-point T-SQL (D2).
<!-- /note -->
<!-- note: hand-over -->
## Hand-over to Data Product Migration (source dataset contract): EPTW

What Data Product Migration reuses from this source. Generated by `source_contract.py`; do not edit.

- **Lakehouse**: `DP_SDS_QHSES_<ENV>` / `EPTW` / `LH_SDS_EPTW` (schema `dbo`)
- **Ready for data products**: ✅ yes (S1 completed, S2 completed, S3 completed, S4 completed, S5 completed)
- **In a data product**: input Lakehouse `LH_INP_SDS_EPTW` with one OneLake shortcut per table used; VL_MAIN of the product holds `LH_SDS_EPTW_ID`, `LH_SDS_EPTW_WORKSPACE_ID`, `LH_INP_SDS_EPTW_ID`

- **Tables**: 26 · **Data products that read it in DPV1**: EASYPIPING, EPTW
- Tables with their DPV1 access paths, and the evidence per data product: `../analysis/build-details.md` (hand-over); machine-readable: `source-dataset-contract.json`.
<!-- /note -->
