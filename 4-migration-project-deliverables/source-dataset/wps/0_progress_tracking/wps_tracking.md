# Tracking: WPS (Source dataset)

Last update: 2026-10-29

Sections: [ID card](#project-id-card) · [Stages](#workflow-and-stage-status) · [Gates](#mandatory-gates) · [Inputs](#inputs-received) · [Risks](#open-risks--blockers) · [Change log](#change-log) · [Definitions](#status-definitions)

## Project ID Card
- **Project name**: WPS
- **Service offering**: Source dataset
- **Domain**: DIG (to confirm)
- **Target**: `Platform-Hub_<ENV>` / `LH_SDS_WPS`
- **Source systems**: Oracle
- **Ingestion**: Directly from the source: databases => Files/raw (parquet) => tables; APIs and files => Files/landing (as delivered) => Files/raw (parquet) => tables. No shortcut.
- **Complexity (repo)**: Small (15 objects)
- **Register**: WPS (Small)
- **Owner**: TBD
- **Created on**: 2026-10-28
- **Last updated**: 2026-10-29

## Workflow and Stage Status
- **Completion**: 100%
- **Current stage**: ✅ all stages completed

| # | Workflow | Stage Name | Status | Notes |
| --- | --- | --- | --- | --- |
| F1 | `wf-1-framing` | Capture the request | ✅ completed |  |
| F2 | `wf-1-framing` | Scope analysis | ✅ completed |  |
| F3 | `wf-1-framing` | Target design | ✅ completed |  |
| F4 | `wf-1-framing` | Migration plan and approval | ✅ completed |  |
| S1 | `wf-2-migration-source-dataset` | Catalog view and Lakehouse | ✅ completed |  |
| S2 | `wf-2-migration-source-dataset` | Source to landing and RAW | ✅ completed |  |
| S3 | `wf-2-migration-source-dataset` | RAW to Lakehouse tables | ✅ completed |  |
| S4 | `wf-2-migration-source-dataset` | Orchestration and variable library | ✅ completed |  |
| S5 | `wf-2-migration-source-dataset` | Gap review and readiness | ✅ completed |  |

## Mandatory Gates

| Gate | Status | Evidence |
| --- | --- | --- |
| Framing approved by the owner | ✅ completed | Developer approval, 2026-10-28 |
| Name check: no "not included" object left | ✅ completed | 0 objects not included (01-scope-analysis.md) |
| Catalog view rows = DPV1 catalog script | ✅ completed | 27 view rows / 27 catalog script rows |
| VL_MAIN: no `<to set>` value for DEV | ✅ completed | VL_MAIN synced from workspace to repo (fd7bc74, 888c79c); pipeline runs end to end in Fabric, 2026-10-29 |
| Gap review: no ❌ finding left | ✅ completed | review/gap-review.md (2026-10-29) |

## Inputs Received

- [x] Domain: `COST`
- [x] Workspace: `Platform-Hub`
- [x] Deployment repo: `C:\Ten_Fabric_Data_Platform\fabric_deployment_repository\REPO-FABRIC-DEPLOYMENT`
- [x] Service: `Source Dataset`
- [x] Name: `WPS`
- [x] Workspace folder: `Platform-Hub`
- [x] Catalog warehouse: `WH_CATALOG_COMMON`
- [x] Source dataset identifier: `WPS` (resolved from name)
- [x] Domain: `COST`
- [x] Catalog warehouse: `WH_CATALOG_WPS`

## Open Risks / Blockers

- None identified yet

## Change Log

Chronological order: the first activity is at the top.

| # | Date | Workflow | Stage | Type | Activity |
| --- | --- | --- | --- | --- | --- |
| 1 | 2026-10-28 16:54 | - | - | 🟡 started | Source dataset migration started |
| 2 | 2026-10-28 16:54 | wf-1-framing | F2 | 🔵 change | Framing pack generated in `1-framing/` (42 objects) |
| 3 | 2026-10-28 16:54 | wf-1-framing | F1 | ✅ completed | Capture the request: ✅ completed |
| 4 | 2026-10-28 16:54 | wf-1-framing | F2 | 🟡 started | Scope analysis: 🟡 in progress - resolve review rows, then mark completed |
| 5 | 2026-10-28 17:11 | - | - | ✅ completed | Gate framing_approved: ✅ completed (Developer approval, 2026-10-28) |
| 6 | 2026-10-28 17:12 | wf-1-framing | F2 | ✅ completed | Scope analysis: ✅ completed - approved by developer 2026-10-28 |
| 7 | 2026-10-28 17:12 | wf-1-framing | F3 | ✅ completed | Target design: ✅ completed - approved by developer 2026-10-28 |
| 8 | 2026-10-28 17:12 | wf-1-framing | F4 | ✅ completed | Migration plan and approval: ✅ completed - approved by developer 2026-10-28 |
| 9 | 2026-10-28 17:12 | - | - | ✔️ decision | Domain COST, workspace Platform-Hub (same catalog warehouse WH_CATALOG_WPS); RMA paused at S5 to start WPS |
| 10 | 2026-10-28 17:12 | wf-2-migration-source-dataset | S1 | 🔵 change | Built `LH_SDS_WPS.Lakehouse` (build_source_dataset.py) |
| 11 | 2026-10-28 17:12 | wf-2-migration-source-dataset | S2 | 🔵 change | Built `PL_WPS_SOURCE_TO_RAW` (build_source_dataset.py) |
| 12 | 2026-10-28 17:12 | wf-2-migration-source-dataset | S3 | 🔵 change | Built `NB_WPS_RAW_TO_DELTA`, `PL_WPS_RAW_TO_DELTA` (build_source_dataset.py) |
| 13 | 2026-10-28 17:12 | wf-2-migration-source-dataset | S4 | 🔵 change | Source dataset contract published: 27 tables, 0 consuming data products, ready=False |
| 14 | 2026-10-28 17:12 | wf-2-migration-source-dataset | S4 | 🔵 change | Built `PL_WPS_MASTER_ORCHESTRATOR`, `VL_MAIN`, `connections.md`, `source-dataset-contract` (build_source_dataset.py) |
| 15 | 2026-10-28 17:12 | wf-2-migration-source-dataset | S1 | 🔵 change | Catalog view `[CATALOG].[wps_catalog]` generated in `WH_CATALOG_WPS`: 27 rows (27 active), from dpv1 |
| 16 | 2026-10-28 17:13 | wf-2-migration-source-dataset | S5 | ℹ️ note | Gap review: ⚠️ ready with warnings (0 ❌, 3 ⚠️, 1 ⚪), review/gap-review.md |
| 17 | 2026-10-28 17:14 | wf-2-migration-source-dataset | S1 | ✅ completed | Catalog view and Lakehouse: ✅ completed - stage review passed |
| 18 | 2026-10-28 17:14 | wf-2-migration-source-dataset | S2 | ✅ completed | Source to landing and RAW: ✅ completed - stage review passed |
| 19 | 2026-10-28 17:14 | wf-2-migration-source-dataset | S3 | ✅ completed | RAW to Lakehouse tables: ✅ completed - stage review passed |
| 20 | 2026-10-28 17:14 | wf-2-migration-source-dataset | S4 | ✅ completed | Orchestration and variable library: ✅ completed - stage review passed |
| 21 | 2026-10-28 17:14 | wf-2-migration-source-dataset | S4 | 🔵 change | Source dataset contract published: 27 tables, 0 consuming data products, ready=False |
| 22 | 2026-10-28 17:14 | wf-2-migration-source-dataset | S5 | ℹ️ note | Gap review: ⚠️ ready with warnings (0 ❌, 4 ⚠️, 0 ⚪), review/gap-review.md |
| 23 | 2026-10-28 17:14 | - | - | 🔵 change | Artifacts stored in the deployment repo `C:\Ten_Fabric_Data_Platform\fabric_deployment_repository\REPO-FABRIC-DEPLOYMENT` under `Platform-Hub/`: 18 files, 0 conflicts kept |
| 24 | 2026-10-28 17:41 | wf-2-migration-source-dataset | S1 | 🔵 change | Catalog view `[CATALOG].[wps_catalog]` generated in `WH_CATALOG_COMMON`: 27 rows (27 active), from dpv1 |
| 25 | 2026-10-28 17:41 | wf-2-migration-source-dataset | S5 | ℹ️ note | Gap review: ⚠️ ready with warnings (0 ❌, 3 ⚠️, 0 ⚪), review/gap-review.md |
| 26 | 2026-10-28 17:41 | - | - | 🔵 change | Artifacts stored in the deployment repo `C:\Ten_Fabric_Data_Platform\fabric_deployment_repository\REPO-FABRIC-DEPLOYMENT` under `Platform-Hub/`: 1 files, 1 conflicts kept |
| 27 | 2026-10-28 17:43 | - | S1 | ✔️ decision | Catalog view of WPS moved to the common warehouse WH_CATALOG_COMMON (framing input catalog_warehouse); VL_MAIN uses COMMON_CATALOG_WAREHOUSE_*; WH_CATALOG_WPS dropped |
| 28 | 2026-10-28 17:43 | - | - | 🔵 change | Artifacts stored in the deployment repo `C:\Ten_Fabric_Data_Platform\fabric_deployment_repository\REPO-FABRIC-DEPLOYMENT` under `Platform-Hub/`: 0 files, 0 conflicts kept |
| 29 | 2026-10-28 17:49 | wf-2-migration-source-dataset | S4 | 🔵 change | VL_MAIN generated: 9 variables, DEV / UAT / PRD, 18 values `<to set>` |
| 30 | 2026-10-28 17:49 | wf-2-migration-source-dataset | S1 | 🔵 change | Catalog view `[CATALOG].[wps_catalog]` generated in `WH_CATALOG_COMMON`: 27 rows (27 active), from dpv1 |
| 31 | 2026-10-28 17:56 | wf-2-migration-source-dataset | S5 | ℹ️ note | Gap review: ⚠️ ready with warnings (0 ❌, 2 ⚠️, 0 ⚪), review/gap-review.md |
| 32 | 2026-10-28 18:15 | wf-2-migration-source-dataset | S1 | 🔵 change | Built `LH_SDS_WPS.Lakehouse` (build_source_dataset.py) |
| 33 | 2026-10-28 18:15 | wf-2-migration-source-dataset | S2 | 🔵 change | Built `PL_WPS_SOURCE_TO_RAW` (build_source_dataset.py) |
| 34 | 2026-10-28 18:15 | wf-2-migration-source-dataset | S3 | 🔵 change | Built `NB_WPS_RAW_TO_DELTA`, `PL_WPS_RAW_TO_DELTA` (build_source_dataset.py) |
| 35 | 2026-10-28 18:15 | wf-2-migration-source-dataset | S4 | 🔵 change | Built `PL_WPS_MASTER_ORCHESTRATOR`, `VL_MAIN`, `connections.md`, `source-dataset-contract` (build_source_dataset.py) |
| 36 | 2026-10-28 18:15 | - | - | 🔵 change | Artifacts stored in the deployment repo `C:\Ten_Fabric_Data_Platform\fabric_deployment_repository\REPO-FABRIC-DEPLOYMENT` under `Platform-Hub/`: 2 files, 4 conflicts kept |
| 37 | 2026-10-28 18:15 | - | - | 🔵 change | Artifacts stored in the deployment repo `C:\Ten_Fabric_Data_Platform\fabric_deployment_repository\REPO-FABRIC-DEPLOYMENT` under `Platform-Hub/`: 4 files, 0 conflicts kept |
| 38 | 2026-10-28 18:15 | wf-2-migration-source-dataset | S4 | 🔵 change | Source dataset contract published: 27 tables, 0 consuming data products, ready=True |
| 39 | 2026-10-28 18:15 | wf-2-migration-source-dataset | S5 | ℹ️ note | Gap review: ⚠️ ready with warnings (0 ❌, 1 ⚠️, 0 ⚪), review/gap-review.md |
| 40 | 2026-10-28 18:22 | - | - | 🔵 change | Artifacts stored in the deployment repo `C:\Ten_Fabric_Data_Platform\fabric_deployment_repository\REPO-FABRIC-DEPLOYMENT` under `Platform-Hub/`: 0 files, 0 conflicts kept |
| 41 | 2026-10-28 18:24 | wf-2-migration-source-dataset | S4 | 🔵 change | VL_MAIN generated: 9 variables, DEV / UAT / PRD, 18 values `<to set>` |
| 42 | 2026-10-28 18:24 | - | - | 🔵 change | Artifacts stored in the deployment repo `C:\Ten_Fabric_Data_Platform\fabric_deployment_repository\REPO-FABRIC-DEPLOYMENT` under `Platform-Hub/`: 7 files, 0 conflicts kept |
| 43 | 2026-10-28 22:04 | wf-2-migration-source-dataset | S4 | 🔵 change | Built `PL_WPS_MASTER_ORCHESTRATOR`, `VL_MAIN`, `connections.md`, `source-dataset-contract` (build_source_dataset.py) |
| 44 | 2026-10-28 22:04 | wf-2-migration-source-dataset | S4 | 🔵 change | Source dataset contract published: 27 tables, 0 consuming data products, ready=True |
| 45 | 2026-10-28 22:04 | wf-2-migration-source-dataset | S5 | ⚠️ issue | Gap review: ❌ not ready (2 ❌, 2 ⚠️, 0 ⚪), review/gap-review.md |
| 46 | 2026-10-28 22:04 | wf-2-migration-source-dataset | S1 | 🔵 change | Built `LH_SDS_WPS.Lakehouse` (build_source_dataset.py) |
| 47 | 2026-10-28 22:04 | wf-2-migration-source-dataset | S2 | 🔵 change | Built `PL_WPS_SOURCE_TO_RAW` (build_source_dataset.py) |
| 48 | 2026-10-28 22:04 | wf-2-migration-source-dataset | S3 | 🔵 change | Built `NB_WPS_RAW_TO_DELTA`, `PL_WPS_RAW_TO_DELTA` (build_source_dataset.py) |
| 49 | 2026-10-28 22:04 | wf-2-migration-source-dataset | S4 | 🔵 change | Built `PL_WPS_MASTER_ORCHESTRATOR`, `VL_MAIN`, `connections.md`, `source-dataset-contract` (build_source_dataset.py) |
| 50 | 2026-10-28 22:04 | wf-2-migration-source-dataset | S4 | 🔵 change | Source dataset contract published: 27 tables, 0 consuming data products, ready=False |
| 51 | 2026-10-28 22:04 | wf-2-migration-source-dataset | S5 | ℹ️ note | Gap review: ⚠️ ready with warnings (0 ❌, 3 ⚠️, 0 ⚪), review/gap-review.md |
| 52 | 2026-10-28 22:04 | - | - | 🔵 change | Artifacts stored in the deployment repo `C:\Ten_Fabric_Data_Platform\fabric_deployment_repository\REPO-FABRIC-DEPLOYMENT` under `Platform-Hub/`: 1 files, 0 conflicts kept |
| 53 | 2026-10-28 22:09 | wf-2-migration-source-dataset | S1 | 🔵 change | Built `LH_SDS_WPS.Lakehouse` (build_source_dataset.py) |
| 54 | 2026-10-28 22:09 | wf-2-migration-source-dataset | S2 | 🔵 change | Built `PL_WPS_SOURCE_TO_RAW` (build_source_dataset.py) |
| 55 | 2026-10-28 22:09 | wf-2-migration-source-dataset | S3 | 🔵 change | Built `NB_WPS_RAW_TO_DELTA`, `PL_WPS_RAW_TO_DELTA` (build_source_dataset.py) |
| 56 | 2026-10-28 22:09 | wf-2-migration-source-dataset | S4 | 🔵 change | Built `PL_WPS_MASTER_ORCHESTRATOR`, `VL_MAIN`, `connections.md`, `source-dataset-contract` (build_source_dataset.py) |
| 57 | 2026-10-28 22:09 | wf-2-migration-source-dataset | S4 | 🔵 change | Source dataset contract published: 27 tables, 0 consuming data products, ready=True |
| 58 | 2026-10-28 22:09 | wf-2-migration-source-dataset | S5 | ⚠️ issue | Gap review: ❌ not ready (1 ❌, 2 ⚠️, 0 ⚪), review/gap-review.md |
| 59 | 2026-10-28 22:09 | - | - | 🔵 change | Artifacts stored in the deployment repo `C:\Ten_Fabric_Data_Platform\fabric_deployment_repository\REPO-FABRIC-DEPLOYMENT` under `Platform-Hub/`: 6 files, 0 conflicts kept |
| 60 | 2026-10-28 22:10 | wf-2-migration-source-dataset | S1 | 🔵 change | Built `LH_SDS_WPS.Lakehouse` (build_source_dataset.py) |
| 61 | 2026-10-28 22:10 | wf-2-migration-source-dataset | S2 | 🔵 change | Built `PL_WPS_SOURCE_TO_RAW` (build_source_dataset.py) |
| 62 | 2026-10-28 22:10 | wf-2-migration-source-dataset | S3 | 🔵 change | Built `NB_WPS_RAW_TO_DELTA`, `PL_WPS_RAW_TO_DELTA` (build_source_dataset.py) |
| 63 | 2026-10-28 22:10 | wf-2-migration-source-dataset | S4 | 🔵 change | Built `PL_WPS_MASTER_ORCHESTRATOR`, `VL_MAIN`, `connections.md`, `source-dataset-contract` (build_source_dataset.py) |
| 64 | 2026-10-28 22:10 | wf-2-migration-source-dataset | S4 | 🔵 change | Source dataset contract published: 27 tables, 0 consuming data products, ready=False |
| 65 | 2026-10-28 22:10 | wf-2-migration-source-dataset | S5 | ℹ️ note | Gap review: ⚠️ ready with warnings (0 ❌, 3 ⚠️, 0 ⚪), review/gap-review.md |
| 66 | 2026-10-28 22:18 | - | - | 🔵 change | Artifacts stored in the deployment repo `C:\Ten_Fabric_Data_Platform\fabric_deployment_repository\REPO-FABRIC-DEPLOYMENT` under `Platform-Hub/`: 0 files, 0 conflicts kept |
| 67 | 2026-10-28 22:18 | - | - | 🔵 change | Artifacts stored in the deployment repo `C:\Ten_Fabric_Data_Platform\fabric_deployment_repository\REPO-FABRIC-DEPLOYMENT` under `Platform-Hub/`: 2 files, 0 conflicts kept |
| 68 | 2026-10-28 22:19 | - | - | 🔵 change | Artifacts stored in the deployment repo `C:\Ten_Fabric_Data_Platform\fabric_deployment_repository\REPO-FABRIC-DEPLOYMENT` under `Platform-Hub/`: 1 files, 0 conflicts kept |
| 69 | 2026-10-29 13:52 | wf-2-migration-source-dataset | S5 | ℹ️ note | Gap review: ⚠️ ready with warnings (0 ❌, 2 ⚠️, 0 ⚪), review/gap-review.md |
| 70 | 2026-10-29 15:47 | wf-2-migration-source-dataset | S4 | 🔵 change | VL_MAIN generated: 10 variables, DEV / UAT / PRD, 18 values `<to set>` |
| 71 | 2026-10-29 15:47 | wf-2-migration-source-dataset | S1 | 🔵 change | Built `LH_SDS_WPS.Lakehouse` (build_source_dataset.py) |
| 72 | 2026-10-29 15:47 | wf-2-migration-source-dataset | S2 | 🔵 change | Built `PL_WPS_SOURCE_TO_RAW` (build_source_dataset.py) |
| 73 | 2026-10-29 15:47 | wf-2-migration-source-dataset | S3 | 🔵 change | Built `NB_WPS_RAW_TO_DELTA`, `PL_WPS_RAW_TO_DELTA` (build_source_dataset.py) |
| 74 | 2026-10-29 15:47 | wf-2-migration-source-dataset | S4 | 🔵 change | Built `PL_WPS_MASTER_ORCHESTRATOR`, `VL_MAIN`, `connections.md`, `source-dataset-contract` (build_source_dataset.py) |
| 75 | 2026-10-29 15:47 | wf-2-migration-source-dataset | S4 | 🔵 change | Source dataset contract published: 27 tables, 0 consuming data products, ready=True |
| 76 | 2026-10-29 15:47 | wf-2-migration-source-dataset | S5 | ℹ️ note | Gap review: ⚠️ ready with warnings (0 ❌, 2 ⚠️, 0 ⚪), review/gap-review.md |
| 77 | 2026-10-29 15:47 | - | - | 🔵 change | Artifacts stored in the deployment repo `C:\Ten_Fabric_Data_Platform\fabric_deployment_repository\REPO-FABRIC-DEPLOYMENT` under `Platform-Hub/`: 5 files, 0 conflicts kept |
| 78 | 2026-10-29 17:30 | - | - | ✅ completed | Gate vl_main_complete: ✅ completed (VL_MAIN synced from workspace to repo (fd7bc74, 888c79c); pipeline runs end to end in Fabric, 2026-10-29) |
| 79 | 2026-10-29 17:30 | - | - | ✔️ decision | batchCount raised to 40 in workspace and synced to repo; generator still writes 20. Decimals use numberScale 10 (lossless option pending). Copy tuning deferred. |
| 80 | 2026-10-29 17:30 | wf-2-migration-source-dataset | S5 | ✅ completed | Gap review and readiness: ✅ completed - gap review passed; deployed and pipeline runs end to end in Fabric, 2026-10-29 |

## Status definitions

| Status | Meaning |
| --- | --- |
| ✅ completed | Stage finished and its review passed, or gate met (evidence in the Evidence column). |
| 🟡 in progress | Started, not finished. The note says what is still pending. |
| ⚪ not started | Not started yet. |
| ⚠️ blocked | Cannot continue until an input, a decision or an ID arrives (the note names it). Also used to pause a project. |
| ⚫ n/a | Does not apply to this project. |

## Activity types

| Type | Meaning |
| --- | --- |
| 🟡 started | A project or a stage began. |
| ✅ completed | A stage finished or a gate was met. |
| ✔️ decision | The owner or developer chose something that changes the scope or the design. Decisions on one object are also in `2-config/migration/scope-decisions.json`. |
| ⚠️ issue | A problem, missing input, risk or failed check. It stays open until a later decision or completed entry resolves it. |
| 🔵 change | A script or agent generated or changed files (build, re-generation, fix). |
| ℹ️ note | Information recorded, such as an input received. No action needed. |
| ❌ rollback | An earlier change was undone. |
