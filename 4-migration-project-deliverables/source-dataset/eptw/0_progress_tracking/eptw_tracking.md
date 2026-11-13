# Tracking: EPTW (Source dataset)

Last update: 2026-11-05

Sections: [ID card](#project-id-card) · [Stages](#workflow-and-stage-status) · [Gates](#mandatory-gates) · [Inputs](#inputs-received) · [Risks](#open-risks--blockers) · [Change log](#change-log) · [Definitions](#status-definitions)

## Project ID Card
- **Project name**: EPTW
- **Service offering**: Source dataset
- **Domain**: QHSES
- **Target**: `DP_SDS_QHSES_<ENV>` / `LH_SDS_EPTW`
- **Source systems**: RestService
- **Ingestion**: Directly from the source: databases => Files/raw (parquet) => tables; APIs and files => Files/landing (as delivered) => Files/raw (parquet) => tables. No shortcut.
- **Complexity (repo)**: Medium (117 objects)
- **Register**: EPTW (Medium)
- **Owner**: TBD
- **Created on**: 2026-11-02
- **Last updated**: 2026-11-05

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
| Framing approved by the owner | ✅ completed | Owner (gbadhani), 2026-11-02 |
| Name check: no "not included" object left | ✅ completed | 0 objects not included (01-scope-analysis.md) |
| Catalog view rows = DPV1 catalog script | ✅ completed | 26 view rows / 26 catalog script rows |
| VL_MAIN: no `<to set>` value for DEV | 🟡 in progress | DEV still to set: LH_SDS_EPTW_ID, CATALOG_WAREHOUSE_CONN_ID, EPTW_LH_CONN_ID, EPTW_REST_SERVICE_CONN_ID |
| Gap review: no ❌ finding left | ✅ completed | review/gap-review.md (2026-11-05) |

## Inputs Received

- [x] Domain: `QHSES`
- [x] Workspace: `DP_SDS_QHSES_DEV`
- [x] Deployment repo: `C:\Ten_Fabric_Data_Platform\fabric_deployment_repository\REPO-FABRIC-DEPLOYMENT`
- [x] Catalog warehouse: `WH_CATALOG_COMMON`
- [x] Service: `Source Dataset`
- [x] Name: `EPTW`
- [x] Workspace folder: `DP_SDS_QHSES`
- [x] Catalog ids: `{'DEV': {'workspace_name': 'DP_SDS_QHSES_DEV', 'workspace_id': '4796d818-bfb7-41cf-92f4-caed5743cf24', 'warehouse_name': 'WH_CATALOG_COMMON', 'warehouse_id': '95f828da-713b-4dfb-a003-ca2df46ae856', 'sql_endpoint': 'dlihtekm5geejnpqivklyr2prq-ddmjmr5xx7hudexuzlwvoq6peq.datawarehouse.fabric.microsoft.com'}}`
- [x] Source dataset identifier: `EPTW` (resolved from name)
- [x] Domain: `QHSES`
- [x] Catalog warehouse: `WH_CATALOG_COMMON`

## Open Risks / Blockers

- None identified yet

## Change Log

Chronological order: the first activity is at the top.

| # | Date | Workflow | Stage | Type | Activity |
| --- | --- | --- | --- | --- | --- |
| 1 | 2026-11-02 19:59 | - | - | 🟡 started | Source dataset migration started |
| 2 | 2026-11-02 19:59 | wf-1-framing | F2 | 🔵 change | Framing pack generated in `1-framing/` (31 objects) |
| 3 | 2026-11-02 19:59 | wf-1-framing | F1 | ✅ completed | Capture the request: ✅ completed |
| 4 | 2026-11-02 19:59 | wf-1-framing | F2 | 🟡 started | Scope analysis: 🟡 in progress - 5 name-check objects to confirm |
| 5 | 2026-11-02 20:23 | wf-1-framing | F2 | ⚠️ issue | Scope analysis: ⚠️ blocked - paused |
| 6 | 2026-11-02 20:32 | wf-1-framing | F2 | 🟡 started | Scope analysis: 🟡 in progress - resumed |
| 7 | 2026-11-02 20:32 | wf-1-framing | F2 | 🟡 started | Scope analysis: 🟡 in progress - resolve review rows, then mark completed |
| 8 | 2026-11-02 20:33 | wf-1-framing | F2 | 🟡 started | Scope analysis: 🟡 in progress - resolve review rows, then mark completed |
| 9 | 2026-11-02 20:56 | wf-1-framing | F2 | 🔵 change | Framing pack generated in `1-framing/` (48 objects) |
| 10 | 2026-11-02 20:56 | wf-1-framing | F2 | 🟡 started | Scope analysis: 🟡 in progress - resolve review rows, then mark completed |
| 11 | 2026-11-02 21:33 | - | - | ✅ completed | Gate framing_approved: ✅ completed (Owner (gbadhani), 2026-11-02) |
| 12 | 2026-11-02 21:33 | wf-1-framing | F4 | ✅ completed | Migration plan and approval: ✅ completed |
| 13 | 2026-11-02 21:33 | wf-1-framing | F1 | ✅ completed | Capture the request: ✅ completed |
| 14 | 2026-11-02 21:33 | wf-1-framing | F2 | ✅ completed | Scope analysis: ✅ completed |
| 15 | 2026-11-02 21:33 | wf-1-framing | F3 | ✅ completed | Target design: ✅ completed |
| 16 | 2026-11-02 21:33 | wf-2-migration-source-dataset | S1 | 🔵 change | Built `LH_SDS_EPTW.Lakehouse` (build_source_dataset.py) |
| 17 | 2026-11-02 21:33 | wf-2-migration-source-dataset | S2 | 🔵 change | Built `PL_EPTW_SOURCE_TO_RAW` (build_source_dataset.py) |
| 18 | 2026-11-02 21:33 | wf-2-migration-source-dataset | S3 | 🔵 change | Built `NB_EPTW_FLATTEN`, `NB_EPTW_RAW_TO_DELTA`, `PL_EPTW_RAW_TO_DELTA` (build_source_dataset.py) |
| 19 | 2026-11-02 21:33 | wf-2-migration-source-dataset | S4 | 🔵 change | Source dataset contract published: 26 tables, 2 consuming data products, ready=False |
| 20 | 2026-11-02 21:33 | wf-2-migration-source-dataset | S4 | 🔵 change | Built `PL_EPTW_MASTER_ORCHESTRATOR`, `VL_MAIN`, `connections.md`, `source-dataset-contract` (build_source_dataset.py) |
| 21 | 2026-11-02 21:33 | wf-2-migration-source-dataset | S5 | ℹ️ note | Gap review: ⚠️ ready with warnings (0 ❌, 1 ⚠️, 3 ⚪), review/gap-review.md |
| 22 | 2026-11-02 21:33 | wf-2-migration-source-dataset | S1 | 🔵 change | Catalog view `[CATALOG].[eptw_catalog]` generated in `WH_CATALOG_COMMON`: 26 rows (26 active), from dpv1; watermark table `catalog_eptw_watermark` |
| 23 | 2026-11-02 21:33 | wf-2-migration-source-dataset | S5 | ⚠️ issue | Gap review: ❌ not ready (1 ❌, 1 ⚠️, 1 ⚪), review/gap-review.md |
| 24 | 2026-11-02 21:34 | wf-2-migration-source-dataset | S1 | 🔵 change | Built `LH_SDS_EPTW.Lakehouse` (build_source_dataset.py) |
| 25 | 2026-11-02 21:34 | wf-2-migration-source-dataset | S2 | 🔵 change | Built `PL_EPTW_SOURCE_TO_RAW` (build_source_dataset.py) |
| 26 | 2026-11-02 21:34 | wf-2-migration-source-dataset | S3 | 🔵 change | Built `NB_EPTW_FLATTEN`, `NB_EPTW_RAW_TO_DELTA`, `PL_EPTW_RAW_TO_DELTA` (build_source_dataset.py) |
| 27 | 2026-11-02 21:34 | wf-2-migration-source-dataset | S4 | 🔵 change | Built `PL_EPTW_MASTER_ORCHESTRATOR`, `VL_MAIN`, `connections.md`, `source-dataset-contract` (build_source_dataset.py) |
| 28 | 2026-11-02 21:34 | wf-2-migration-source-dataset | S5 | ℹ️ note | Gap review: ⚠️ ready with warnings (0 ❌, 1 ⚠️, 1 ⚪), review/gap-review.md |
| 29 | 2026-11-02 21:35 | - | - | 🔵 change | Artifacts stored in the deployment repo `C:\Ten_Fabric_Data_Platform\fabric_deployment_repository\REPO-FABRIC-DEPLOYMENT` under `DP_SDS_QHSES/`: 23 files, 0 conflicts kept |
| 30 | 2026-11-02 21:35 | wf-2-migration-source-dataset | S5 | ℹ️ note | Gap review: ⚪ build not finished (0 ❌, 0 ⚠️, 1 ⚪), review/gap-review.md |
| 31 | 2026-11-02 21:35 | wf-2-migration-source-dataset | S1 | ✅ completed | Catalog view and Lakehouse: ✅ completed |
| 32 | 2026-11-02 21:35 | wf-2-migration-source-dataset | S2 | ✅ completed | Source to landing and RAW: ✅ completed |
| 33 | 2026-11-02 21:35 | wf-2-migration-source-dataset | S3 | ✅ completed | RAW to Lakehouse tables: ✅ completed |
| 34 | 2026-11-02 21:35 | wf-2-migration-source-dataset | S4 | ✅ completed | Orchestration and variable library: ✅ completed |
| 35 | 2026-11-02 21:35 | wf-2-migration-source-dataset | S5 | ✅ completed | Gap review and readiness: ✅ completed |
| 36 | 2026-11-02 21:35 | wf-2-migration-source-dataset | S4 | 🔵 change | Source dataset contract published: 26 tables, 2 consuming data products, ready=False |
| 37 | 2026-11-02 21:35 | wf-2-migration-source-dataset | S4 | 🔵 change | Source dataset contract published: 26 tables, 2 consuming data products, ready=False |
| 38 | 2026-11-03 17:07 | wf-2-migration-source-dataset | S1 | 🔵 change | Built `LH_SDS_EPTW.Lakehouse` (build_source_dataset.py) |
| 39 | 2026-11-03 17:07 | wf-2-migration-source-dataset | S2 | 🔵 change | Built `PL_EPTW_SOURCE_TO_RAW` (build_source_dataset.py) |
| 40 | 2026-11-03 17:07 | wf-2-migration-source-dataset | S3 | 🔵 change | Built `NB_EPTW_FLATTEN`, `NB_EPTW_RAW_TO_DELTA`, `PL_EPTW_RAW_TO_DELTA` (build_source_dataset.py) |
| 41 | 2026-11-03 17:08 | - | - | 🔵 change | Artifacts stored in the deployment repo `C:\Ten_Fabric_Data_Platform\fabric_deployment_repository\REPO-FABRIC-DEPLOYMENT` under `DP_SDS_QHSES/`: 7 files, 0 conflicts kept |
| 42 | 2026-11-05 11:18 | wf-2-migration-source-dataset | S4 | 🔵 change | Source dataset contract published: 26 tables, 2 consuming data products, ready=True |
| 43 | 2026-11-05 11:18 | wf-2-migration-source-dataset | S5 | ℹ️ note | Gap review: ⚠️ ready with warnings (0 ❌, 1 ⚠️, 0 ⚪), review/gap-review.md |
| 44 | 2026-11-05 11:26 | wf-2-migration-source-dataset | S4 | 🔵 change | VL_MAIN generated: 11 variables, DEV / UAT / PRD, 16 values `<to set>` |
| 45 | 2026-11-05 13:44 | wf-2-migration-source-dataset | S1 | 🔵 change | Catalog view `[CATALOG].[eptw_catalog]` generated in `WH_CATALOG_COMMON`: 26 rows (26 active), from dpv1; watermark table `catalog_eptw_watermark` |
| 46 | 2026-11-05 13:44 | - | - | 🔵 change | Artifacts stored in the deployment repo `C:\Ten_Fabric_Data_Platform\fabric_deployment_repository\REPO-FABRIC-DEPLOYMENT` under `DP_SDS_QHSES/`: 4 files, 0 conflicts kept |
| 47 | 2026-11-05 14:06 | wf-2-migration-source-dataset | S1 | 🔵 change | Built `LH_SDS_EPTW.Lakehouse` (build_source_dataset.py) |
| 48 | 2026-11-05 14:06 | wf-2-migration-source-dataset | S2 | 🔵 change | Built `PL_EPTW_SOURCE_TO_RAW`, `PL_EPTW_SOURCE_TO_RAW_CHILD_API` (build_source_dataset.py) |
| 49 | 2026-11-05 14:06 | wf-2-migration-source-dataset | S3 | 🔵 change | Built `NB_EPTW_FLATTEN`, `NB_EPTW_RAW_TO_DELTA`, `PL_EPTW_RAW_TO_DELTA` (build_source_dataset.py) |
| 50 | 2026-11-05 14:06 | wf-2-migration-source-dataset | S4 | 🔵 change | Built `PL_EPTW_MASTER_ORCHESTRATOR`, `VL_MAIN`, `connections.md`, `source-dataset-contract` (build_source_dataset.py) |
| 51 | 2026-11-05 14:07 | wf-2-migration-source-dataset | S4 | 🔵 change | Source dataset contract published: 26 tables, 2 consuming data products, ready=True |
| 52 | 2026-11-05 14:07 | wf-2-migration-source-dataset | S5 | ⚠️ issue | Gap review: ❌ not ready (1 ❌, 1 ⚠️, 0 ⚪), review/gap-review.md |
| 53 | 2026-11-05 14:07 | wf-2-migration-source-dataset | S4 | 🔵 change | Source dataset contract published: 26 tables, 2 consuming data products, ready=False |
| 54 | 2026-11-05 14:07 | wf-2-migration-source-dataset | S5 | ℹ️ note | Gap review: ⚠️ ready with warnings (0 ❌, 2 ⚠️, 0 ⚪), review/gap-review.md |
| 55 | 2026-11-05 14:07 | - | - | 🔵 change | Artifacts stored in the deployment repo `C:\Ten_Fabric_Data_Platform\fabric_deployment_repository\REPO-FABRIC-DEPLOYMENT` under `DP_SDS_QHSES/`: 8 files, 0 conflicts kept |
| 56 | 2026-11-05 14:17 | - | - | 🔵 change | Artifacts stored in the deployment repo `C:\Ten_Fabric_Data_Platform\fabric_deployment_repository\REPO-FABRIC-DEPLOYMENT` under `DP_SDS_QHSES/`: 6 files, 0 conflicts kept |
| 57 | 2026-11-05 14:25 | wf-2-migration-source-dataset | S1 | 🔵 change | Built `LH_SDS_EPTW.Lakehouse` (build_source_dataset.py) |
| 58 | 2026-11-05 14:25 | wf-2-migration-source-dataset | S2 | 🔵 change | Built `PL_EPTW_SOURCE_TO_RAW`, `PL_EPTW_SOURCE_TO_RAW_CHILD_API` (build_source_dataset.py) |
| 59 | 2026-11-05 14:25 | wf-2-migration-source-dataset | S3 | 🔵 change | Built `NB_EPTW_FLATTEN`, `NB_EPTW_RAW_TO_DELTA`, `PL_EPTW_RAW_TO_DELTA` (build_source_dataset.py) |
| 60 | 2026-11-05 14:25 | wf-2-migration-source-dataset | S4 | 🔵 change | Built `PL_EPTW_MASTER_ORCHESTRATOR`, `VL_MAIN`, `connections.md`, `source-dataset-contract` (build_source_dataset.py) |
| 61 | 2026-11-05 14:25 | wf-2-migration-source-dataset | S5 | ℹ️ note | Gap review: ⚠️ ready with warnings (0 ❌, 1 ⚠️, 0 ⚪), review/gap-review.md |
| 62 | 2026-11-05 14:25 | - | - | 🔵 change | Artifacts stored in the deployment repo `C:\Ten_Fabric_Data_Platform\fabric_deployment_repository\REPO-FABRIC-DEPLOYMENT` under `DP_SDS_QHSES/`: 9 files, 0 conflicts kept |
| 63 | 2026-11-05 14:29 | wf-2-migration-source-dataset | S1 | 🔵 change | Built `LH_SDS_EPTW.Lakehouse` (build_source_dataset.py) |
| 64 | 2026-11-05 14:29 | wf-2-migration-source-dataset | S2 | 🔵 change | Built `PL_EPTW_SOURCE_TO_RAW`, `PL_EPTW_SOURCE_TO_RAW_CHILD_API` (build_source_dataset.py) |
| 65 | 2026-11-05 14:29 | wf-2-migration-source-dataset | S3 | 🔵 change | Built `NB_EPTW_FLATTEN`, `NB_EPTW_RAW_TO_DELTA`, `PL_EPTW_RAW_TO_DELTA` (build_source_dataset.py) |
| 66 | 2026-11-05 14:29 | wf-2-migration-source-dataset | S4 | 🔵 change | Built `PL_EPTW_MASTER_ORCHESTRATOR`, `VL_MAIN`, `connections.md`, `source-dataset-contract` (build_source_dataset.py) |
| 67 | 2026-11-05 14:29 | wf-2-migration-source-dataset | S4 | 🔵 change | Source dataset contract published: 26 tables, 2 consuming data products, ready=True |
| 68 | 2026-11-05 14:29 | wf-2-migration-source-dataset | S5 | ⚠️ issue | Gap review: ❌ not ready (2 ❌, 1 ⚠️, 0 ⚪), review/gap-review.md |
| 69 | 2026-11-05 14:30 | wf-2-migration-source-dataset | S4 | 🔵 change | Source dataset contract published: 26 tables, 2 consuming data products, ready=False |
| 70 | 2026-11-05 14:30 | wf-2-migration-source-dataset | S5 | ℹ️ note | Gap review: ⚠️ ready with warnings (0 ❌, 2 ⚠️, 0 ⚪), review/gap-review.md |
| 71 | 2026-11-05 14:30 | - | - | 🔵 change | Artifacts stored in the deployment repo `C:\Ten_Fabric_Data_Platform\fabric_deployment_repository\REPO-FABRIC-DEPLOYMENT` under `DP_SDS_QHSES/`: 7 files, 0 conflicts kept |
| 72 | 2026-11-05 15:03 | wf-2-migration-source-dataset | S1 | 🔵 change | Built `LH_SDS_EPTW.Lakehouse` (build_source_dataset.py) |
| 73 | 2026-11-05 15:03 | wf-2-migration-source-dataset | S2 | 🔵 change | Built `PL_EPTW_SOURCE_TO_RAW`, `PL_EPTW_SOURCE_TO_RAW_CHILD_API` (build_source_dataset.py) |
| 74 | 2026-11-05 15:03 | wf-2-migration-source-dataset | S3 | 🔵 change | Built `NB_EPTW_FLATTEN`, `NB_EPTW_RAW_TO_DELTA`, `PL_EPTW_RAW_TO_DELTA` (build_source_dataset.py) |
| 75 | 2026-11-05 15:03 | wf-2-migration-source-dataset | S4 | 🔵 change | Built `PL_EPTW_MASTER_ORCHESTRATOR`, `VL_MAIN`, `connections.md`, `source-dataset-contract` (build_source_dataset.py) |
| 76 | 2026-11-05 15:03 | wf-2-migration-source-dataset | S5 | ℹ️ note | Gap review: ⚠️ ready with warnings (0 ❌, 1 ⚠️, 0 ⚪), review/gap-review.md |
| 77 | 2026-11-05 15:03 | - | - | 🔵 change | Artifacts stored in the deployment repo `C:\Ten_Fabric_Data_Platform\fabric_deployment_repository\REPO-FABRIC-DEPLOYMENT` under `DP_SDS_QHSES/`: 10 files, 0 conflicts kept |
| 78 | 2026-11-05 15:04 | wf-2-migration-source-dataset | S1 | 🔵 change | Built `LH_SDS_EPTW.Lakehouse` (build_source_dataset.py) |
| 79 | 2026-11-05 15:04 | wf-2-migration-source-dataset | S2 | 🔵 change | Built `PL_EPTW_SOURCE_TO_RAW`, `PL_EPTW_SOURCE_TO_RAW_CHILD_API` (build_source_dataset.py) |
| 80 | 2026-11-05 15:04 | wf-2-migration-source-dataset | S3 | 🔵 change | Built `NB_EPTW_FLATTEN`, `NB_EPTW_RAW_TO_DELTA`, `PL_EPTW_RAW_TO_DELTA` (build_source_dataset.py) |
| 81 | 2026-11-05 15:04 | wf-2-migration-source-dataset | S4 | 🔵 change | Built `PL_EPTW_MASTER_ORCHESTRATOR`, `VL_MAIN`, `connections.md`, `source-dataset-contract` (build_source_dataset.py) |
| 82 | 2026-11-05 15:04 | wf-2-migration-source-dataset | S4 | 🔵 change | Source dataset contract published: 26 tables, 2 consuming data products, ready=True |
| 83 | 2026-11-05 15:04 | wf-2-migration-source-dataset | S5 | ℹ️ note | Gap review: ⚠️ ready with warnings (0 ❌, 1 ⚠️, 0 ⚪), review/gap-review.md |
| 84 | 2026-11-05 15:04 | - | - | 🔵 change | Artifacts stored in the deployment repo `C:\Ten_Fabric_Data_Platform\fabric_deployment_repository\REPO-FABRIC-DEPLOYMENT` under `DP_SDS_QHSES/`: 10 files, 0 conflicts kept |

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
