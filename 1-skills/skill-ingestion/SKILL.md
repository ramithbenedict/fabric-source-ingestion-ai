---
name: skill-ingestion
description: How a source dataset is ingested as DPV1 does it, one section per method - database or list (structured) and API or files (semi-structured), each full or incremental. Copy to Files/raw (or Files/landing then a flatten notebook), one notebook to the dbo tables, MERGE and watermark for incremental. Used by wf-2 S2, S3 and S4.
---

# skill-ingestion

Design and reasons: [ingestion-design.md](../../3-workflows/wf-2-migration-source-dataset/ingestion-design.md). Generator: `build_source_dataset.py` (methods in `ingestion.py`). Pick the section from `ingestion.source_kind` (structured / semi-structured) and `catalog-profile.json` (full / incremental).

| Section | Source | Load |
| --- | --- | --- |
| [Database or list, full load](#database-or-list-full-load) | database or list | full |
| [Database, incremental load](#database-incremental-load) | database or list | incremental |
| [API or files, full load](#api-or-files-full-load) | API or files | full |
| [API or files, incremental load](#api-or-files-incremental-load) | API or files | incremental |

## Database or list, full load

### When it applies
- The DPV1 source connection is a database or a SharePoint list (`ingestion.source_kind` = `structured`).
- The DPV1 pipelines extract every table in full: no watermark in their code. The catalog view then sets `LoadMethod = full` for every row, even when the DPV1 catalog has an `isIncLoad` flag that the pipelines ignore (GEOS, JEEVAN, MDM, WPS).

### How DPV1 did it, and what changes
| DPV1 | Fabric |
| --- | --- |
| Lookup `CATALOG.<SRC>` (metabase) | Lookup on `[CATALOG].[<src>_catalog]`: standard columns plus `ExtractQuery` built in T-SQL |
| Switch on `@item().tableName`, one Copy per branch with its own query | no Switch: the queries go to `2-config/migration/extract-queries/<SRC>.json` (S2) and the Lookup returns each row's query as `ExtractQuery` |
| ForEach Copy `SELECT * FROM <schema>.<table>` => ADLS `RAW/DATASOURCE=<SRC>/<SCHEMA>.<TABLE>/` | ForEach (20 in parallel) Copy `@item().ExtractQuery` => **parquet once** in `Files/raw/<src>/<inst>/<entity>/<yyyy>/<mm>/<dd>/<HHhMM>/` |
| AppendVariable success list, Delete of the landing folder | success list kept (`LoadedTables`, plus `FailedTables` with the error): only the tables that copied are loaded; no landing folder to delete |
| `NTBK_COMMON_MASTER_RAW_TO_CLEAN` => per table `NTBK_<SRC>_CHILD_FULL_RAW_TO_CLEAN` + `NTBK_COMMON_CHILD_META_RAW_TO_CLEAN` | one `NB_<SRC>_RAW_TO_DELTA`, all tables in one session ([skill-raw-to-lakehouse](../skill-raw-to-lakehouse/SKILL.md)) |
| overwrite Delta in CLEANSED, dates before 1900 clamped, `LOADING_DATE` | overwrite `dbo.<table>` with the same rules, read from the legacy notebook |

### Items
```
1-SOURCE_TO_RAW/PL_<SRC>_SOURCE_TO_RAW   Set run partition => Lookup catalog => ForEach { Copy "Extract to RAW parquet" => append loaded / failed } => return both lists
2-RAW_TO_DELTA/PL_<SRC>_RAW_TO_DELTA     Notebook NB_<SRC>_RAW_TO_DELTA (tables_json = LoadedTables, run_partition) => return loaded / failed
0-ORCHESTRATION/PL_<SRC>_MASTER_ORCHESTRATOR   Set run partition => SOURCE_TO_RAW => RAW_TO_DELTA (LoadedTables, same RunPartition) => Fail when a table failed
```

### Rules
- The extract query is built in the warehouse (Lookup), not in pipeline expressions: `SELECT * FROM [schema].[SourceName]` (T-SQL), `"SCHEMA"."TABLE"` (Oracle, ANSI). `SourceName` keeps the DPV1 on-the-fly renames.
- The Copy writes parquet with V-Order (`enableVertiParquet`). No second Copy, no landing folder for a database source.
- The run folder is set once by the master and passed to both children (`RunPartition`), so the notebook reads exactly what this run wrote.
- `batchCount` 20 by default; lower it when the source database limits sessions.
- Connections from VL_MAIN (`@pipeline().libraryVariables.<X>_CONN_ID`); Lakehouse and warehouse ids as VL_MAIN expressions, workspace `@pipeline().DataFactory`: one Git sync deploys every item ([deployment-design.md](../../3-workflows/wf-2-migration-source-dataset/deployment-design.md)).

### Performance
- One parquet write per table; the notebook reads it once.
- Tables load in parallel threads of one Spark session: no per-table notebook start.
- Large tables: set `partitionOption` (`DynamicRange` on Oracle / SQL Server with a numeric key) in the Copy; the catalog can carry the column.

### Known issues kept from the baseline
- KI-012: ExecutePipeline `referenceName` = the child's `.platform` logicalId.
- KI-007: `batchCount` at most 50.
- KI-009: every Copy has `datasetSettings` on source and sink.

### Checks (review)
- One Copy per row, writing to `Files/raw`; no Copy reading `Files/landing` for a database source.
- `LoadMethod = full` for every row when the DPV1 pipelines have no watermark.

## Database, incremental load

### When it applies
- Database source (`structured`) whose DPV1 pipelines read a watermark (`WatermarkParam`, `WatermarkVal`, `isFullLoad`): `catalog-profile.json` says `incremental`.
- Per row, `LoadMethod` comes from the DPV1 flags: `isFullLoad = 1` => full, otherwise incremental (or `isIncLoad = 1` => incremental).

### How DPV1 did it, and what changes
| DPV1 | Fabric |
| --- | --- |
| Watermark in the catalog table, updated by `SP_COMMON_UpdateWatermark` | `[CATALOG].[catalog_<src>_watermark]` (a view is read-only), updated by the master after both children succeed |
| IfCondition: full Copy or `WHERE COALESCE(<WatermarkParam>, '2000-01-01') > <watermark - 1 day>` | one Copy running `@item().ExtractQuery`; the Lookup builds full or incremental query per row in T-SQL. A table with a DPV1 per-table query keeps it: `SELECT * FROM (<query>) q WHERE <watermark> > <since>` (the query must return the watermark column, no ORDER BY) |
| Delete-log tables (`isDeleteLog`, `TargetTable`) copied to `<TARGET>/…/DELETE_LOGS` | same rows, same folder tail (`FolderTail`), same Copy |
| `_History` tables in `<TABLE>/…/HISTORY` | same (`EntityName` = base table, `FolderTail` = `/HISTORY`) |
| child notebook: dedupe on `UnicityKeys`, empty => NULL, upper-case columns, MERGE where the source date is newer, delete logs | the same rules in `standardise()` and `load()` of `NB_<SRC>_RAW_TO_DELTA`, all tables in one session |

### Items
Same as the full-load section above, plus:
- `WH_CATALOG_<SOURCE>.Warehouse/CATALOG/Tables/catalog_<src>_watermark.sql`
- `Update watermarks` (Script on the catalog warehouse) in `PL_<SRC>_MASTER_ORCHESTRATOR`, after RAW_TO_DELTA, for the tables in its returned `LoadedTables` only (OPENJSON)
- VL_MAIN `<SRC>_CATALOG_WATERMARK_TABLE_NAME`

### Rules
- Overlap: watermark minus 1 day, as DPV1 (rows read twice are absorbed by the MERGE).
- MERGE on `KeyColumns` with null-safe equality (`<=>`); a matched row is updated only when `WatermarkColumn` is not older; new rows inserted; new columns added (`autoMerge`).
- Before the MERGE, keep one row per key: the newest by `WatermarkColumn` (no duplicate-match error, less data merged).
- First run of a table, or `LoadMethod = full`: overwrite.
- Delete logs: delete target rows whose keys are in the log (and created before `DELETEDDATE` when the log has it).
- The watermark is moved only for the tables loaded in this run: a failed table re-reads the same changes next run (safe).

### Performance
- Only changed rows leave the source; the MERGE touches only matched files (Fabric low-shuffle merge, deletion vectors).
- Run `OPTIMIZE dbo.<table>` weekly for tables merged every day (maintenance job, not in the daily run).

### Known issues kept from the baseline
- KI-INC-001: seed the watermark table before the first incremental run, or let the first run fall back to `WatermarkValue` of the catalog (done by the Lookup).
- KI-INC-002: the watermark update uses the warehouse connection, not the Lakehouse SQL endpoint (read-only).

### Checks (review)
- Watermark table exists; `<SRC>_CATALOG_WATERMARK_TABLE_NAME` in VL_MAIN; the update step depends on RAW_TO_DELTA `Succeeded` and is limited to its `LoadedTables`.
- Every incremental row has `KeyColumns` and `WatermarkColumn`; rows without keys are overwritten (reported).

## API or files, full load

### When it applies
- The DPV1 source connection is an API or a file store (`ingestion.source_kind` = `semi-structured`).
- The format is the one DPV1 stored in its RAW zone (datasets `Json`, `DelimitedText`, `Excel`, `Xml`); `SourceFormat` of a catalog row overrides it.

### How DPV1 did it, and what changes
| DPV1 | Fabric |
| --- | --- |
| WebActivity "is there data?" then Copy `RestSource` with pagination => JSON in `RAW/…/LANDING/` | one Copy `RestSource` with the **same pagination rules** (copied from the DPV1 Copy) => `Files/landing/…/<run>/`; an empty answer is skipped by the notebook |
| Copy `BinarySource` (SFTP wildcard) => ADLS | Copy `BinarySource` with `wildcardFileName = @item().SourcePath` => `Files/landing/…/<run>/` |
| child notebook: read JSON, `explode(result)`, flatten, cut strings, write `LANDING_HISTORY` parquet and CLEANSED Delta | `NB_<SRC>_FLATTEN`: landing => explode `RootPath`, flatten => parquet in `Files/raw/…/<run>/<table>/`; then `NB_<SRC>_RAW_TO_DELTA`: raw => clean => overwrite `dbo.<table>` |
| AppendVariable success list | kept: `LoadedTables` / `FailedTables`; only the tables that copied are flattened and loaded |
| Excel: `NTBK_*_EXCEL_TO_PARQUET` with pandas | the same pandas read, only for `.xlsx` / `.xls` |

### Items
```
1-SOURCE_TO_RAW/PL_<SRC>_SOURCE_TO_RAW   Set run partition => Lookup catalog => ForEach { Copy "Land as delivered" => append loaded / failed } => return both lists
2-RAW_TO_DELTA/PL_<SRC>_RAW_TO_DELTA     NB_<SRC>_FLATTEN (LoadedTables) => NB_<SRC>_RAW_TO_DELTA (flattened tables) => return loaded / failed
```

### Catalog columns used
- `SourcePath`: API relative URL, or the file wildcard (DPV1 `ApiName`, `RelativeUrl`, `RelativePath`, `FilePath`)
- `SourceFormat`: `json`, `csv`, `xml`, `excel`, `parquet`
- `RootPath`: the JSON attribute that holds the records (DPV1 `explode(col("result"))`); empty = the file is the record list
- `FileOptions`: JSON of Spark read options (`{"delimiter": ";"}`, `{"multiLine": "true"}`, `{"rowTag": "item"}`)

### Rules
- Landing keeps exactly what arrived; raw holds the same run as parquet; tables are built from raw (replay = re-run the notebook on a run folder).
- Flatten: `a.b.c` => `a_b_c` (DPV1 rule); arrays other than `RootPath` stay as arrays.
- The cleansing rules of the DPV1 child notebook (string cut, upper-case names…) are lines of `clean()`, built from `0-shared/templates/raw-to-delta-snippets.py`.

### Performance
- One read of the landed files per table; the frame written to raw is the one loaded to the table.
- API: pagination in the Copy (no Until loop of WebActivities); `requestInterval` only when the API throttles.

### Known issues kept from the baseline
- KI-SS-004: an empty API answer is not an error: the notebook reports "no new data".
- KI-SS-005: `RootPath` missing in the answer: the notebook reads the file as is.
- KI-SS-002 / 003: rate limits and auth headers stay in the Fabric connection (gateway or OAuth), never in the pipeline.

### Checks (review)
- Pagination of every REST Copy matches the DPV1 Copy (S2 notes say where it was copied from).
- A notebook exists only when DPV1 had one; otherwise [skill-raw-to-lakehouse](../skill-raw-to-lakehouse/SKILL.md) "no notebook" path.

## API or files, incremental load

### When it applies
- API or file source (`semi-structured`) whose DPV1 pipelines read a watermark (ServiceNow `waterMarkField` / `waterMarkVal`, SFTP `modifiedDatetimeStart = startTime`).

### How DPV1 did it, and what changes
| DPV1 | Fabric |
| --- | --- |
| Script "COMPUTE RANGES" + ForEach range + WebActivity count + Copy per range | one Copy per catalog row; the API filter uses `@item().Since` (watermark minus 1 day, from the Lookup) |
| SFTP Copy with `modifiedDatetimeStart = @pipeline().parameters.startTime` | `modifiedDatetimeStart = @item().Since` for incremental rows |
| notebook: latest row per `sys_id` by `sys_updated_on` (window), MERGE, `LOADING_DATE` | same in `standardise()` (latest per `KeyColumns` by `WatermarkColumn`) and `load()` (MERGE) |
| `UPDATE WATERMARKS` stored procedure after the notebook | `Update watermarks` Script in the master, after RAW_TO_DELTA, for the tables loaded in this run only |

### Rules
- Put the watermark in the API query string through `SourcePath` (for example `…?sysparm_query=sys_updated_on>@{item().Since}`): the catalog row keeps the DPV1 query, `Since` replaces the DPV1 value.
- The newest row per key wins; MERGE on `KeyColumns`, update only when `WatermarkColumn` is not older; new columns added.
- The watermark moves only for the tables that reached the lakehouse in this run; a failed table keeps its watermark and re-reads the same changes next run.

### Performance
- Only changed records leave the API; one landing read; MERGE of the latest row per key only.

### Known issues kept from the baseline
- KI-CP-003: no new data is a success: the watermark still moves to the run start (as DPV1).
- KI-CP-004: the watermark update runs after the whole run, never inside the page loop.

### Checks (review)
- Every incremental row has `KeyColumns` and `WatermarkColumn`.
- The REST Copy or the file filter uses `Since`; the pagination matches DPV1.
