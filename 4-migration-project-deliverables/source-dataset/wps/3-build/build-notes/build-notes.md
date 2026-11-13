# Build notes: WPS

What each build stage generated, what it kept from DPV1 and what changed. Reference tables: `../analysis/build-details.md`. Sections are rewritten when their stage runs again.

[S1-catalog-view](#catalog-view-wps) · [S1-lakehouse](#s1-lakehouse-wps) · [S2-source-to-raw](#s2-source-to-raw-wps-structured-full) · [S3-raw-to-tables](#s3-raw-to-lakehouse-tables-wps) · [S4-orchestration](#s4-orchestration-and-variable-library-wps) · [hand-over](#hand-over-to-data-product-migration-source-dataset-contract-wps)

<!-- note: S1-catalog-view -->
## Catalog view: WPS

- **Warehouse**: `WH_CATALOG_COMMON` in `Platform-Hub_<ENV>` (same_workspace)
- **View**: `[CATALOG].[wps_catalog]`
- **Built from**: DPV1 sqlscript `Catalog_Wps`
- **Rows**: 27 tables, 27 active, 0 incremental, 27 full (script has 27 INSERT rows)
- **Load profile (from the DPV1 pipelines)**: full load

### VL_MAIN variables used by the pipelines

Only the location of the view is in VL_MAIN. Tables, load mode, active flag and watermark stay in the view.

| Variable | Value |
| --- | --- |
| `WPS_CATALOG_VIEW_NAME` | `CATALOG.wps_catalog` |
| `CATALOG_WAREHOUSE_NAME` | `WH_CATALOG_COMMON` |
| `CATALOG_WAREHOUSE_ID` | item ID per environment (DEV / UAT / PRD) |

Columns: 8 DPV1 columns plus the standard columns (list: `../analysis/build-details.md`).

### Standard columns (read by the pipelines and the notebook)

`Active`, `LoadMethod` (full / incremental), `KeyColumns`, `WatermarkColumn`, `WatermarkValue`, `IsDeleteLog`, `DeleteTarget`, `SourceName`, `EntityName` and `FolderTail` (DPV1 folder tree), `TargetName`, `SourceFormat`, `SourcePath`, `FileOptions`, `RootPath`.
Load method: full for every table, as the DPV1 pipelines extract them.
<!-- /note -->
<!-- note: S1-lakehouse -->
## S1 Lakehouse: WPS

- **Item**: `Platform-Hub/WPS/LH_SDS_WPS.Lakehouse` (logicalId `d44747b9-fdbe-4551-85a3-e03315a74fc4`)
- **Schemas**: default schema `dbo` (schemas enabled)
- **Files**: `Files/raw/wps/<table>/[HISTORY|DELETE_LOGS]` (parquet written once by the Copy; one folder per table, overwritten at each run)
- **Shortcuts**: none. The source dataset ingests directly from the source.
- **Replaces (DPV1)**: ADLS RAW and CLEANSED zones `DATASOURCE=WPS_MAIN` and the SPOT_DB source views
<!-- /note -->
<!-- note: S2-source-to-raw -->
## S2 Source to RAW: WPS (structured, full)

- **Item**: `Platform-Hub/WPS/1-SOURCE_TO_RAW/PL_WPS_SOURCE_TO_RAW`
- **Replaces (DPV1)**: `PL_RAWDATA_WPS_TO_ADLS`
- **Source**: Oracle through `LS_CORE_ORACLE_WPS` => Fabric connection `WPS_ORACLE_CONN_ID`

### Activities

1. Set run partition (from the master, so both children use the same folder)
2. Lookup on the catalog view: active rows, watermark per table, `ExtractQuery`
3. ForEach (20 in parallel): one Copy per row => `Files/raw/wps/<table>/[HISTORY|DELETE_LOGS]`; a table that copied goes to `LoadedTables`, one that failed to `FailedTables` (with its error)
4. Return both lists to the master: only `LoadedTables` goes on to the lakehouse; `FailedTables` ends the run with a failure message

### Kept from DPV1

- Table list and load mode from the catalog; watermark minus 1 day for incremental rows; the DPV1 folder tree
### Removed (no effect on the data)

- Copy landing => raw for databases (the extract is written once, as parquet)
- "is there data?" calls and "clear landing" deletes: run folders make them unnecessary (DPV1 success list kept: `LoadedTables`)
<!-- /note -->
<!-- note: S3-raw-to-tables -->
## S3 RAW to Lakehouse tables: WPS

- **Items**: `NB_WPS_RAW_TO_DELTA`, `PL_WPS_RAW_TO_DELTA`
- **Replaces (DPV1)**: `PL_CLNDATA_WPS_TO_ADLS`, `NTBK_COMMON_CHILD_META_RAW_TO_CLEAN`, `NTBK_COMMON_MASTER_RAW_TO_CLEAN`, `NTBK_WPS_CHILD_FULL_RAW_TO_CLEAN`
- **Method**: structured, full (overwrite)
- **Tables**: only those that copied in this run (`LoadedTables` of S2, DPV1 "Append Success Files"); a failed table is reported, the others still load

### Steps

1. `NB_WPS_RAW_TO_DELTA`: raw parquet of the tables that copied => clean => write
3. Return `LoadedTables` and `FailedTables` to the master

### DPV1 cleaning steps (one line each in `clean()`)

| Rule | Value | Meaning | Found in |
| --- | --- | --- | --- |
| `clamp_1900` | True | timestamps before 1900-01-01 set to 1900-01-01 | `NTBK_WPS_CHILD_FULL_RAW_TO_CLEAN` |
| `parquet_vectorized_off` | True | parquet vectorised reader off (DPV1 decimal workaround) | `NTBK_COMMON_MASTER_RAW_TO_CLEAN` |

### Faster than DPV1

- One notebook run per step, tables in a thread pool of one session (DPV1: a child notebook and a META notebook per table)
- No lake database registration: `saveAsTable` / `MERGE` on Lakehouse managed tables
- Row counts from the Delta operation metrics, not a second read
<!-- /note -->
<!-- note: S4-orchestration -->
## S4 Orchestration and variable library: WPS

- **Items**: `Platform-Hub/WPS/0-ORCHESTRATION/PL_WPS_MASTER_ORCHESTRATOR`, and `Platform-Hub/VL_MAIN`
- **Replaces (DPV1)**: `PL_MASTER_WPS`, `PL_WPS`, and the chaining of `PL_CLNDATA_*` inside `PL_RAWDATA_*`

### Run order

0. Set the run folder once; both children get it (`RunPartition`)
1. `PL_WPS_SOURCE_TO_RAW`: catalog view => raw parquet
2. `PL_WPS_RAW_TO_DELTA`: only the tables that copied (`LoadedTables` returned by step 1) => `dbo` tables
3. **Any table failed**: the failed tables of both steps, with their errors, end the run as Failed; the other tables are loaded.
4. A Fail activity names the child that did not run to the end.

### Parallel loads and waiting

- One Spark session per notebook run, whatever the number of tables; the tables run in a thread pool inside it.
- `MaxParallel` (master parameter, default 8): tables loaded at the same time; the others wait in the queue. Start with the Spark pool cores ÷ 4; lower it when the source has a few very large tables, raise it (16–32) for many small ones. Set it per schedule or manual run.
- Automatic: FAIR scheduling (one pool per table thread), largest tables first.
- The master has concurrency 1: a second run of WPS waits until the first has finished. Notebook timeout: `0.04:00:00` (`notebook_timeout` in `shared-platform.json`, or per project in `progress.json` `project_inputs`).
- FLATTEN and the loader share one session (session tag) when *high concurrency for pipelines* is on in the workspace Spark settings: turn it on once.

### Schedule (documented, not activated)

| DPV1 trigger | State in DPV1 | Recurrence | Days | Time | Time zone | Started |
| --- | --- | --- | --- | --- | --- | --- |
| `PL_WPS` | Stopped | Hour every 12 | - | - | Romance Standard Time | `PL_MASTER_WPS` |

- In Fabric: open `PL_WPS_MASTER_ORCHESTRATOR` => Schedule, and enter the same recurrence. Leave it **off** until the data phase and the cut-over are agreed.
- The DPV1 trigger also started pipelines that are dropped (owner decisions); the Fabric schedule starts only the master orchestrator.

### VL_MAIN shared by the workspace

- `Platform-Hub/VL_MAIN` is one item for every source of the workspace. Names that differ per source carry it (`WPS_CATALOG_VIEW_NAME`, `WPS_LH_CONN_ID`…), and each pipeline declares them under the same name.
- Also holds 6 variables of other sources or of earlier builds, kept and not used by WPS: `LH_SDS_RMA_ID`, `RMA_CATALOG_VIEW_NAME`, `RMA_LH_CONN_ID`, `RMA_LH_NAME`, `RMA_SQL_SERVER_CONN_ID`, `RMA_SQL_SERVER_CONN_NAME`.
- Remove a name only when no deployed pipeline uses it any more (for example the unprefixed `CATALOG_*` names once every source is republished).

### Connections

- `connections.md` (next to this page): each Fabric connection to create, its name per environment, type, gateway, DPV1 values, secret and VL_MAIN variable.

### Alerts instead of mail wrappers

- On `PL_WPS_MASTER_ORCHESTRATOR`: add an Activator job alert for **Failed** (and **Succeeded** if the owner wants it), sent to the source owner.
- Use workspace monitoring for run history. No DPV1 mail or log child pipeline is migrated.

### Hand-over to Data Product Migration

- `source-dataset-contract.json` / `.md` (project root) lists the Lakehouse, every table with its DPV1 access paths, the VL_MAIN names and the data products that read WPS.
- Data Product Migration reads it to build its input Lakehouse (`build_input_lakehouse.py`) and to re-point T-SQL (D2).
<!-- /note -->
<!-- note: hand-over -->
## Hand-over to Data Product Migration (source dataset contract): WPS

What Data Product Migration reuses from this source. Generated by `source_contract.py`; do not edit.

- **Lakehouse**: `Platform-Hub_<ENV>` / `WPS` / `LH_SDS_WPS` (schema `dbo`)
- **Ready for data products**: ✅ yes (S1 completed, S2 completed, S3 completed, S4 completed, S5 not_started)
- **In a data product**: input Lakehouse `LH_INP_SDS_WPS` with one OneLake shortcut per table used; VL_MAIN of the product holds `LH_SDS_WPS_ID`, `LH_SDS_WPS_WORKSPACE_ID`, `LH_INP_SDS_WPS_ID`

- **Tables**: 27 · **Data products that read it in DPV1**: none
- Tables with their DPV1 access paths, and the evidence per data product: `../analysis/build-details.md` (hand-over); machine-readable: `source-dataset-contract.json`.
<!-- /note -->
