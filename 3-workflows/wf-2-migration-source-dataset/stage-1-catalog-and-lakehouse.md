---
status: active
---

# S1 · Catalog view and Lakehouse

## Objective
- Build the source's catalog view `[CATALOG].[<source>_catalog]` from its DPV1 catalog script, in the catalog warehouse.
- Create `LH_SDS_<SOURCE>` with `Files/landing`, `Files/raw` and `dbo` tables.
- No shortcut: this service ingests directly from the source (S2).

## Input
- DPV1 catalog script `Catalog_<SOURCE>`: `CREATE TABLE [CATALOG].[<SOURCE>]` plus one INSERT per table.
- `2-config/migration/shared-platform.json`:
  - catalog warehouse: `WH_CATALOG_<SOURCE>` in the source's workspace for now (`catalog_warehouse_pattern`); the common warehouse later (`catalog_warehouse_location = shared`)
  - schema `CATALOG` and the view name pattern `{source}_catalog`
- `1-framing/03-target-design-and-plan.md`.
- Skills:
  - [skill-fabric-create-warehouse](../../1-skills/skill-fabric-create-warehouse/SKILL.md)
  - [skill-fabric-create-lakehouse](../../1-skills/skill-fabric-create-lakehouse/SKILL.md)
  - [skill-sds-landing-raw-tables](../../1-skills/skill-sds-landing-raw-tables/SKILL.md)

## Workflow Instructions
1. **Catalog view.** Run `python -I 0-shared/scripts/create_catalog_view.py --id <SOURCE>`. It reads the DPV1 catalog script and writes:
   - the `WH_CATALOG_<SOURCE>.Warehouse` item with its SDK database project
   - `[CATALOG].[<source>_catalog]` (e.g. `geos_catalog`): all the catalog details, DPV1 columns converted to Fabric types, DPV1 rows embedded
   - `catalog-view.md`: rows, active, incremental, and the 3 VL_MAIN variables
   - gate `catalog_rows_match`
   - the catalog parser reads the layouts DPV1 used: one INSERT per row, values over several lines, a column list, several tuples per INSERT, and column lists that start each line with a comma
   - **files ingested next to the database** (mixed source, for example GAIA: Oracle plus SharePoint Excel and CSV): `2-config/migration/file-inputs/<SOURCE>.json` lists them (connection, folder, one table each, `confirm: true` when inferred from the tables the data product reads; correct it in `overrides`). They become catalog rows with `ConnectionKey = 'files'`, the database rows are `'main'`
2. **Lakehouse.** Run `python -I 0-shared/scripts/build_source_dataset.py --id <SOURCE> --stage S1`. It writes `LH_SDS_<SOURCE>.Lakehouse` (default schema `dbo`) in `3-build/fabric-deployment/DP_SDS_<DOMAIN>/<SOURCE>/` and `3-build/build-notes/build-notes.md#S1-lakehouse`.
3. Log any table with no catalog entry as an open point (`track.py log --type issue`).

## Output
- `3-build/fabric-deployment/<WORKSPACE>/WH_CATALOG_<SOURCE>.Warehouse/` (item, `.sqlproj`, `CATALOG/Views/<source>_catalog.sql`; `DP_COMMON/` once shared) and `3-build/build-notes/build-notes.md#S1-catalog-view`
- `3-build/fabric-deployment/DP_SDS_<DOMAIN>/<SOURCE>/LH_SDS_<SOURCE>.Lakehouse/` and `3-build/build-notes/build-notes.md#S1-lakehouse`

## Rules Checklist
- [ ] View row count equals the DPV1 catalog script (commented-out rows excluded)
- [ ] VL_MAIN holds only where the view is: `<SRC>_CATALOG_VIEW_NAME`, `<SRC>_CATALOG_WAREHOUSE_NAME`, `<SRC>_CATALOG_WAREHOUSE_ID`, `<SRC>_CATALOG_WAREHOUSE_SQL_ENDPOINT` and `<SRC>_CATALOG_WAREHOUSE_CONN_ID` (the Lookup connection needs the endpoint and the connection); the catalog details stay in the view
- [ ] No shortcut, no ADLS connection in the source dataset
- [ ] No GUID, path or name hardcoded
