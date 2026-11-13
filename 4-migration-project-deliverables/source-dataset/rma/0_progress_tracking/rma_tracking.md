# Tracking: RMA (Source dataset)

Last update: 2026-10-29

Sections: [ID card](#project-id-card) · [Stages](#workflow-and-stage-status) · [Gates](#mandatory-gates) · [Inputs](#inputs-received) · [Risks](#open-risks--blockers) · [Change log](#change-log) · [Definitions](#status-definitions)

## Project ID Card
- **Project name**: RMA
- **Service offering**: Source dataset
- **Domain**: FIN
- **Target**: `Platform-Hub` / `LH_SDS_RMA`
- **Source systems**: SqlServer
- **Ingestion**: Directly from the source: databases => Files/raw (parquet) => tables; APIs and files => Files/landing (as delivered) => Files/raw (parquet) => tables. No shortcut.
- **Complexity (repo)**: Medium (109 objects)
- **Register**: RMA (Small)
- **Owner**: TBD
- **Created on**: 2026-10-27
- **Last updated**: 2026-10-29

## Workflow and Stage Status
- **Completion**: 89%
- **Current stage**: S5

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
| S5 | `wf-2-migration-source-dataset` | Gap review and readiness | ⚠️ blocked | paused |

## Mandatory Gates

| Gate | Status | Evidence |
| --- | --- | --- |
| Framing approved by the owner | ✅ completed | Framing approved by the developer (gbadhani), 2026-10-27; VL_MAIN without IS_PROD and without warehouse CONN_ID |
| Name check: no "not included" object left | ✅ completed | 0 objects not included (01-scope-analysis.md) |
| Catalog view rows = DPV1 catalog script | ✅ completed | 18 view rows / 18 catalog script rows |
| VL_MAIN: no `<to set>` value for DEV | 🟡 in progress | DEV still to set: LH_SDS_RMA_ID, CATALOG_WAREHOUSE_ID, CATALOG_WAREHOUSE_CONN_ID, CATALOG_WAREHOUSE_SQL_ENDPOINT, RMA_LH_CONN_ID, RMA_SQL_SERVER_CONN_ID |
| Gap review: no ❌ finding left | ✅ completed | review/gap-review.md (2026-10-29) |

## Inputs Received

- [x] Domain: `FIN`
- [x] Workspace: `Platform-Hub`
- [x] Deployment repo: `C:\Ten_Fabric_Data_Platform\fabric_deployment_repository\REPO-FABRIC-DEPLOYMENT`
- [x] Service: `Source Dataset`
- [x] Name: `RMA`
- [x] Workspace folder: `Platform-Hub`
- [x] Catalog warehouse: `WH_CATALOG_COMMON`
- [x] Source dataset identifier: `RMA` (resolved from name)
- [x] Domain: `FIN`
- [x] Catalog warehouse: `WH_CATALOG_RMA`

## Open Risks / Blockers

- None identified yet

## Change Log

Chronological order: the first activity is at the top.

| # | Date | Workflow | Stage | Type | Activity |
| --- | --- | --- | --- | --- | --- |
| 1 | 2026-10-27 17:51 | - | - | 🟡 started | Source dataset migration started |
| 2 | 2026-10-27 17:51 | wf-1-framing | F1 | ✅ completed | Capture the request: ✅ completed |
| 3 | 2026-10-27 17:51 | wf-1-framing | F2 | 🟡 started | Scope analysis: 🟡 in progress - 1 name-check objects to confirm |
| 4 | 2026-10-27 17:58 | wf-1-framing | F2 | 🟡 started | Scope analysis: 🟡 in progress - resolve review rows, then mark completed |
| 5 | 2026-10-27 17:58 | - | - | ✔️ decision | Domain confirmed FIN by the developer. Target workspace Platform-Hub (not DP_SDS_FIN); artifacts stored in the Platform-Hub folder of the deployment repo. TR_RMA_DAILY: no trigger needed (product, owner decision 2026-10-27). |
| 6 | 2026-10-27 18:04 | wf-1-framing | F2 | 🔵 change | Framing pack generated in `1-framing/` (31 objects) |
| 7 | 2026-10-27 18:04 | wf-1-framing | F2 | 🟡 started | Scope analysis: 🟡 in progress - resolve review rows, then mark completed |
| 8 | 2026-10-27 18:04 | - | - | ✅ completed | Gate framing_approved: ✅ completed (Framing approved by the developer (gbadhani), 2026-10-27; VL_MAIN without IS_PROD and without warehouse CONN_ID) |
| 9 | 2026-10-27 18:04 | - | - | ✔️ decision | VL_MAIN: IS_PROD removed (environment value sets suffice); RMA_CATALOG_WAREHOUSE_CONN_ID removed (warehouse addressed by item id, SQL endpoint, workspace). Scripts, docs and framing pack updated. |
| 10 | 2026-10-27 18:06 | wf-1-framing | F2 | ✅ completed | Scope analysis: ✅ completed - approved 2026-10-27 |
| 11 | 2026-10-27 18:06 | wf-1-framing | F3 | ✅ completed | Target design: ✅ completed - approved 2026-10-27 |
| 12 | 2026-10-27 18:06 | wf-1-framing | F4 | ✅ completed | Migration plan and approval: ✅ completed - approved 2026-10-27 |
| 13 | 2026-10-27 18:06 | wf-2-migration-source-dataset | S1 | 🔵 change | Catalog view `[CATALOG].[rma_catalog]` generated in `WH_CATALOG_RMA`: 18 rows (18 active), from dpv1 |
| 14 | 2026-10-27 18:06 | wf-2-migration-source-dataset | S1 | 🔵 change | Built `LH_SDS_RMA.Lakehouse` (build_source_dataset.py) |
| 15 | 2026-10-27 18:06 | wf-2-migration-source-dataset | S1 | ✅ completed | Catalog view and Lakehouse: ✅ completed - catalog view 18 rows; LH_SDS_RMA built; pending review |
| 16 | 2026-10-27 18:09 | wf-2-migration-source-dataset | S2 | 🟡 started | Source to landing and RAW: 🟡 in progress |
| 17 | 2026-10-27 18:09 | wf-2-migration-source-dataset | S3 | 🟡 started | RAW to Lakehouse tables: 🟡 in progress |
| 18 | 2026-10-27 18:09 | wf-2-migration-source-dataset | S2 | 🔵 change | Built `PL_RMA_SOURCE_TO_RAW` (build_source_dataset.py) |
| 19 | 2026-10-27 18:09 | wf-2-migration-source-dataset | S3 | 🔵 change | Built `NB_RMA_RAW_TO_DELTA`, `PL_RMA_RAW_TO_DELTA` (build_source_dataset.py) |
| 20 | 2026-10-27 18:09 | wf-2-migration-source-dataset | S2 | 🔵 change | Legacy code extracted: 3 pipelines, 3 notebooks, 1 SQL scripts, 0 embedded T-SQL objects |
| 21 | 2026-10-27 18:09 | wf-2-migration-source-dataset | S2 | ✅ completed | Source to landing and RAW: ✅ completed - PL_RMA_SOURCE_TO_RAW built |
| 22 | 2026-10-27 18:09 | wf-2-migration-source-dataset | S3 | ✅ completed | RAW to Lakehouse tables: ✅ completed - NB_RMA_RAW_TO_DELTA, PL_RMA_RAW_TO_DELTA built |
| 23 | 2026-10-27 18:09 | wf-2-migration-source-dataset | S4 | 🟡 started | Orchestration and variable library: 🟡 in progress |
| 24 | 2026-10-27 18:15 | wf-2-migration-source-dataset | S3 | 🔵 change | Built `NB_RMA_RAW_TO_DELTA`, `PL_RMA_RAW_TO_DELTA` (build_source_dataset.py) |
| 25 | 2026-10-27 18:15 | wf-2-migration-source-dataset | S4 | 🔵 change | VL_MAIN generated: 8 variables, DEV / UAT / PRD, 15 values `<to set>` |
| 26 | 2026-10-27 18:15 | wf-2-migration-source-dataset | S5 | ℹ️ note | Gap review: ⚠️ ready with warnings (0 ❌, 2 ⚠️, 1 ⚪), review/gap-review.md |
| 27 | 2026-10-27 18:19 | wf-2-migration-source-dataset | S2 | 🔵 change | Built `PL_RMA_SOURCE_TO_RAW` (build_source_dataset.py) |
| 28 | 2026-10-27 18:19 | wf-2-migration-source-dataset | S4 | 🔵 change | Source dataset contract published: 18 tables, 2 consuming data products, ready=False |
| 29 | 2026-10-27 18:19 | wf-2-migration-source-dataset | S4 | 🔵 change | Built `PL_RMA_MASTER_ORCHESTRATOR`, `VL_MAIN`, `connections.md`, `source-dataset-contract` (build_source_dataset.py) |
| 30 | 2026-10-27 18:19 | wf-2-migration-source-dataset | S4 | ✅ completed | Orchestration and variable library: ✅ completed - reviewed: pass with warnings |
| 31 | 2026-10-27 18:19 | - | - | ✅ completed | Gate gap_review_passed: ✅ completed (S5: ready with warnings, 0 blockers) |
| 32 | 2026-10-27 18:19 | - | - | 🔵 change | Artifacts stored in the deployment repo `C:\Ten_Fabric_Data_Platform\fabric_deployment_repository\REPO-FABRIC-DEPLOYMENT` under `Platform-Hub/`: 20 files, 0 conflicts kept |
| 33 | 2026-10-27 18:37 | wf-2-migration-source-dataset | S4 | 🔵 change | VL_MAIN generated: 8 variables, DEV / UAT / PRD, 15 values `<to set>` |
| 34 | 2026-10-27 18:37 | - | - | 🔵 change | Artifacts stored in the deployment repo `C:\Ten_Fabric_Data_Platform\fabric_deployment_repository\REPO-FABRIC-DEPLOYMENT` under `Platform-Hub/`: 4 files, 0 conflicts kept |
| 35 | 2026-10-27 18:45 | wf-2-migration-source-dataset | S1 | 🔵 change | Built `LH_SDS_RMA.Lakehouse` (build_source_dataset.py) |
| 36 | 2026-10-27 18:45 | wf-2-migration-source-dataset | S3 | 🔵 change | Built `NB_RMA_RAW_TO_DELTA`, `PL_RMA_RAW_TO_DELTA` (build_source_dataset.py) |
| 37 | 2026-10-27 18:45 | wf-2-migration-source-dataset | S4 | 🔵 change | Built `PL_RMA_MASTER_ORCHESTRATOR`, `VL_MAIN`, `connections.md`, `source-dataset-contract` (build_source_dataset.py) |
| 38 | 2026-10-27 18:46 | - | - | 🔵 change | Artifacts stored in the deployment repo `C:\Ten_Fabric_Data_Platform\fabric_deployment_repository\REPO-FABRIC-DEPLOYMENT` under `Platform-Hub/`: 5 files, 0 conflicts kept |
| 39 | 2026-10-27 19:43 | wf-2-migration-source-dataset | S2 | 🔵 change | Built `PL_RMA_SOURCE_TO_RAW` (build_source_dataset.py) |
| 40 | 2026-10-28 16:54 | wf-2-migration-source-dataset | S5 | ⚠️ issue | Gap review and readiness: ⚠️ blocked - paused |
| 41 | 2026-10-28 17:40 | wf-2-migration-source-dataset | S1 | 🔵 change | Catalog view `[CATALOG].[rma_catalog]` generated in `WH_CATALOG_COMMON`: 18 rows (18 active), from dpv1 |
| 42 | 2026-10-28 17:41 | - | - | 🔵 change | Artifacts stored in the deployment repo `C:\Ten_Fabric_Data_Platform\fabric_deployment_repository\REPO-FABRIC-DEPLOYMENT` under `Platform-Hub/`: 7 files, 1 conflicts kept |
| 43 | 2026-10-28 17:42 | wf-2-migration-source-dataset | S4 | 🔵 change | VL_MAIN generated: 9 variables, DEV / UAT / PRD, 18 values `<to set>` |
| 44 | 2026-10-28 17:43 | - | - | 🔵 change | Artifacts stored in the deployment repo `C:\Ten_Fabric_Data_Platform\fabric_deployment_repository\REPO-FABRIC-DEPLOYMENT` under `Platform-Hub/`: 0 files, 1 conflicts kept |
| 45 | 2026-10-28 17:43 | wf-2-migration-source-dataset | S5 | ℹ️ note | Gap review: ⚠️ ready with warnings (0 ❌, 2 ⚠️, 0 ⚪), review/gap-review.md |
| 46 | 2026-10-28 17:43 | - | S1 | ✔️ decision | WH_CATALOG_RMA renamed WH_CATALOG_COMMON (same logicalId: Fabric renames the item); VL_MAIN uses COMMON_CATALOG_WAREHOUSE_* |
| 47 | 2026-10-28 17:43 | - | - | 🔵 change | Artifacts stored in the deployment repo `C:\Ten_Fabric_Data_Platform\fabric_deployment_repository\REPO-FABRIC-DEPLOYMENT` under `Platform-Hub/`: 0 files, 0 conflicts kept |
| 48 | 2026-10-28 17:44 | wf-2-migration-source-dataset | S4 | 🔵 change | Source dataset contract published: 18 tables, 2 consuming data products, ready=True |
| 49 | 2026-10-28 17:44 | wf-2-migration-source-dataset | S5 | ℹ️ note | Gap review: ⚠️ ready with warnings (0 ❌, 1 ⚠️, 0 ⚪), review/gap-review.md |
| 50 | 2026-10-28 17:49 | wf-2-migration-source-dataset | S4 | 🔵 change | VL_MAIN generated: 9 variables, DEV / UAT / PRD, 18 values `<to set>` |
| 51 | 2026-10-28 17:49 | wf-2-migration-source-dataset | S1 | 🔵 change | Catalog view `[CATALOG].[rma_catalog]` generated in `WH_CATALOG_COMMON`: 18 rows (18 active), from dpv1 |
| 52 | 2026-10-28 18:15 | wf-2-migration-source-dataset | S1 | 🔵 change | Built `LH_SDS_RMA.Lakehouse` (build_source_dataset.py) |
| 53 | 2026-10-28 18:15 | wf-2-migration-source-dataset | S2 | 🔵 change | Built `PL_RMA_SOURCE_TO_RAW` (build_source_dataset.py) |
| 54 | 2026-10-28 18:15 | wf-2-migration-source-dataset | S3 | 🔵 change | Built `NB_RMA_RAW_TO_DELTA`, `PL_RMA_RAW_TO_DELTA` (build_source_dataset.py) |
| 55 | 2026-10-28 18:15 | wf-2-migration-source-dataset | S4 | 🔵 change | Built `PL_RMA_MASTER_ORCHESTRATOR`, `VL_MAIN`, `connections.md`, `source-dataset-contract` (build_source_dataset.py) |
| 56 | 2026-10-28 18:15 | - | - | 🔵 change | Artifacts stored in the deployment repo `C:\Ten_Fabric_Data_Platform\fabric_deployment_repository\REPO-FABRIC-DEPLOYMENT` under `Platform-Hub/`: 7 files, 4 conflicts kept |
| 57 | 2026-10-28 18:15 | wf-2-migration-source-dataset | S4 | 🔵 change | Source dataset contract published: 18 tables, 2 consuming data products, ready=True |
| 58 | 2026-10-28 18:15 | wf-2-migration-source-dataset | S5 | ℹ️ note | Gap review: ✅ ready (0 ❌, 0 ⚠️, 0 ⚪), review/gap-review.md |
| 59 | 2026-10-28 18:23 | wf-2-migration-source-dataset | S4 | 🔵 change | VL_MAIN generated: 9 variables, DEV / UAT / PRD, 18 values `<to set>` |
| 60 | 2026-10-28 18:24 | - | - | 🔵 change | Artifacts stored in the deployment repo `C:\Ten_Fabric_Data_Platform\fabric_deployment_repository\REPO-FABRIC-DEPLOYMENT` under `Platform-Hub/`: 1 files, 0 conflicts kept |
| 61 | 2026-10-28 22:04 | wf-2-migration-source-dataset | S4 | 🔵 change | Built `PL_RMA_MASTER_ORCHESTRATOR`, `VL_MAIN`, `connections.md`, `source-dataset-contract` (build_source_dataset.py) |
| 62 | 2026-10-28 22:04 | wf-2-migration-source-dataset | S4 | 🔵 change | Source dataset contract published: 18 tables, 2 consuming data products, ready=True |
| 63 | 2026-10-28 22:04 | wf-2-migration-source-dataset | S5 | ⚠️ issue | Gap review: ❌ not ready (2 ❌, 1 ⚠️, 0 ⚪), review/gap-review.md |
| 64 | 2026-10-28 22:04 | wf-2-migration-source-dataset | S1 | 🔵 change | Built `LH_SDS_RMA.Lakehouse` (build_source_dataset.py) |
| 65 | 2026-10-28 22:04 | wf-2-migration-source-dataset | S2 | 🔵 change | Built `PL_RMA_SOURCE_TO_RAW` (build_source_dataset.py) |
| 66 | 2026-10-28 22:04 | wf-2-migration-source-dataset | S3 | 🔵 change | Built `NB_RMA_RAW_TO_DELTA`, `PL_RMA_RAW_TO_DELTA` (build_source_dataset.py) |
| 67 | 2026-10-28 22:04 | wf-2-migration-source-dataset | S4 | 🔵 change | Built `PL_RMA_MASTER_ORCHESTRATOR`, `VL_MAIN`, `connections.md`, `source-dataset-contract` (build_source_dataset.py) |
| 68 | 2026-10-28 22:04 | wf-2-migration-source-dataset | S4 | 🔵 change | Source dataset contract published: 18 tables, 2 consuming data products, ready=False |
| 69 | 2026-10-28 22:04 | wf-2-migration-source-dataset | S5 | ℹ️ note | Gap review: ⚠️ ready with warnings (0 ❌, 2 ⚠️, 0 ⚪), review/gap-review.md |
| 70 | 2026-10-28 22:04 | - | - | 🔵 change | Artifacts stored in the deployment repo `C:\Ten_Fabric_Data_Platform\fabric_deployment_repository\REPO-FABRIC-DEPLOYMENT` under `Platform-Hub/`: 1 files, 0 conflicts kept |
| 71 | 2026-10-28 22:09 | wf-2-migration-source-dataset | S1 | 🔵 change | Built `LH_SDS_RMA.Lakehouse` (build_source_dataset.py) |
| 72 | 2026-10-28 22:09 | wf-2-migration-source-dataset | S2 | 🔵 change | Built `PL_RMA_SOURCE_TO_RAW` (build_source_dataset.py) |
| 73 | 2026-10-28 22:09 | wf-2-migration-source-dataset | S3 | 🔵 change | Built `NB_RMA_RAW_TO_DELTA`, `PL_RMA_RAW_TO_DELTA` (build_source_dataset.py) |
| 74 | 2026-10-28 22:09 | wf-2-migration-source-dataset | S4 | 🔵 change | Built `PL_RMA_MASTER_ORCHESTRATOR`, `VL_MAIN`, `connections.md`, `source-dataset-contract` (build_source_dataset.py) |
| 75 | 2026-10-28 22:09 | wf-2-migration-source-dataset | S4 | 🔵 change | Source dataset contract published: 18 tables, 2 consuming data products, ready=True |
| 76 | 2026-10-28 22:09 | wf-2-migration-source-dataset | S5 | ⚠️ issue | Gap review: ❌ not ready (1 ❌, 1 ⚠️, 0 ⚪), review/gap-review.md |
| 77 | 2026-10-28 22:09 | - | - | 🔵 change | Artifacts stored in the deployment repo `C:\Ten_Fabric_Data_Platform\fabric_deployment_repository\REPO-FABRIC-DEPLOYMENT` under `Platform-Hub/`: 6 files, 0 conflicts kept |
| 78 | 2026-10-28 22:10 | wf-2-migration-source-dataset | S1 | 🔵 change | Built `LH_SDS_RMA.Lakehouse` (build_source_dataset.py) |
| 79 | 2026-10-28 22:10 | wf-2-migration-source-dataset | S2 | 🔵 change | Built `PL_RMA_SOURCE_TO_RAW` (build_source_dataset.py) |
| 80 | 2026-10-28 22:10 | wf-2-migration-source-dataset | S3 | 🔵 change | Built `NB_RMA_RAW_TO_DELTA`, `PL_RMA_RAW_TO_DELTA` (build_source_dataset.py) |
| 81 | 2026-10-28 22:10 | wf-2-migration-source-dataset | S4 | 🔵 change | Built `PL_RMA_MASTER_ORCHESTRATOR`, `VL_MAIN`, `connections.md`, `source-dataset-contract` (build_source_dataset.py) |
| 82 | 2026-10-28 22:10 | wf-2-migration-source-dataset | S4 | 🔵 change | Source dataset contract published: 18 tables, 2 consuming data products, ready=False |
| 83 | 2026-10-28 22:10 | wf-2-migration-source-dataset | S5 | ℹ️ note | Gap review: ⚠️ ready with warnings (0 ❌, 2 ⚠️, 0 ⚪), review/gap-review.md |
| 84 | 2026-10-28 22:10 | - | - | 🔵 change | Artifacts stored in the deployment repo `C:\Ten_Fabric_Data_Platform\fabric_deployment_repository\REPO-FABRIC-DEPLOYMENT` under `Platform-Hub/`: 1 files, 0 conflicts kept |
| 85 | 2026-10-28 22:19 | - | - | 🔵 change | Artifacts stored in the deployment repo `C:\Ten_Fabric_Data_Platform\fabric_deployment_repository\REPO-FABRIC-DEPLOYMENT` under `Platform-Hub/`: 0 files, 0 conflicts kept |
| 86 | 2026-10-29 13:52 | wf-2-migration-source-dataset | S5 | ℹ️ note | Gap review: ⚠️ ready with warnings (0 ❌, 1 ⚠️, 0 ⚪), review/gap-review.md |
| 87 | 2026-10-29 15:47 | wf-2-migration-source-dataset | S4 | 🔵 change | VL_MAIN generated: 10 variables, DEV / UAT / PRD, 18 values `<to set>` |
| 88 | 2026-10-29 15:47 | wf-2-migration-source-dataset | S1 | 🔵 change | Built `LH_SDS_RMA.Lakehouse` (build_source_dataset.py) |
| 89 | 2026-10-29 15:47 | wf-2-migration-source-dataset | S2 | 🔵 change | Built `PL_RMA_SOURCE_TO_RAW` (build_source_dataset.py) |
| 90 | 2026-10-29 15:47 | wf-2-migration-source-dataset | S3 | 🔵 change | Built `NB_RMA_RAW_TO_DELTA`, `PL_RMA_RAW_TO_DELTA` (build_source_dataset.py) |
| 91 | 2026-10-29 15:48 | wf-2-migration-source-dataset | S4 | 🔵 change | Built `PL_RMA_MASTER_ORCHESTRATOR`, `VL_MAIN`, `connections.md`, `source-dataset-contract` (build_source_dataset.py) |
| 92 | 2026-10-29 15:48 | wf-2-migration-source-dataset | S4 | 🔵 change | Source dataset contract published: 18 tables, 2 consuming data products, ready=True |
| 93 | 2026-10-29 15:48 | wf-2-migration-source-dataset | S5 | ℹ️ note | Gap review: ⚠️ ready with warnings (0 ❌, 1 ⚠️, 0 ⚪), review/gap-review.md |
| 94 | 2026-10-29 15:48 | - | - | 🔵 change | Artifacts stored in the deployment repo `C:\Ten_Fabric_Data_Platform\fabric_deployment_repository\REPO-FABRIC-DEPLOYMENT` under `Platform-Hub/`: 2 files, 0 conflicts kept |

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
