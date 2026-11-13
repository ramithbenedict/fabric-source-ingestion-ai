---
name: skill-raw-to-lakehouse
description: One loader notebook per source (NB_<SRC>_RAW_TO_DELTA) that loads only the tables that copied in this run (LoadedTables of S2) from raw into dbo Delta tables in one Spark session, with the DPV1 cleansing rules; semi-structured sources first run NB_<SRC>_FLATTEN (landing => flattened raw parquet). When DPV1 had no notebook, a Copy from raw parquet to the tables. Used by wf-2 S3.
---

# skill-raw-to-lakehouse

Design: [ingestion-design.md](../../3-workflows/wf-2-migration-source-dataset/ingestion-design.md). Generator: `ingestion.build_s3` (through `build_source_dataset.py --stage S3`).

## Notebook only where DPV1 had one
| DPV1 cleansed the source with | Fabric |
| --- | --- |
| notebooks (master + child + META) | `NB_<SRC>_RAW_TO_DELTA`, one per source; semi-structured sources also get `NB_<SRC>_FLATTEN` |
| a Mapping Data Flow, or nothing | no notebook: ForEach Copy raw parquet => Lakehouse table (overwrite); each Data Flow listed for review ([skill-spark-notebook-to-fabric](../skill-spark-notebook-to-fabric/SKILL.md)) |

## The notebook: short, readable, built from reusable DPV1 code
The generated notebook has seven cells, in reading order:
```
1 description     what it loads, the DPV1 notebooks it replaces, the cleaning steps kept (markdown)
2 parameters      tables_json (the tables that copied), run_partition, raw_root, target_schema, max_parallel
3 settings        DPV1 Spark settings (%%configure of NTBK_COMMON_MASTER_RAW_TO_CLEAN), catalog rows, col(), keys_of()
4 functions       only the functions this source needs, copied from the reusable file (below)
5 clean(df, row)  one line per DPV1 cleaning step, each with the DPV1 notebook it comes from
6 load_table(row) read raw => clean => overwrite (full) or MERGE + delete logs (incremental)
7 run             all tables in parallel, 3 attempts each (DPV1 master notebook); exit value {loaded, failed}: a failed table is reported, never raised
```
Example (GEOS): `clean()` is two lines, `clamp_dates_1900(df)` (DPV1 `NTBK_GEOS_CHILD_FULL_RAW_TO_CLEAN`) and `add_loading_date(df)`.

**Reusable functions** live once in [`0-shared/templates/raw-to-delta-snippets.py`](../../0-shared/templates/raw-to-delta-snippets.py). Each `# --- snippet: <name>` block is one function taken from a DPV1 notebook:

| Snippet | Function | From DPV1 |
| --- | --- | --- |
| `folders` | `has_files`, `latest_run`, `folder_size`, `read_parquet` | folder checks of the child notebooks; sizes to start the largest tables first |
| `read_raw_flat` / `read_raw_dated` | `table_path`, `read_table` | `spark.read.parquet(RAW/...)` of `NTBK_<SRC>_CHILD_FULL_RAW_TO_CLEAN`; flat or date tree as the source |
| `flatten`, `flatten_to_raw` (FLATTEN notebook) | `flatten`, `flatten_to_raw` | `NTBK_SERVICENOW_CHILD_JSON_TO_CLEANSED` first half (read landing, explode, `flatten_json_df`); Excel with pandas |
| `read_raw_run` | `table_path`, `read_table` | the parquet FLATTEN wrote: `Files/raw/<src>/<run>/<table>/` |
| `clamp_1900`, `upper_columns`, `empty_to_null`, `tz_offset_fix`, `string_null_over`, `string_cut`, `dedupe`, `latest_per_key` | one cleaning step each | the child notebook that has it (named in the generated comment) |
| `loading_date` | `add_loading_date` | `LOADING_DATE` of every child notebook |
| `write_overwrite`, `write_merge`, `delete_logs` | `overwrite_table`, `merge_table`, `apply_delete_logs` | `write_delta_table` and `DeltaTable.merge` of the child notebooks |

To change how every source cleans or writes: edit the snippet, then `build_source_dataset.py --id <SOURCE> --stage S3` for each source. A step is added to `clean()` only when the source's legacy notebook has it (`ingestion.legacy_rules`); logic special to one source goes into its `clean()` with a comment naming the legacy notebook.

