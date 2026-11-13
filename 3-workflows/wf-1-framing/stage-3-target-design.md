---
status: active
---

# F3 · Target design

## Objective
Fix the Fabric names and structure for the scope, following the conventions, before anything is built.

## Input
- `1-framing/02-object-mapping.md` and `03-target-design-and-plan.md` (pre-filled by F2).
- Conventions:
  - Workspaces: `2-config/conventions/02-fabric-workspace/` (SDS: `6-…`, DPG: `5-…`)
  - Items: `2-config/conventions/03-fabric-items/`
  - Database project: `2-config/conventions/05-data-products/database-project-structure.md`

## Workflow Instructions
1. Confirm the workspace, folder and item names with the developer:
   - Source dataset: `DP_SDS_<DOMAIN>`, folder `<SOURCE>`, `LH_SDS_<SOURCE>`
   - Data product: `DP_DPG_<GROUP>`, `WH_DPG_<GROUP>`, `DPG-<GROUP>`, `LH_INP_SDS_<SRC>`
2. **Source dataset.** Describe the Lakehouse layout:
   - `Files/landing/<source>/…` holds files in the source format (csv, json, xml, …).
   - `Files/raw/<source>/…` holds every landed file converted to parquet.
   - Tables are built on top of RAW, with history. There is no cleansed zone.
   - Data is ingested directly from the source. No shortcut, no DPV1 ADLS linked service, no dataset.
   - The catalog is the view `[CATALOG].[<source>_catalog]` in the catalog warehouse.
3. **Data product.** List the silver tables and procedures and the gold views, with their DPV1 origin.
   - All T-SQL stays T-SQL.
   - Code from the dedicated pool moves through the DACPAC (wf-4).
   - INP, LDW, CURATED and STG logic becomes CTEs inside the silver load procedures.
4. Write the decisions under **Analyst notes** in `03-target-design-and-plan.md`: renames, merges, excluded objects and why.

## Output
- `1-framing/03-target-design-and-plan.md` (Analyst notes completed).

## Rules Checklist
- [ ] All names follow the conventions; deviations justified
- [ ] No T-SQL object is mapped to a notebook
- [ ] No cleansed zone in the Fabric design
