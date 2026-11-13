---
name: skill-scope-resolution
description: How a DPV1 project is resolved into a source dataset or data product scope, with evidence per object and a name check, using 5-migration-hub/migration-map.json. Used by wf-1-framing F2.
---

# skill-scope-resolution

The scope engine is `0-shared/scripts/dpv1_mapping.py`. It runs through `refresh_hub.py` and writes `5-migration-hub/migration-map.json`. Never build a scope by hand: run `frame_scope.py`.

## Identifiers accepted
| Service | Identifier | Example |
|---|---|---|
| Source dataset (`--service sds`) | source name; domain via `--domain` | `GAIA` + `ENG` |
| Data product (`--service dp`) | project name, any pipeline of the product (e.g. a master), DW/DM schema | `GAIA`, `00_PL_GAIA_ORCH_MASTER`, `DW_GAIA` |

## Rules that draw the boundary (the "Found by" evidence)
1. **Scope folder.**
   - Source datasets: `01_CORE_DATA/NN_<SRC>` and `01_GLOBAL_DATA_SOURCES/NN_<SRC>`.
   - Data products: `02_PROJECTS/<X>` (+ `03_INTEGRATION_PROJECTS`, `05_BUSR`).
   - Numeric prefixes and spelling variants are normalised (alias table in `dpv1_mapping.py`).
2. **Entry point.** A pipeline started by a trigger, placed in `99_EXTERNAL_ORCHESTRATION`, or called by no other pipeline.
3. **Called by.** The Execute Pipeline closure from the entry points, plus notebooks run by those pipelines, notebook names passed as parameters (e.g. `IngestionNotebook`) and notebooks run by notebooks (`mssparkutils.notebook.run`, `%run`).
   - A source dataset keeps RAW=>CLEANSED steps even when they sit in a project folder, and hands product steps to the data product.
   - A data product marks source steps as `upstream`. It adds pipelines that deploy product DDL (`EXECUTE_*_SCRIPT`, `DB_BUILD`) and copy-back roots named after the scope.
4. **Used by / Starts.** Notebooks, data flows, datasets, linked services and triggers of those pipelines.
5. **Defined in / Referenced by / Catalog table.**
   - SQL objects created in the scope's schemas.
   - Tables read but not defined in the repo: their DDL must come from the database.
   - Source tables from `CATALOG.<SRC>`.

6. **Data lineage.** Each source dataset gets data tokens: ADLS folders `DATASOURCE=<X>`, SPOT lake database `<Prefix>_<Project>`, `rpl_<src>` views. A data product whose pipelines, SQL scripts or notebooks name a token reads that source: the source lists it under `consumers` (analysis only), the product gets the source in `upstream` (`upstream_data`).
7. **Shared framework.** Generic pipelines used by many scopes get an explicit action from `SHARED_RULES` (mail => Activator, catalog creation => catalog view, copy-back => dropped, DB build => DACPAC, monitoring => workspace monitoring).
8. **Owner decisions.** `2-config/migration/scope-decisions.json` overrides the rules for named objects (keys `sds`, `dp`, `estate`).

## Estate register
Every object of the export that no scope reaches is listed in `5-migration-hub/estate-coverage.md` with a category: shared framework, platform (integration runtimes, Spark configurations, managed private endpoints, identity, templates), name match with a scope, unused (test or old copy, never started, not referenced), or unassigned. Nothing is silently left out.

## Name check
Every other DPV1 object whose name or folder starts with the scope name is listed in `01-scope-analysis.md`:
- `other service`: in the source dataset or data product of the same project
- `in <scope>`: owned by another scope
- `not included`: must be confirmed out of scope or added by hand

## When the result looks wrong
Fix the rule in `dpv1_mapping.py` (or the alias table) and re-run `refresh_hub.py`. Don't edit the generated framing files.
