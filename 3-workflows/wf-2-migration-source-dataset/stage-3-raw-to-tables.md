---
status: active
---

# S3 · RAW to Lakehouse tables

## Objective
Build the `dbo` tables of `LH_SDS_<SOURCE>` from RAW, with the same result as DPV1 CLEANSED. There is no cleansed zone in Fabric.
- Only the tables that copied in this run are loaded: `PL_<SOURCE>_RAW_TO_DELTA` has no catalog Lookup; it gets `LoadedTables` from S2 and returns `LoadedTables` / `FailedTables`.
- **DPV1 used notebooks for the source** => one `NB_<SOURCE>_RAW_TO_DELTA` that loads those tables in one Spark session; semi-structured sources first run `NB_<SOURCE>_FLATTEN` (landing => flattened raw parquet).
- **DPV1 used no notebook** (Data Flow or Copy only) => no notebook: a Copy writes each raw parquet folder to its table; each Data Flow is reviewed.

Design: [ingestion-design.md](ingestion-design.md).

## Input
- `02-object-mapping.md` rows with target `2-RAW_TO_DELTA/…`, and the legacy notebooks in `2-legacy-code/notebooks/`.
- Skills:
  - [skill-raw-to-lakehouse](../../1-skills/skill-raw-to-lakehouse/SKILL.md)
  - the ingestion skill of the source (see S2)
  - [skill-spark-notebook-to-fabric](../../1-skills/skill-spark-notebook-to-fabric/SKILL.md) for Data Flows and source-specific notebook logic

## Workflow Instructions
1. Run `python -I 0-shared/scripts/build_source_dataset.py --id <SOURCE> --stage S3`. It writes the notebook (or the Copy pipeline) and `3-build/build-notes/build-notes.md#S3-raw-to-tables`.
2. Read `clean()` in the notebook: one line per DPV1 cleaning step, each naming the legacy notebook it comes from. Add a step only when a legacy notebook has it; never invent one.
3. Logic shared by many sources: change its function in `0-shared/templates/raw-to-delta-snippets.py` and regenerate. Logic special to this source (a join, a pivot, a derived column) goes into its `clean()`, with a comment naming the legacy notebook.
4. Incremental rows: confirm `KeyColumns` and `WatermarkColumn` in the catalog; the MERGE needs both.
5. Data Flows listed in the notes: decide per flow (Copy covers a column mapping; other logic becomes T-SQL or notebook code) and log the decision.
6. Log every legacy notebook merged and every behaviour difference.

## Output
- `3-build/fabric-deployment/DP_SDS_<DOMAIN>/<SOURCE>/2-RAW_TO_DELTA/`: notebook (when DPV1 had one) and pipeline
- `3-build/build-notes/build-notes.md#S3-raw-to-tables`

## Rules Checklist
- [ ] A notebook exists only when DPV1 used notebooks for the source; one loader per source, plus `NB_<SOURCE>_FLATTEN` for semi-structured sources
- [ ] No catalog Lookup in S3; the loader reads `tables_json` and `Files/raw` only, and reports a failed table instead of stopping
- [ ] No `notebook.run` (no child notebook per table)
- [ ] Every line of `clean()` names its legacy notebook; the functions come from `raw-to-delta-snippets.py`
- [ ] Table names equal the DPV1 table names, so `LH_INP_SDS_<SOURCE>` keeps the same names
- [ ] History, delete logs and load mode of DPV1 kept or documented
