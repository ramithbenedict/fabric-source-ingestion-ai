---
status: active
---

# S4 · Orchestration and variable library

## Objective
One master pipeline per source with the legacy schedule, and a complete `VL_MAIN` with DEV, UAT and PRD values.

## Input
- `02-object-mapping.md` rows with target `0-ORCHESTRATION/…`, and the trigger rows.
- `1-framing/03-target-design-and-plan.md`.
- [skill-fabric-create-pipeline](../../1-skills/skill-fabric-create-pipeline/SKILL.md).

## Workflow Instructions
1. **Variable library.** Run `python -I 0-shared/scripts/create_variable_library.py --service sds --id <SOURCE>`.
   - It writes `VL_MAIN.VariableLibrary` in Fabric Git format, with value sets DEV, UAT and PRD.
   - One VL_MAIN per workspace, shared by its sources: it is merged with the deployment repo and the other projects of the workspace, and names that differ per source carry it ([deployment-design.md](deployment-design.md#one-vl_main-per-workspace-names-that-carry-the-source)).
   - It holds only what pipelines and notebooks need to locate things: `LH_SDS_<SOURCE>_ID`, `<SRC>_CATALOG_VIEW_NAME`, `<SRC>_CATALOG_WAREHOUSE_NAME`, `<SRC>_CATALOG_WAREHOUSE_ID`, `<SRC>_CATALOG_WAREHOUSE_SQL_ENDPOINT`, `<SRC>_CATALOG_WAREHOUSE_CONN_ID`, `<SRC>_LH_CONN_ID` and one connection per source system.
   - Pipelines read every id from it at run time, so all items deploy in one Git sync ([deployment-design.md](deployment-design.md)). `build_source_dataset.py --stage S4` regenerates it.
   - Not in VL_MAIN: the catalog details (they are in the view), DPV1 ADLS / Synapse values, batch sizes.
   - Known values come from `2-config/migration/environment-values.json`. Ask the developer for each `<to set>` value they already know, and update that file when the value is shared.
2. **Master pipeline.** Run `python -I 0-shared/scripts/build_source_dataset.py --id <SOURCE> --stage S4` (database sources), or generate `PL_<SOURCE>_MASTER_ORCHESTRATOR` by hand. It calls SOURCE_TO_RAW, then RAW_TO_DELTA with the `LoadedTables` that SOURCE_TO_RAW returned, updates watermarks for the loaded incremental tables only, and ends **Failed** with the list of failed tables and their errors when any table failed (the others are loaded). It reads every environment value from `VL_MAIN` (`@pipeline().libraryVariables.<NAME>`).
3. **Connections.** `--stage S4` writes `3-build/build-notes/connections.md`: each Fabric connection to create (name per environment, type, gateway, the DPV1 host / port / service / database / URL, authentication, Key Vault secret) and the VL_MAIN variable that gets its id; plus the Lakehouse and warehouse connections and the item ids to fill after the first sync. Also: `python -I 0-shared/scripts/connections.py --service sds --id <SOURCE>`.
4. **Alerts instead of mail wrappers.** Do not migrate `PL_GENERIC_MAIL_NOTIFICATION` or the per-source log / success / failure child pipelines. Document an Activator job alert (failure and success) on the master pipeline, and use workspace monitoring.
5. **Schedule.** Record the legacy schedule from the trigger, or from the external orchestrator if there is no trigger. Do not activate it before the data phase and the cut-over are agreed.

6. **Parallel loads.** The master has parameter `MaxParallel` (default 8: tables loaded at the same time, the others wait) and concurrency 1 (a second run of the source waits). Once per workspace, in the Spark settings: turn on *high concurrency for pipelines* and set `spark.scheduler.mode=FAIR`. Sizing: [skill-raw-to-lakehouse](../../1-skills/skill-raw-to-lakehouse/SKILL.md#5-or-100-tables-one-session-tables-in-parallel).

7. **Hand-over.** `build_source_dataset.py --stage S4` publishes `source-dataset-contract.json` at the project root (or run `python -I 0-shared/scripts/source_contract.py publish --id <SOURCE>`).

## Output
- `3-build/fabric-deployment/DP_SDS_<DOMAIN>/VL_MAIN.VariableLibrary/` (workspace root)
- `3-build/fabric-deployment/DP_SDS_<DOMAIN>/<SOURCE>/0-ORCHESTRATION/PL_<SOURCE>_MASTER_ORCHESTRATOR.DataPipeline/`, `3-build/build-notes/build-notes.md#S4-orchestration` and `3-build/build-notes/connections.md`

## Rules Checklist
- [ ] VL_MAIN has DEV, UAT and PRD value sets; gate `vl_main_complete` shows the remaining `<to set>` values
- [ ] No pipeline holds an environment value outside VL_MAIN
- [ ] Schedule documented, not activated
