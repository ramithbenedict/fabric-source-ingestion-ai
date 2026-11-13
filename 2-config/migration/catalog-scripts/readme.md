# Catalog scripts supplied by the owner

Use this folder only when the DPV1 export has no catalog script for a source (the table list lives only in the metabase table `CATALOG.<SOURCE>`).

- File name: `<SOURCE>.sql`, e.g. `EASYTENDER.sql`
- Content: the same format as a DPV1 catalog script: `CREATE TABLE [CATALOG].[<SOURCE>] (...)` followed by one `INSERT INTO [CATALOG].[<SOURCE>] VALUES (...)` per table.
  Easiest: script the metabase table `CATALOG.<SOURCE>` as CREATE + INSERT.
- Then run `python -I 0-shared/scripts/create_catalog_view.py --id <SOURCE>`: it builds `[CATALOG].[<source>_catalog]` from it and sets the gate `catalog_rows_match`.
