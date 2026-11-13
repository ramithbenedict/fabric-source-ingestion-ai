---
status: active
---

# S2 · Source to RAW

## Objective
Replace the DPV1 extract pipelines with one `PL_<SOURCE>_SOURCE_TO_RAW`: a Lookup on the catalog view, then one Copy per catalog row.
- **Structured source** (database, SharePoint list): the Copy writes **parquet once, straight to `Files/raw`**. No landing copy.
- **Semi-structured source** (API, files): the Copy lands the files **as delivered** in `Files/landing`; the S3 notebook writes them to `Files/raw` as parquet.

Both keep the DPV1 folder tree: `<entity>/<yyyy>/<mm>/<dd>/<HHhMM>[/HISTORY|/DELETE_LOGS]`. Design: [ingestion-design.md](ingestion-design.md).

## Input
- `02-object-mapping.md` rows with target `1-SOURCE_TO_RAW/…`, and their legacy JSON in `2-legacy-code/pipelines/`.
- The catalog view of S1 (standard columns: `LoadMethod`, `KeyColumns`, `WatermarkColumn`, `EntityName`, `FolderTail`, `SourcePath`, `SourceFormat`…).
- The skill of the source's method:

  | Source | Full | Incremental |
  | --- | --- | --- |
  | Database or list | [skill-ingestion (structured full)](../../1-skills/skill-ingestion/SKILL.md) | [skill-ingestion (structured incremental)](../../1-skills/skill-ingestion/SKILL.md) |
  | API or files | [skill-ingestion (semistructured full)](../../1-skills/skill-ingestion/SKILL.md) | [skill-ingestion (semistructured incremental)](../../1-skills/skill-ingestion/SKILL.md) |

## Workflow Instructions
1. Run `python -I 0-shared/scripts/build_source_dataset.py --id <SOURCE> --stage S2`. It picks the method from the DPV1 connection and catalog profile and writes `3-build/build-notes/build-notes.md#S2-source-to-raw`.
2. Compare the generated pipeline with each legacy extract pipeline:
   - every DPV1 table or API path is a catalog row (`SourcePath`, `SourceName`)
   - incremental rows: the `ExtractQuery` (Lookup output) filters on the DPV1 watermark column, minus 1 day
   - per-table queries: when DPV1 branches per table (a Switch on `@item().tableName` whose Copies run their own query), S2 writes them to `2-config/migration/extract-queries/<SRC>.json` and the Lookup returns them as `ExtractQuery`: one Copy replaces the branches. `@{item().X}` becomes the catalog column `c.[X]`; DPV1's trailing watermark filter is dropped (Fabric adds its own); an incremental row runs `SELECT * FROM (<query>) q WHERE <watermark> > <since>`, so the query must return its watermark column. A query that uses other pipeline expressions is listed as manual: write it in `overrides` of that file (kept by every build), then rebuild S2
   - REST: the pagination rules match DPV1 (S2 notes say where they were copied from, and whether they were adapted)
   - files: the wildcard and the modified-date filter match DPV1
   - incremental REST: the request DPV1 builds from the catalog row is copied to `2-config/migration/request-urls/<SRC>.json` (`item().WatermarkVal` becomes `item().WatermarkNow`, the live watermark the Lookup returns). A request that uses pipeline parameters or variables is listed as manual: write it in `override`, then rebuild S2. Review check "Incremental REST: the request carries the watermark"
   - mixed source: `PL_<SRC>_SOURCE_TO_RAW` has a second Lookup, ForEach and Copy for the file rows (`ConnectionKey = 'files'`); S3 flattens them (`NB_<SRC>_FLATTEN`, database rows pass through) and the loader reads each row from its own raw folder
3. Fill what DPV1 kept outside the catalog: API query strings, file options (`FileOptions`), record path (`RootPath`), keys of incremental rows (`KeyColumns`).
4. Replace every `if(pipeline().DataFactory …)` value with a `VL_MAIN` variable.
5. Keep the DPV1 success list: each Copy appends its row to `LoadedTables` (succeeded) or `table (copy): error` to `FailedTables` (failed); the pipeline returns both to the master. Do not migrate the other bookkeeping: "is there data?" WebActivities, Delete of the landing folder.

## Output
- `3-build/fabric-deployment/DP_SDS_<DOMAIN>/<SOURCE>/1-SOURCE_TO_RAW/PL_<SOURCE>_SOURCE_TO_RAW.DataPipeline/`
- `3-build/build-notes/build-notes.md#S2-source-to-raw`

## Rules Checklist
- [ ] Every legacy extract table or API path is a catalog row
- [ ] Every DPV1 per-table query (Switch branch) is in the Lookup `ExtractQuery`; none left as manual (review check "DPV1 per-table queries carried into the catalog Lookup")
- [ ] Structured source: one Copy per row writing parquet to `Files/raw`; no Copy from `Files/landing` to `Files/raw`
- [ ] Semi-structured source: files landed as delivered; no conversion in the pipeline
- [ ] The run folder comes from `RunPartition` (set by the master) and follows the DPV1 tree
- [ ] No environment if-chain left; every connection and catalog name from VL_MAIN
- [ ] Data comes from the source connection, never from DPV1 ADLS
