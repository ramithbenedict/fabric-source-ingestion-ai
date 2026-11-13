# Ingestion design: four load methods, built from how DPV1 works

Status: approved (2026-10-26), folder layout revised the same day. Implemented in `0-shared/scripts/ingestion.py` and `skill-ingestion` (one section per method) and `skill-raw-to-lakehouse`.

## 1. What DPV1 does today (measured on the 53 source datasets)

| Step | DPV1 | Cost |
| --- | --- | --- |
| Table list | Lookup on the catalog (`CATALOG.<SRC>` in the metabase) | small |
| Extract | ADF Copy per table, ForEach: database => parquet in `RAW/DATASOURCE=<SRC>/…`; API / SFTP / HTTP => JSON, CSV, Excel files as delivered | the real work |
| Bookkeeping | SetVariable / AppendVariable per table (success lists), WebActivity "is there data?", Delete "clear landing folder" | many small activities per table |
| RAW => CLEANSED | `NTBK_COMMON_MASTER_RAW_TO_CLEAN` loops over tables in 16 threads; for **each table** it runs a child notebook (`mssparkutils.notebook.run`) and then `NTBK_COMMON_CHILD_META_RAW_TO_CLEAN` | 2 notebook starts per table |
| Child logic | full: read parquet, clamp dates before 1900, add `LOADING_DATE`, overwrite Delta · incremental: same, then `MERGE` on keys (`pks` / `UnicityKeys`), newest date wins, delete logs · JSON: explode the root array (e.g. `result`), flatten structs, cut long strings, keep the latest row per key, `MERGE` | Spark |
| META step | drop and re-create the lake database table on the Delta folder, `REFRESH TABLE` | not needed in Fabric |
| Watermark | stored procedure `SP_COMMON_UpdateWatermark` after the run | small |
| Data flows | ECOSYS, SYMPHONY, ILEARN and a few others cleanse with Mapping Data Flows instead of notebooks | Spark cluster per flow |

Notebooks exist for almost every source (`NTBK_<SRC>_CHILD_FULL_RAW_TO_CLEAN` on 20 sources, `NTBK_COMMON_*` on 30); a few sources use only Copy and Data Flows.

## 2. The new design in one picture

```
PL_<SRC>_MASTER_ORCHESTRATOR
 ├─ PL_<SRC>_SOURCE_TO_RAW            Lookup catalog view (+ watermark) ──► ForEach table (batchCount 20)
 │     structured        Copy ──► Files/raw/<src>/<table>/                              parquet, written once, overwritten each run
 │                                 (Files/raw/<src>/<table>/<yyyy>/<mm>/<dd>/<HHhMM>/ only when DPV1 raw had a date tree)
 │     semi-structured   Copy ──► Files/landing/<src>/<yyyy>/<mm>/<dd>/<HHhMM>/           every table of the run, as delivered (json, csv, xml, xlsx)
 │     each Copy         succeeded ──► LoadedTables      failed ──► FailedTables (table and error); returned to the master
 ├─ PL_<SRC>_RAW_TO_DELTA             no Lookup: gets LoadedTables, so only the tables that copied are loaded
 │     NB_<SRC>_FLATTEN               semi-structured only: landing ──► explode, flatten ──► Files/raw/<src>/<yyyy>/<mm>/<dd>/<HHhMM>/<table>/
 │     NB_<SRC>_RAW_TO_DELTA          one Spark session, tables in a thread pool: raw ──► clean ──► dbo.<table> (overwrite or MERGE)
 │                                    a failed table is reported (exit value loaded / failed), the others still load
 ├─ Update watermarks                  only the incremental tables in the returned LoadedTables (Script on the watermark table)
 └─ Any table failed                   Fail with every failed table of both steps and its error
```

Only **one** loader notebook per source (plus `NB_<SRC>_FLATTEN` for semi-structured sources), and only for sources that had a notebook in DPV1. Sources that DPV1 cleansed with a Data Flow or not at all get no notebook (see 4.5).

## 2b. Folder rules
| Source | Landing | Raw | Why |
| --- | --- | --- | --- |
| Structured, full | none | `Files/raw/<src>/<table>/`, one parquet file per table, overwritten | the table is replaced at each run: a date tree only adds folders |
| Structured, DPV1 raw had a date tree (EASYTENDER) | none | `Files/raw/<src>/<table>/<yyyy>/<mm>/<dd>/<HHhMM>/[HISTORY\|DELETE_LOGS]` | keep the DPV1 organisation |
| Semi-structured | `Files/landing/<src>/<yyyy>/<mm>/<dd>/<HHhMM>/` (all tables of the run) | `Files/raw/<src>/<yyyy>/<mm>/<dd>/<HHhMM>/<table>/` | files arrive per run; the run folder is the unit of replay |

The table folder is the table name; the schema is added only when two schemas of the source have a table with the same name. The date tree is decided by `scope_tree.layout()` from the DPV1 code of the source.

## 3. Why it is faster and simpler than DPV1

