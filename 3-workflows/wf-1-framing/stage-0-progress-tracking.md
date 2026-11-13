---
title: Stage 0 Migration Progress Tracking
description: Contract for creating and updating the progress tracking, change log and portfolio of a migration project. Applies to every workflow (wf-1 to wf-4).
---

## Objective

Keep one progress file and one change log per service offering and project, in the Fabric-AI-DEV-REPO format, so anyone can see where a migration stands and what changed.

## Input

- `<SERVICE>`: `sds` (Source Dataset Migration) or `dp` (Data Product Migration).
- `<PROJECT>`: the source name (sds) or the data product project (dp). Folder: `4-migration-project-deliverables/<source-dataset|data-product>/<PROJECT>/`.

## Global Instructions

- Never edit the tracking markdown by hand. Always use `python -I 0-shared/scripts/track.py`, which updates `progress.json` and renders the markdown.
- Every command takes `--service <SERVICE> --project <PROJECT>`.
- Status icons:
  - `✅ completed`
  - `🟡 in progress`
  - `⚪ not started`
  - `⚠️ blocked`
  - `⚫ n/a`
- Use the `Notes` cell only for `🟡 in progress` or `⚠️ blocked` stages, and only for blockers or decisions that need follow-up. Do not summarise completed work there.
- Each tracking file ends with the definition of every status and activity type (`track.py` `STATUS_MEANING`, `LOGTYPE_MEANING`).
- The scripts log their own activity (framing, catalog view, VL_MAIN, extraction, DACPAC, gap review). Agents log decisions, issues and stage status.

## Workflow Instructions

1. **First run:** `frame_scope.py` calls `track.py init`. Manually: `track.py init --service <SERVICE> --project <PROJECT>`.
2. **At the start of every stage:** `track.py set --service <SERVICE> --project <PROJECT> --stage <ID> --status in_progress`.
3. **At the end of every stage:**
   - Mark it completed: `track.py set … --status completed`. Only do this once its Rules Checklist passes.
   - If it cannot finish, mark it blocked instead: `track.py set … --status blocked --note "<blocker>"`.
4. **Decisions and issues:**
   - Record them as they happen: `track.py log … --stage <ID> --type decision|issue|note --text "<what>"`.
   - Open a risk with `track.py risk … --text "<risk>"`; close it with `track.py risk … --close "<risk>"`.
5. **Mandatory gates:** set them with `track.py gate … --gate <id> --status completed --evidence "<file or approver>"`. Some gates are set by scripts:
   - `name_check_resolved`: by frame_scope.py
   - `catalog_rows_match`: by create_catalog_view.py
   - `vl_main_complete`: by create_variable_library.py
   - `lint_zero_blocking`: by dacpac_retarget.py
   - `gap_review_passed`: by review_scope.py (m-reviewer, gap review)
6. **Inputs received from the developer:** `track.py input … --item "<input>"`.
7. **Status overview:** `track.py report [--service <SERVICE> --project <PROJECT>]`.

## Output

- Existing outputs: keep_existing_update_in_place
- Output artifacts, under `4-migration-project-deliverables/<source-dataset|data-product>/<PROJECT>/0_progress_tracking/`:
  - `<project>_tracking.md`: ID card, completion %, stage status, mandatory gates, inputs received, risks
  - `<project>_tracking.md#change-log`: every activity in **chronological order** (the first activity at the top), numbered
  - `progress.json`: state, generated
- Per service offering, under `4-migration-project-deliverables/<source-dataset|data-product>/`:
  - `progress_tracking.md`: every project of the service, stage by stage per workflow, plus gates and open risks
  - `change_log.md`: an index, one row per project (started, last activity, number of activities and decisions, open issues) linking to `<project>_tracking.md#change-log`, which holds every detail
- `4-migration-project-deliverables/migration-portfolio.md`: all projects of both services

## Output Interface

```markdown
# Progress Tracking: <PROJECT> (Source dataset)

Last update: <YYYY-MM-DD>

## Project ID Card
- **Project name**: <PROJECT>
- **Service offering**: Source dataset
- **Domain**: <DOMAIN>
- **Target**: `DP_SDS_<DOMAIN>_<ENV>` / `LH_SDS_<SOURCE>`
- **Ingestion**: Directly from the source: Files/landing => Files/raw (parquet) => tables. No shortcut.
- **Complexity (repo)**: <Small|Medium|High> (<N> objects)
- **Owner**: <OWNER>

## Workflow and Stage Status
- **Completion**: <PERCENTAGE>%
- **Current stage**: <ID>

| # | Workflow | Stage Name | Status | Notes |
| --- | --- | --- | --- | --- |
| F1 | `wf-1-framing` | Capture the request | ✅ completed | |

## Mandatory Gates
| Gate | Status | Evidence |
| --- | --- | --- |

## Inputs Received
- [x] <INPUT>

## Open Risks / Blockers
- ⚠️ <RISK>
```

## Mandatory gates

| Service | Gate id | Gate |
| --- | --- | --- |
| Source dataset | `framing_approved` | Framing approved by the owner |
| Source dataset | `name_check_resolved` | No "not included" object left |
| Source dataset | `catalog_rows_match` | Catalog view rows = DPV1 catalog script |
| Source dataset | `vl_main_complete` | No `<to set>` value for DEV |
| Source dataset | `gap_review_passed` | Gap review: no ❌ finding left |
| Data product | `framing_approved` | Framing approved by the owner |
| Data product | `name_check_resolved` | No "not included" object left |
| Data product | `sources_available` | Every input source dataset exists in Fabric |
| Data product | `lint_zero_blocking` | T-SQL lint: 0 blocking findings |
| Data product | `build_succeeds` | Database project builds |
| Data product | `vl_main_complete` | No `<to set>` value for DEV |
| Data product | `gap_review_passed` | Gap review: no ❌ finding left |

A service is ready for deployment only when every gate shows `✅ completed`.

## Rules Checklist

- [ ] Every stage start and end is recorded with `track.py set`
- [ ] Every decision and blocker is in the change log
- [ ] Notes are used only for in-progress or blocked stages
- [ ] No tracking markdown edited by hand
