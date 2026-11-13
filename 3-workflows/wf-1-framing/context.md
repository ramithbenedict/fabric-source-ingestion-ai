# wf-1-framing

Every migration starts here. The developer says what to migrate; AI resolves the scope in DPV1, analyses it and writes the framing pack. Nothing is built in this workflow.

| Stage | File | Who | Output in `4-migration-project-deliverables/<source-dataset|data-product>/<PROJECT>/` |
|---|---|---|---|
| F0 | [stage-0-progress-tracking.md](stage-0-progress-tracking.md) | scripts + agents | `0_progress_tracking/` summary, change log; `migration-portfolio.md` |
| F1 | [stage-1-capture-request.md](stage-1-capture-request.md) | agent + developer | inputs in `0_progress_tracking/` |
| F2 | [stage-2-scope-analysis.md](stage-2-scope-analysis.md) | script + agent | `1-framing/01`–`03` + `analysis/dpv1-inventory.md` |
| F3 | [stage-3-target-design.md](stage-3-target-design.md) | agent + developer | `1-framing/03-target-design-and-plan.md` |
| F4 | [stage-4-migration-plan.md](stage-4-migration-plan.md) | agent + owner | `1-framing/03-target-design-and-plan.md`, gate `framing_approved` |

`<service>` is `source-dataset` or `data-product`. A project that has both runs F2–F4 once per service.

## Next workflow
- Source dataset => [wf-2-migration-source-dataset](../wf-2-migration-source-dataset/context.md)
- Data product => [wf-3-migration-data-product](../wf-3-migration-data-product/context.md). Dedicated-pool code also goes through [wf-4-migration-dacpac](../wf-4-migration-dacpac/context.md).

## Shared rules
- **One project migration at a time.** Framing and build scripts stop when another project (either service) has a stage in progress. Finish it, or pause it (`track.py set … --status blocked --note "paused"`). `--parallel` only when the owner agreed.
- **Source Dataset Migration** identifies, maps and builds only the objects of the source dataset and their lineage. Product steps reached from a source master are marked `product` and left to Data Product Migration; data products that read the source are listed for analysis only.
- **Data Product Migration** focuses on the product: its structure, its dependencies and how it interacts with other data products. It starts only when every source dataset it is produced from is migrated (source dataset contract published, S1-S4 completed). Otherwise the scripts stop before writing anything, name the missing sources, and the agent asks the developer to migrate them first; their objects are created in `source-dataset/<SOURCE>/` only.
- DPV1 is read-only. Path: `2-config/migration/paths.json` => `dpv1_export_root`.
- The scope comes from `5-migration-hub/migration-map.json`. Refresh it first if DPV1 changed: `python -I 0-shared/scripts/refresh_hub.py`.
- Naming follows `2-config/conventions`. Where a convention conflicts with a legacy name, the convention wins; record the rename in `03-target-design-and-plan.md`.
- Pause after each stage for the developer to confirm. Track every stage with `track.py` ([stage 0](stage-0-progress-tracking.md)).

## Parallel execution
| What runs in parallel | How |
| --- | --- |
| Framing of the source dataset and of the data product of the same project | Two framing runs (`--service sds`, `--service dp`); both write to the same progress file |
| Framing of several projects | Independent: one session per project; `migration-portfolio.md` shows them all |
| F2 review of name-check objects and `review` rows | One subagent per object type (pipelines, notebooks, SQL), results merged in `03-target-design-and-plan.md` |
