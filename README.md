# FABRIC-REPO-MIGRATION-AI

Migrates the **code and architecture** of the Synapse data platform (DPV1) to Microsoft Fabric, one project at a time, with GitHub Copilot or Claude Code agents. Data movement is a later phase. The aim: no DPV1 object left behind, and every migrated item giving the same results in Fabric as in DPV1.

## How to run a migration
1. **Pick the service agent** in Copilot Chat:
   - **m-source-dataset**: say the source, e.g. "EASYTENDER, domain Construction".
   - **m-data-product**: say the product, e.g. "GAIA". It starts only when every source it reads is migrated, and offers to migrate the missing ones first.
2. **Answer its questions** and approve after each stage. It checks the knowledge base, frames, builds, reviews and fixes, with the specialist agents ([agents.md](.github/agents.md)).
3. Optional: run `python -I 0-shared/scripts/refresh_hub.py`, then open `5-migration-hub/dpv1-fabric-migration-hub.html` (generated, not committed) to browse scopes, or ask the **m-scope-refresher** to refresh everything from DPV1.

Rules every agent follows: [.github/copilot-instructions.md](.github/copilot-instructions.md).

## Folders
| Folder | Content |
|---|---|
| `.github/` | Routing and rules (`copilot-instructions.md`), 8 agents ([agents.md](.github/agents.md)) |
| `0-shared/scripts/` | Deterministic work: scope engine, hub and knowledge base, framing, generators, review, tracking (table below) |
| `0-shared/templates/` | Migration Hub page template; `raw-to-delta-snippets.py`, the reusable notebook functions taken from DPV1 |
| `1-skills/` | Skills, all named `skill-*`: migration skills (`skill-scope-resolution`, `skill-sds-landing-raw-tables`, `skill-spark-notebook-to-fabric`, `skill-tsql-dedicated-to-fabric`, `skill-equivalence-tests`, `skill-data-validation`) and Fabric skills synced from Fabric-AI-DEV-REPO (read-only here) |
| `2-config/` | `conventions/` (synced, read-only); `migration/`: paths, project register, target names, catalog warehouse, environment values, owner decisions, catalog scripts |
| `3-workflows/` | `wf-1-framing`, `wf-2-migration-source-dataset`, `wf-3-migration-data-product`, `wf-4-migration-dacpac`, `wf-5-data-validation` (standalone) |
| `4-migration-project-deliverables/` | `source-dataset/<source>/`, `data-product/<project>/` (layout: [readme](4-migration-project-deliverables/readme.md)); `migration-portfolio.md` for every project |
| `5-migration-hub/` | Generated: `knowledge/` (one JSON per scope, read by agents), hub page, `migration-scope-index.md`, `estate-coverage.md`, `migration-map.json`, refresh report |
| `backlog.md` | Improvements to the framework, with status |

## Scripts
| Script | Used in | Does |
|---|---|---|
| `refresh_hub.py [--check\|--pull]` | refresher | DPV1 => map, knowledge base, hub page, scope index, estate register |
| `knowledge.py show\|check\|deps` | every agent | what is known about one scope; whether its DPV1 files changed; its dependencies |
| `frame_scope.py` | wf-1 F2 | framing pack with the as-is and to-be trees |
| `extract_scope_code.py` | wf-2, wf-3 | copies the scope's DPV1 code to `2-legacy-code/` |
| `create_catalog_view.py` | wf-2 S1 | catalog view (+ watermark table for incremental sources) |
| `build_source_dataset.py` (methods in `ingestion.py`) | wf-2 S1-S4 | Lakehouse, SOURCE_TO_RAW, RAW_TO_DELTA (one notebook only where DPV1 had one), MASTER_ORCHESTRATOR, VL_MAIN |
| `connections.py` | S4 | the Fabric connections to create: name per environment, type, gateway, DPV1 values, secret, VL_MAIN variable |
| `create_variable_library.py` | S4 / D4 | VL_MAIN (DEV / UAT / PRD): every id the pipelines read at run time |
| `source_contract.py publish\|show` | S4, wf-3 | hand-over from a source to data products, readiness |
| `build_input_lakehouse.py` | wf-3 D3 | `LH_INP_SDS_<SRC>` shortcuts |
| `dacpac_retarget.py`, `tsql_fabric_lint.py` | wf-4 | DACPAC retarget, Fabric T-SQL lint |
| `validate_data.py profiles\|init\|run\|report` | wf-5 | live DPV1 => DPV2 data validation, read-only, connections from the VS Code MSSQL profiles => `<project>/data-validation/` |
| `review_scope.py`, `fix_from_review.py` | S5 / D6 | gap review, script-level fixes |
| `project_inputs.py show\|set` | wf-1 F1 | the five framing inputs per project (workspace, deployment repo path…) |
| `deploy_publish.py publish\|status` | after each stage review | stores the build in `<deployment repo>/<workspace folder>/` |
| `track.py` | every stage | progress, change log, gates, portfolio |
| `sync_baseline.py` | maintenance | refresh conventions and skills from Fabric-AI-DEV-REPO |

Run them from the repository root with `python -I 0-shared/scripts/<script> --help`. VS Code: Terminal => Run Task => "Migration: …". Requirements: Python 3.10+; for builds, the .NET SDK and SqlPackage.