| DPV1 | Fabric | Gain |
| --- | --- | --- |
| 2 notebook starts per table (child + META) | 1 notebook per source, tables in threads of one session | removes per-table start-up (tens of seconds each) |
| META notebook re-registers every table | `saveAsTable` / `MERGE` on Lakehouse managed tables | step removed |
| Database extract written to RAW, then read again | Copy writes parquet straight to `Files/raw` | one write per table (no landing copy for databases) |
| JSON: one pass to history parquet, another to CLEANSED | `NB_<SRC>_FLATTEN` writes raw parquet once; the loader reads that parquet (column pruning, no JSON parsing) | JSON parsed once per run |
| Success lists with AppendVariable, "data present?" WebActivity, "clear landing" Delete | the success list is kept (`LoadedTables`, plus `FailedTables`): only copied tables are loaded; run folders make cleanup unnecessary (retention handled once by a weekly job) | ~3 activities fewer per table |
| Spark 3.x on Synapse pools, `%%configure` per notebook | Fabric runtime with Native Execution Engine, V-Order and optimized write on by default, starter pool, high-concurrency session tag shared by the run | faster parquet and Delta I/O, no cluster wait |
| Dedicated pool `COPY INTO` downstream | data products read the Lakehouse tables through shortcuts | no copy |

## 4. The four load methods

The catalog row of each table chooses the method: `format` (table, json, csv, xml, excel, parquet) and `load` (full, incremental). DPV1 columns map directly: `isFullLoad`, `UnicityKeys`/`pks`, `WatermarkParam`, `isDeleteLog`, `TargetTable`.

### 4.1 Structured full (database table, full extract)
- Pipeline: Copy `table` mode ⇒ parquet in `Files/raw/.../<run>/`.
- Notebook: read parquet ⇒ DPV1 rules of the source (dates before 1900 clamped, `LOADING_DATE`, long strings) ⇒ `overwrite` with `overwriteSchema`.
- Same result as DPV1: the table is replaced at every run.

### 4.2 Structured incremental (database table, watermark)
- Pipeline: Copy with `SELECT * FROM t WHERE <WatermarkParam> > watermark − overlap` (DPV1 used 1 day); delete-log tables the same way.
- Notebook: keep the latest row per key (window on the watermark column) ⇒ `MERGE` on `UnicityKeys`, update only when the source date is newer (DPV1 rule) ⇒ apply delete logs ⇒ history tables in `HISTORY/`.
- First run or `isFullLoad = 1`: overwrite.
- Watermark: updated in `CATALOG.catalog_<src>_watermark` only for tables that loaded.

### 4.3 Semi-structured full (API, SFTP, HTTP, SharePoint files)
- Pipeline: Copy with the source's own options (REST pagination from DPV1, SFTP wildcard) ⇒ files as delivered in `Files/landing/.../<run>/`.
- `NB_<SRC>_FLATTEN`: read with the format options from the catalog (`multiLine`, `rootPath` such as `result`, CSV header and delimiter) ⇒ explode the root array ⇒ flatten structs (`a.b` ⇒ `a_b`, the DPV1 rule) ⇒ write parquet to `Files/raw/.../<run>/<table>/`.
- `NB_<SRC>_RAW_TO_DELTA`: the flattened tables only ⇒ DPV1 cleaning steps ⇒ `overwrite` the table.
- Excel: read with pandas, only for `.xlsx`, as DPV1 did (`NTBK_*_EXCEL_TO_PARQUET`).

### 4.4 Semi-structured incremental (API or files since the watermark)
- Pipeline: the API filter or `modifiedDatetimeStart` = watermark (DPV1: ServiceNow `sys_updated_on`, ILEARN `startTime`).
- Notebook: as 4.3, then keep the latest row per key ⇒ `MERGE` (DPV1 ServiceNow logic) ⇒ watermark update.

### 4.5 Sources without a DPV1 notebook
- Data Flow sources: relational cleansing ⇒ Copy with a Lakehouse table sink when the flow only maps columns; otherwise listed for review (`skill-spark-notebook-to-fabric`: T-SQL or notebook, decided per flow).
- Copy-only sources: Copy straight to a Lakehouse table (no notebook).

## 5. One generic notebook, generated per source

`NB_<SRC>_RAW_TO_DELTA` is short: seven cells (description, parameters, settings, functions, `clean()`, `load_table()`, run). The functions come from `0-shared/templates/raw-to-delta-snippets.py`, each taken from a DPV1 notebook; only those the source needs are copied, and `clean()` has one line per DPV1 cleaning step of the source, naming its legacy notebook. See [skill-raw-to-lakehouse](../../1-skills/skill-raw-to-lakehouse/SKILL.md).

## 6. Changes to the repository (after approval)

| Item | Change |
| --- | --- |
| `skill-ingestion`, `skill-raw-to-lakehouse` | Rewritten for this design; removed from `baseline-sync.json` so the baseline no longer overwrites them |
| `skill-sds-landing-raw-tables` | Points to the four methods; zone rule updated (see decision 1) |
| `build_source_dataset.py`, `build_source_incremental.py` | Merged: `ingestion.py` holds the methods, `build_source_incremental.py` is removed |
| `create_catalog_view.py` | Adds `Format`, `RootPath`, `FileOptions` columns (from DPV1 datasets and pipelines) |
| `review_scope.py` | Checks: notebook exists only where DPV1 had one; one write per table; no per-table notebook call |
| wf-2 stages S2, S3 | Rewritten around the four methods |

## 7. Decisions requested
1. **Database sources write parquet straight to `Files/raw`** (no copy in `Files/landing`), because a database extract is already tabular and writing it twice doubles the cost. Files and API sources keep `Files/landing` (as delivered) and `Files/raw` (parquet).
2. **Data Flow sources**: Copy to a Lakehouse table when the flow only maps columns; any other flow is reviewed one by one.
3. **One notebook per source** replacing the DPV1 master, child and META notebooks.
