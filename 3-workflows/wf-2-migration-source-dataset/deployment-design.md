# Deployment design: every item of a source deploys in one Git sync

Status: active (2026-10-26). Applies to every pipeline the generators write (wf-2, and wf-3 when it reuses them).

## What went wrong with GEOS
| Finding | Effect in Fabric |
| --- | --- |
| `artifactId` / `endpoint` of the Lakehouse and the catalog warehouse held `__VL_MAIN.<NAME>__` deploy tokens | Only fabric-cicd replaces them through `parameter.yml`. A Git sync ("Update all") passes the text as an id: **"Failed to discover dependencies: Object reference not set"** on `PL_GEOS_SOURCE_TO_RAW` |
| The warehouse was referenced through a `linkedService` block, the Lakehouse without `workspaceId` | Not the shape of the curated patterns (`skill-fabric-create-pipeline`: `connectionSettings`) |
| A commit **from the workspace** (`Committing 24 items from workspace`) deleted from Git what the workspace did not have yet; the restore brought back GEOS but not `VL_MAIN.VariableLibrary` and the `.platform` of `WH_CATALOG.Warehouse` | The pipelines read `VL_MAIN`, which was no longer in Git: their dependency could not be found |

## The rule
A generated pipeline **never holds the id of another item**. Every connection is resolved when the pipeline runs:

