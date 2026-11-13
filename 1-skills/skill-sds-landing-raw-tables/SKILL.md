---
name: skill-sds-landing-raw-tables
description: The Fabric source dataset pattern for migrated sources - ingested directly from the source; databases straight to Files/raw (parquet), APIs and files through Files/landing (as delivered) to Files/raw; then Lakehouse tables. No cleansed zone, no shortcut, no ADLS linked service. Used by wf-2.
---

# skill-sds-landing-raw-tables

## Layout of `LH_SDS_<SOURCE>`
```
Database source (structured)
  Files/raw/<src>/<table>/                                     one parquet file per table, written once by the Copy, overwritten each run
  Files/raw/<src>/<table>/<yyyy>/<mm>/<dd>/<HHhMM>/[HISTORY|DELETE_LOGS]   only when DPV1 raw had a date tree (EASYTENDER)
API or file source (semi-structured)
  Files/landing/<src>/<yyyy>/<mm>/<dd>/<HHhMM>/                every table of the run, as delivered (json, csv, xml, xlsx)
  Files/raw/<src>/<yyyy>/<mm>/<dd>/<HHhMM>/<table>/            parquet, written by the notebook
Tables  dbo.<table>                                            DPV1 table names, LOADING_DATE and meta_* columns
```
- Folder = table name (schema added only when two schemas share a table name). The date tree is used only when the source needs it: `scope_tree.layout()` reads it from the DPV1 code, `knowledge.py show` prints it, `03-target-design-and-plan.md` shows it.
- Methods and reasons: [ingestion-design.md](../../3-workflows/wf-2-migration-source-dataset/ingestion-design.md); one section per method in [skill-ingestion](../skill-ingestion/SKILL.md) (structured or semi-structured, full or incremental) and [skill-raw-to-lakehouse](../skill-raw-to-lakehouse/SKILL.md).
- There is **no cleansed zone** in Fabric. DPV1 CLEANSED logic (typing, dedup, history) moves into the RAW => tables notebook.
- There is **no shortcut** in a source dataset: data comes from the source connection. Shortcuts are created by the Data Product service (`LH_INP_SDS_<SOURCE>` in the product workspace => `LH_SDS_<SOURCE>`).

## Mapping from DPV1
| DPV1 | Fabric |
|---|---|
| `PL_RAWDATA_*`, `*_TO_ADLS` extract pipelines | `1-SOURCE_TO_RAW/PL_<SOURCE>_SOURCE_TO_RAW` (one per source, `LoadMode` FULL/INCREMENTAL) |
| `PL_CLNDATA_*`, `NTBK_*_RAW_TO_CLEAN*` variants | `2-RAW_TO_DELTA/NB_<SOURCE>_RAW_TO_DELTA` + `PL_<SOURCE>_RAW_TO_DELTA` |
| Masters, triggers, external orchestration | `0-ORCHESTRATION/PL_<SOURCE>_MASTER_ORCHESTRATOR` |
| DPV1 catalog script `Catalog_<SRC>` (table, isIncLoad, isActive, watermark) | View `[CATALOG].[<source>_catalog]` built from the script by `create_catalog_view.py`, in the catalog warehouse (`WH_CATALOG_<SOURCE>` in the source's workspace for now, the common warehouse later); drives the SOURCE_TO_RAW Lookup |
| Source linked service (Oracle, SQL Server, SFTP, REST…) | Fabric connection `CONN_<SOURCE>_<TECH>_<ENV>` (gateway when on-premises) |
| ADLS linked services (RAW / CLEANSED / CURATED zones) | Not migrated: OneLake is built into the Lakehouse and addressed by path |
| Datasets | Not migrated: Fabric has no datasets; source / sink settings sit in the activity |
| SPOT_DB source views | Lakehouse SQL endpoint; products read via `LH_INP_SDS_<SOURCE>` |
| `if(pipeline().DataFactory …)` values | `VL_MAIN` variables |

## Every parameter comes from VL_MAIN
Nothing environment-specific is written in a pipeline or notebook. `create_variable_library.py` generates the variables with DEV, UAT and PRD values.

| Where | How to read |
| --- | --- |
| Pipeline expression | `@pipeline().libraryVariables.<NAME>`, declared in the pipeline's `libraryVariables` block |
| Pipeline connection (`externalReferences.connection`) | `@pipeline().libraryVariables.<X>_CONN_ID` |
| Pipeline artifactId, endpoint of a Lakehouse or Warehouse | `@pipeline().libraryVariables.<NAME>`; workspaceId `@pipeline().DataFactory` ([deployment-design.md](../../3-workflows/wf-2-migration-source-dataset/deployment-design.md)) |
| Notebook | `vl = notebookutils.variableLibrary.getLibrary("VL_MAIN")`, then `vl.<NAME>` |

VL_MAIN of a source dataset holds only what locates things:
- `LH_SDS_<SOURCE>_ID` (no `WORKSPACE_ID` or `IS_PROD`: pipelines use `@pipeline().DataFactory`)
- Catalog: `<SRC>_CATALOG_VIEW_NAME` (`CATALOG.<source>_catalog`), `<SRC>_CATALOG_WAREHOUSE_NAME`, `<SRC>_CATALOG_WAREHOUSE_ID`, `<SRC>_CATALOG_WAREHOUSE_SQL_ENDPOINT`, `<SRC>_CATALOG_WAREHOUSE_CONN_ID` (+ `<SRC>_CATALOG_WAREHOUSE_WORKSPACE_ID` once the warehouse is shared). Every Lakehouse and Warehouse in a pipeline carries `externalReferences.connection` (`<SRC>_LH_CONN_ID`, `<SRC>_CATALOG_WAREHOUSE_CONN_ID`): without it Fabric's Git import fails with "Object reference not set". Tables, load mode, active flag and watermark stay in the view.
- Lakehouse connection: `<SRC>_LH_CONN_ID` (Fabric connection GUID used by Copy and Delete activities)
- One connection per source system: `<SOURCE>_<TECH>_CONN_ID`, `<SOURCE>_<TECH>_CONN_NAME`

Not in VL_MAIN: ADLS or DPV1 values, catalog details, batch sizes (`batchCount` is set in the ForEach, default 10).

## One Git sync
A pipeline never holds the id of another item: Lakehouse and warehouse connections are VL_MAIN expressions resolved at run time, so every item of the source deploys in one Git sync. No deploy tokens, no `parameter.yml`. Same-workspace references Git resolves itself (ExecutePipeline `referenceName`, `notebookId`, the notebook default lakehouse) use the `.platform` logicalId and the zero workspace GUID. Details and the GEOS incident: [deployment-design.md](../../3-workflows/wf-2-migration-source-dataset/deployment-design.md).

## Generator
`python -I 0-shared/scripts/build_source_dataset.py --id <SOURCE> [--stage S1|S2|S3|S4]` (methods in `ingestion.py`): the Lakehouse, `PL_<SOURCE>_SOURCE_TO_RAW`, `NB_<SOURCE>_RAW_TO_DELTA` (only when DPV1 had notebooks) and `PL_<SOURCE>_RAW_TO_DELTA`, the master and VL_MAIN, for structured and semi-structured sources, full or incremental, plus a note per stage.