- Columns added to every table: `LOADING_DATE` (DPV1), `meta_loaded_at` (UTC), `meta_source_file`.
- Write: overwrite (full, or first load) or MERGE (incremental) with delete logs; 90 days of Delta history (DPV1 setting).

## 5 or 100 tables: one session, tables in parallel
One notebook run is one Spark session, whatever the number of tables: no session per table.

| What | How | Set by |
| --- | --- | --- |
| Tables at the same time | thread pool of `max_parallel`; the other tables wait in the queue | `MaxParallel` of the master (default 8), passed to FLATTEN and the loader; per schedule or manual run |
| Big tables do not hold every core | one scheduler pool per table thread (`spark.scheduler.pool`) | automatic; needs `spark.scheduler.mode=FAIR` in the workspace Spark settings (the notebook prints the mode) |
| No big table started last | largest raw folder (FLATTEN: largest delivery) first | automatic (`folder_size`, `landing_files`) |
| Two runs of the same source | the second waits for the first | automatic: master `concurrency` 1 |
| FLATTEN and loader share the session | same `sessionTag` | automatic; needs *high concurrency for pipelines* on in the workspace |
| Long runs | notebook activity timeout | `notebook_timeout` in `shared-platform.json`, or per project in `progress.json` `project_inputs` (build time: Fabric takes no expression there) |

Sizing: start `MaxParallel` at the Spark pool cores ÷ 4. Lower it for a few very large tables, raise it (16–32) for many small ones. More than one pool can give means a bigger pool or capacity, not more sessions. FAIR is not set in `%%configure`, because a pipeline injects its parameters cell first and a later `%%configure` can restart the session.

## Why one notebook is faster than DPV1
- DPV1 started 2 notebooks per table (`mssparkutils.notebook.run` child + META); here one session loads all tables in threads.
- No lake database registration: Lakehouse tables are managed (`saveAsTable`, `MERGE`).
- Row counts come from `DESCRIBE HISTORY` operation metrics, not from a second read.
- Fabric defaults: V-Order and optimized write. For large sources, attach an Environment with the Native Execution Engine; the pipeline uses a session tag per source.
- The parquet vectorised reader stays on unless the DPV1 notebooks switched it off (decimal workaround).

## Pipeline: only the tables that copied
`PL_<SRC>_RAW_TO_DELTA` has no catalog Lookup. Parameter `LoadedTables` (array of catalog rows) comes from `PL_<SRC>_SOURCE_TO_RAW` through the master (DPV1 "Append Success Files").

```
semi-structured   NB_<SRC>_FLATTEN (LoadedTables) => exit {flattened, failed} => NB_<SRC>_RAW_TO_DELTA (flattened) => exit {loaded, failed}
structured        NB_<SRC>_RAW_TO_DELTA (LoadedTables) => exit {loaded, failed}
no DPV1 notebook  ForEach LoadedTables: Copy raw parquet => table, AppendVariable loaded / failed
then              return value LoadedTables, FailedTables ("schema.table (step): error") to the master
```
A table that fails is listed with its error; the other tables still load. The master updates watermarks only for the loaded tables and ends Failed with the list. The master passes `RunPartition`, so the notebooks read only this run's folders; run alone, they take the newest folder.

## Known issues kept from the baseline
- KI-018: the notebook is bound to `LH_SDS_<SRC>` by logicalId (`default_lakehouse`), zero workspace GUID.
- KI-019: notebook parameters are passed as strings (`@string(activity(...).output.value)`).
- KI-016: generate the pipeline after the notebook item exists (the generator writes the notebook first and uses its logicalId).

## Checks (review)
- A notebook exists only when DPV1 had notebooks for the source; `NB_<SRC>_FLATTEN` only for semi-structured sources.
- The loader reads `tables_json` and `Files/raw` only (no catalog, no `Files/landing`); S3 has no Lookup and returns loaded / failed.
- No `notebook.run` / `mssparkutils.notebook.run` in the generated notebook.
- Every line of `clean()` names its legacy notebook (also listed in `3-build/build-notes/build-notes.md#S3-raw-to-tables`).