| Field (`connectionSettings.properties.typeProperties`) | Lakehouse (same workspace) | Catalog warehouse (same workspace) | Catalog warehouse (shared workspace) |
| --- | --- | --- | --- |
| `artifactId` | `@pipeline().libraryVariables.LH_SDS_<SRC>_ID` | `@pipeline().libraryVariables.<SRC>_CATALOG_WAREHOUSE_ID` | same |
| `workspaceId` | `@pipeline().DataFactory` (the pipeline's own workspace) | `@pipeline().DataFactory` | `@pipeline().libraryVariables.<SRC>_CATALOG_WAREHOUSE_WORKSPACE_ID` |
| `endpoint` | - | `@pipeline().libraryVariables.<SRC>_CATALOG_WAREHOUSE_SQL_ENDPOINT` | same |
| `externalReferences.connection` | `@pipeline().libraryVariables.<SRC>_LH_CONN_ID` | `@pipeline().libraryVariables.<SRC>_CATALOG_WAREHOUSE_CONN_ID` | same |

The connection reference is required for the warehouse too. Without it, Fabric's Git import fails with **"Failed to discover dependencies: Object reference not set"** (RMA, 2026-10-27, B59). GEOS and CORNERSTONE imported because their Lookup had it.

Only same-workspace references that Git integration resolves itself stay as logicalIds: ExecutePipeline `referenceName`, TridentNotebook `notebookId`, the notebook's default lakehouse (zero workspace GUID). Every variable used is declared in the pipeline's `libraryVariables` block. There is no `parameter.yml` any more.

## One VL_MAIN per workspace, names that carry the source
A workspace can hold several sources (Platform-Hub: GEOS and CORNERSTONE), and it has one `VL_MAIN`. So every variable whose value differs per source carries the source: `<SRC>_CATALOG_VIEW_NAME`, `<SRC>_CATALOG_WATERMARK_TABLE_NAME`, `<SRC>_CATALOG_WAREHOUSE_NAME` / `_ID` / `_SQL_ENDPOINT` / `_CONN_ID`, `<SRC>_LH_CONN_ID` (list: `common.SOURCE_VARS`). `LH_SDS_<SRC>_ID` and `<SRC>_<TYPE>_CONN_ID` already carry it; `WORKSPACE_ID` is not a variable (pipelines use `@pipeline().DataFactory`). VL_MAIN has no `IS_PROD` either: the DEV, UAT and PRD value sets carry the environment.

- **One name in three places.** Fabric resolves `@pipeline().libraryVariables.X` against the pipeline's own `libraryVariables` block, not `VL_MAIN` directly. `X` must be the key of that block, its `variableName` and the `VL_MAIN` variable. A mismatch fails at run time with "Parameter X was not found under PL_…". Review check: "Every library variable used is declared in its pipeline under its VL_MAIN name".
- **Merged, never replaced.** `create_variable_library.save_workspace_library` builds `VL_MAIN` from the deployment repo's `VL_MAIN` of the workspace, the `VL_MAIN` of the other projects of the workspace, then this build. This build's variables win, except that a value still `<to set>` keeps a value set elsewhere. The deployment repo's logicalId is kept. `deploy_publish.py` then treats `VL_MAIN` as an update, not a conflict, when it keeps every deployed variable under the same logicalId.
- **Old names stay** until no deployed pipeline uses them (for example the unprefixed `CATALOG_*` names of the first GEOS build). The S4 build note lists them.

Result: Fabric finds no dependency on the Lakehouse or the Warehouse when it imports a pipeline, so the Lakehouse, the Warehouse, VL_MAIN, the notebook and the pipelines are imported **together, in any order, in one sync**. The ids are needed only at the first run: fill VL_MAIN DEV once the items exist.

## Standard rule: dependencies are in place before deployment
Applies to every artifact of every service (sds and dp). A deployment from the deployment repo to Fabric must not fail on a dependency, so the builder resolves each one **at build time**, and the review proves it.

| Dependency | Must be true before publish |
| --- | --- |
| Variable Library | `VL_MAIN` is in the same workspace folder, and every `@pipeline().libraryVariables.X` is declared in the pipeline's block under the `VL_MAIN` name |
| Pipeline calls | Every ExecutePipeline `referenceName` and TridentNotebook `notebookId` points to an item that exists in the deployed folder (logicalId matches its `.platform`) |
| Lakehouse / Warehouse / connection | Referenced only through `VL_MAIN` expressions with `externalReferences.connection` (table above); each item has its `.platform` and sits in the folder |
| Shortcuts (input Lakehouse) | The source Lakehouse and workspace the shortcut targets already exist (source dataset published and run); targets come from `VL_MAIN`, not literals |
| Warehouse / DACPAC | Database project builds (`dotnet build`), has no reference to an object outside the scope or to a schema not created in the project, and objects are in creation order (schemas, tables, views, procedures); no cross-database or `LDW` reference left |
| Notebooks | Default Lakehouse and parameters resolve from `VL_MAIN`; libraries are Fabric-available |
| Order across services | A data product never deploys before the source datasets it reads (`source_contract.py show`) |
| Repo state | `deploy_publish.py status` shows the deployment repo holds every build file, including `VL_MAIN` and each `.platform` |

Builders: write no item that needs another to exist first at import time; if one does, the build stops and logs it as an issue. Reviewers (S5, D6): every row above is a check; an unmet row is a ❌ that blocks publish. Anything the script cannot see (for example a shortcut target that is not yet deployed) is verified by the reviewer by reading the files.

## Deployment steps
1. `python -I 0-shared/scripts/deploy_publish.py publish --service sds --id <SOURCE>`: the whole workspace folder (VL_MAIN, warehouse, source folder) goes to `<deployment repo>/<workspace folder>/`.
2. Commit and push the deployment repo (branch of the workspace).
3. In Fabric, Source control => **Updates** => **Update all**. Do not use **Commit** in the workspace before the update: a commit from the workspace deletes from Git whatever the workspace does not have yet.
4. After the sync, fill the VL_MAIN DEV values (item ids, SQL endpoint, connection ids) and run `PL_<SOURCE>_MASTER_ORCHESTRATOR`.

## Checks
- Review (S5): "Pipelines deploy in one Git sync" fails on a deploy token, a literal `artifactId` / `workspaceId` / `endpoint`, a `linkedService` block for a Lakehouse or Warehouse, or a Lakehouse / Warehouse without `externalReferences.connection`.
- Publish: `deploy_publish.py publish` runs the same check (`common.one_sync_findings`) and copies nothing while a pipeline has a finding.
- `deploy_publish.py status`: the deployment repo holds every file of the build, including `VL_MAIN.VariableLibrary` and `WH_CATALOG_<SOURCE>.Warehouse/.platform`.

## Deployable gate and deployment order
Found by the RMA data product (2026-10-30): the shortcuts of `LH_INP_SDS_RMA` were published with `VL_MAIN` ids at the zero placeholder and the sync failed ("Either target workspace ID or artifact ID is not a valid GUID"). The review had counted it a warning, and nothing stopped the publish. Since then:

| Rule | Where it is enforced |
| --- | --- |
| A variable a shortcut needs at import (`LH_SDS_<SRC>_ID`, `_WORKSPACE_ID`) is a real GUID in the value set of the environment being deployed | `deploy_gate.unresolved_imports`: review ❌, `deploy_publish.py` refuses, `deploy_preflight.py check` |
| The ids come from one order: by hand, the source dataset's `VL_MAIN` in the deployment repo, Fabric. A disagreement (two ids, or an item id equal to a connection id) is asked | `resolve_upstream.py` |
| The database project creates every schema it uses, references only objects it creates, and reads the Lakehouse only in `[INP_<SRC>]` views (`1-input`) | `deploy_gate.closure`: review ❌, preflight |
| Every procedure a pipeline calls exists in the database project | `deploy_gate.closure` |
| A data product has a master and a child pipeline | `build_process_pipeline.py`, preflight |

Order of a data product deployment (written per product to `3-build/deployment-runbook.md` by `deploy_preflight.py runbook`): source dataset deployed and run, resolve ids, review and preflight, publish to the deployment repo, sync the workspace (Update all, never Commit first), fill the warehouse ids in `VL_MAIN`, publish the DACPAC (Azure DevOps, .NET 8), run the master, verify against DPV1, then UAT and PRD with their own ids. Values that exist only after the first sync (`WH_DPG_<G>_ID`, `_SQL_ENDPOINT`, `_CONN_ID`) are listed as to fill, never guessed.

## Promotion DEV => UAT => PRD (data product)

The same build deploys to every environment; only values change (DPV2: `fabric-git-repo-structure.md` section 3, `ci-cd-dacpac/`, `ci-cd/profiles/`). `deploy_gate.cicd()` checks it in the review, the preflight and before every publish:

- **One folder, no environment suffix.** The workspace folder is `DP_DPG_<G>`, never `DP_DPG_<G>_DEV`. `project_inputs.py` strips the suffix. The Git integration of each workspace points at that folder on its branch (dev, uat, prd).
- **Shortcuts, pipelines and VL_MAIN carry no id.** Shortcut targets are `$(/**/VL_MAIN/LH_SDS_<SRC>_ID)` and `_WORKSPACE_ID`; pipelines read `@pipeline().libraryVariables.*`; the DEV, UAT and PRD value sets hold the ids (`create_variable_library.py --env ENV --set NAME=VALUE`, kept in progress.json).
- **The DACPAC reads the Lakehouse through a SQLCMD variable.** The 1-input views read `[$(LH_INP_SDS_<SRC>)].[dbo].[t]`; `DPG-<G>.sqlproj` declares the variable and references `EXT-LH-INP-SDS-<SRC>` (stub tables, so the build resolves them); the DACPAC pipeline passes `/v:LH_INP_SDS_<SRC>=LH_INP_SDS_<SRC>`. No variable is passed that the sqlproj does not declare.
- **One DACPAC pipeline per product** (`ci-cd-dacpac/pipeline-dpg-<g>.yml`) with the `targetServer` of the warehouse of each environment, and **one profile per environment** (`ci-cd/profiles/dp_dpg_<g>_{dev,uat,prd}.yaml`, listed in `deployment-pipeline.yaml`). `build_cicd.py` writes them; `deploy_publish.py` copies them and registers the profiles.
- Values that exist only once an environment exists (workspace id, warehouse SQL endpoint, item and connection ids) stay `<to set>`, are listed by `deploy_preflight.py check`, and are given with `build_cicd.py --workspace-id/--endpoint` and `create_variable_library.py --set`. They are never copied from DEV.
- **A project that already has a DACPAC in DPV1** (`dacpac_retarget.py --sqlproj <folder>`) follows the same rules. Its SQLCMD variables (declared in the sqlproj, valued per environment in its publish profiles) and every `$(VAR)` its code uses are carried over: declared in `DPG-<G>.sqlproj`, passed per environment by the DACPAC pipeline, listed in `4-dacpac/retarget-report.md`. A value that is not known stays `<to set>` and is listed by the preflight; give it with `build_cicd.py --var ENV:NAME=VALUE`. Pre- and post-deployment scripts and Synapse-only objects (external data sources, credentials, file formats) are not dropped silently: they are listed as skipped or flagged by the lint for a decision. Not yet run end-to-end on a real DPV1 sqlproj (none was available at the time).
