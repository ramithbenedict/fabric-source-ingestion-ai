---
status: active
---

# F1 · Capture the request

## Objective
Know exactly what the developer wants to migrate before any analysis.

## Input
- The developer's message. It may be a migration brief copied from the Migration Hub (`5-migration-hub/dpv1-fabric-migration-hub.html` => "Copy migration brief"). If it is, take the answers from the brief and skip the questions it already answers.

## Workflow Instructions
1. **Ask the five framing inputs, in this order, one question at a time.** Every question is a lettered list with the recommended answer first and `Z) Other`. Get the list from the script and show it as the question; never ask free text when a list exists. Ask all five even when a brief or the hub already gives a value (it becomes the recommendation).

   | # | Input | List from | Used for |
   | --- | --- | --- | --- |
   | 1 | **Service offering type** | `python -I 0-shared/scripts/framing_menu.py service` (Source Dataset / Data Product) | which workflow, and the project folder `4-migration-project-deliverables/source-dataset/` or `data-product/` |
   | 2 | **Domain name** | `framing_menu.py domain [--source <NAME>]`: the domain directory (`2-config/conventions/01-general/domains.md`), with `P&C => PC`; the hub's suggestion is recommended (data product: ask the data product group instead) | workspace and item names |
   | 3 | **Source / project name** | `framing_menu.py source --domain <CODE>` (data product: type the project, master pipeline or DW/DM schema) | scope in DPV1; the project folder (lowercase) created by F2 |
   | 4 | **Target workspace name** | `framing_menu.py workspace --service <sds\|dp> --domain <CODE>` | `workspace_folder` = the name without environment suffix = the folder in the deployment repo |
   | 5 | **Deployment repo path** | `framing_menu.py repo` (repositories found next to this one) | artifacts are also stored in `<path>/<workspace folder>/`; the path must exist |
   | 6 | **Common catalog warehouse** (source dataset only) | `framing_menu.py catalog --workspace <folder> --repo <path>`: "Is there a common warehouse that can store the catalog views of this source?" (recommended: `WH_CATALOG_COMMON`, reused when it exists) | `--common-catalog-warehouse <NAME>`: the view is created in that warehouse and VL_MAIN gets one `CATALOG_WAREHOUSE_*` set shared by all sources. `None` = own `WH_CATALOG_<SOURCE>` |
   | 7 | **Catalog workspace** (only when row 6 is not `None`) | `framing_menu.py catalog-workspace --workspace <target workspace> --repo <path>`: "In which workspace is the catalog warehouse?" (the real name with environment, e.g. `Platform-Hub_DEV`; the target workspace is the default) | `--catalog-workspace <NAME>`: a workspace other than the target adds `CATALOG_WAREHOUSE_WORKSPACE_ID` to VL_MAIN and the warehouse item is built in that workspace's folder. Then `resolve_catalog.py --id <SOURCE>` reads the workspace id, warehouse id and SQL endpoint from Fabric (cached) |

   - Once, if not set: the catalog warehouse in `2-config/migration/shared-platform.json` (today `WH_CATALOG_<SOURCE>`, one per source in its own workspace; later the shared warehouse, location `shared`).
   - Any answer outside the list (`Z`) is accepted in the developer's own format and normalised: domain codes keep only `A-Z`, `0-9`, `_`.
2. **Then verify.** A brief copied from the hub or a direct request may be out of date.
   - `python -I 0-shared/scripts/refresh_hub.py --check`. If it reports STALE, refresh first (`refresh_hub.py`, or the m-scope-refresher).
   - `python -I 0-shared/scripts/knowledge.py check --service <sds|dp> --id <NAME>` (exit 2: its DPV1 files changed, refresh), then `knowledge.py show` (dependencies, DPV1 objects, folder layout, owner decisions, status). Say where any difference between an answer and the hub comes from.
   - Save the answers with `frame_scope.py ... --domain <D> --workspace <W> --deployment-repo <PATH>` (F2 does it; they land in `0_progress_tracking/progress.json`). Do not start F2 while the workspace or the deployment repo path is missing.
3. **Data product only: prerequisite check, before anything else.** Run `python -I 0-shared/scripts/source_contract.py show --product <PROJECT>` (read-only).
   - Every input source is ✅ migrated: continue.
   - A source is not migrated, or not finished: stop. Tell the developer which source datasets the product is produced from and their state, and ask, as a multiple-choice question:
     - A) Migrate `<SOURCE>` first (start Source Dataset Migration for it, in `source-dataset/<SOURCE>/`)
     - B) Stop here
     - Z) Other
   - Only after the developer confirms A, run wf-1 then wf-2 for that source. Run the data product workflow again once all its sources are migrated. `frame_scope.py` enforces this and stops by itself.
4. Check the hub date in `5-migration-hub/refresh-report.md`. If DPV1 changed since then, or the developer asks for it, run `python -I 0-shared/scripts/refresh_hub.py`.
5. Record each answer with `track.py input --service <sds|dp> --project <PROJECT> --item "<answer>"` (tracking is created by F2 if it does not exist yet: `track.py init --service <sds|dp> --project <PROJECT>`).

## Output
- `0_progress_tracking/progress.json` (the five inputs) and the inputs listed under "Inputs Received" in `0_progress_tracking/<project>_tracking.md`.

## Rules Checklist
- [ ] Hub checked as current (`refresh_hub.py --check`); `knowledge.py check` says current; scope read with `knowledge.py show` (scenario, modifiers and, for a data product, the DACPAC code source noted)
- [ ] All five inputs asked and confirmed: service offering, domain (or group), source/project name, target workspace, deployment repo path (exists)
- [ ] Catalog warehouse name and location confirmed
- [ ] Hub data is current
- [ ] Data product: every input source dataset is migrated (contract ready), or the developer chose to migrate it first
