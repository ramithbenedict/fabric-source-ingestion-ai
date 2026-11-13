# wf-2-migration-source-dataset

Builds one source dataset in Fabric from an approved framing pack (`wf-1-framing`). In DPV1 the scope runs from the source to SPOT_DB source. In Fabric it becomes one Lakehouse in the domain's Source Data workspace, filled **directly from the source**.

```
Database ──Copy──────────────────────────────► Files/raw/<src>/<table>/          parquet, written once
API, files ─Copy──► Files/landing/<src>/<run>/ ──notebook──► Files/raw/<src>/<run>/<table>/
                                                 Tables (dbo)   one notebook per source (only where DPV1 had one). No cleansed zone.
```

- No shortcut in this service: the data is ingested from the source, never read from DPV1 ADLS.
- Shortcuts belong to the Data Product service: `LH_INP_SDS_<SOURCE>` in the product workspace exposes `LH_SDS_<SOURCE>` (wf-3 D3).
- **Source Dataset Migration** identifies, maps and builds only the objects of the source dataset and their lineage. Product steps reached from a source master are marked `product` and left to Data Product Migration; data products that read the source are listed for analysis only. Nothing of a data product is built here.
- S4 publishes `source-dataset-contract.json`: the hand-over to Data Product Migration (tables, DPV1 access paths, VL_MAIN names, consumers).
- DPV1 ADLS linked services and datasets are not migrated: OneLake is built into the Lakehouse and addressed by path.

| Stage | File | Output in `4-migration-project-deliverables/source-dataset/<SOURCE>/` |
|---|---|---|
| S0 | [wf-1 stage 0](../wf-1-framing/stage-0-progress-tracking.md) (one contract for all workflows) | `0_progress_tracking/` (every stage) |
| S1 | [stage-1-catalog-and-lakehouse.md](stage-1-catalog-and-lakehouse.md) | `3-build/fabric-deployment/DP_SDS_<DOMAIN>/WH_CATALOG_<SOURCE>.Warehouse/`, `3-build/fabric-deployment/DP_SDS_<DOMAIN>/<SOURCE>/LH_SDS_<SOURCE>.Lakehouse/` |
| S2 | [stage-2-source-to-raw.md](stage-2-source-to-raw.md) (methods: [ingestion-design.md](ingestion-design.md)) | `3-build/fabric-deployment/DP_SDS_<DOMAIN>/<SOURCE>/1-SOURCE_TO_RAW/` |
| S3 | [stage-3-raw-to-tables.md](stage-3-raw-to-tables.md) | `3-build/fabric-deployment/DP_SDS_<DOMAIN>/<SOURCE>/2-RAW_TO_DELTA/` |
| S4 | [stage-4-orchestration.md](stage-4-orchestration.md) | `3-build/fabric-deployment/DP_SDS_<DOMAIN>/<SOURCE>/0-ORCHESTRATION/`, `3-build/fabric-deployment/DP_SDS_<DOMAIN>/VL_MAIN.VariableLibrary/` |
| S5 | [stage-5-review.md](stage-5-review.md) | `review/gap-review.md` (m-reviewer, gap review), fixes by m-bug-fixer |

## Shared rules
- Workspace folder and deployment repo come from the framing inputs (`0_progress_tracking/progress.json`). After a stage review passes, run `python -I 0-shared/scripts/deploy_publish.py publish --service sds --id <NAME>`: the same tree is stored in `<deployment repo>/<workspace folder>/`.
- Start only when the gate `framing_approved` is `✅ completed` (`track.py report --service sds --project <SOURCE>`).
- Inputs:
  - `1-framing/02-object-mapping.md` and `03-target-design-and-plan.md`
  - the legacy code from `python -I 0-shared/scripts/extract_scope_code.py --service sds --id <SOURCE>`, written to `2-legacy-code/`
- Fabric items are written in Fabric Git format (`<ITEM>.<Type>/.platform` + content) under `3-build/fabric-deployment/`, the same layout as REPO-FABRIC-DEPLOYMENT (`2-config/conventions/01-general/fabric-git-repo-structure.md`, `02-fabric-workspace/6-workspace-sds-convention.md`): workspace folder without environment suffix, `VL_MAIN` and the catalog warehouse at its root, one folder per source with `0-ORCHESTRATION`, `1-SOURCE_TO_RAW`, `2-RAW_TO_DELTA` and the Lakehouse; what each stage did goes to `3-build/build-notes/`, so they can later be copied there unchanged.
- Every parameter comes from `VL_MAIN`: never hardcode a GUID, name, path or connection (`2-config/conventions/03-fabric-items/variable-library-convention.md`). Lakehouse and warehouse connections are VL expressions too (`artifactId`, `endpoint`, connection; workspace `@pipeline().DataFactory`), so every item deploys in one Git sync: [deployment-design.md](deployment-design.md).
- Every source (database, API, files; full or incremental): `python -I 0-shared/scripts/build_source_dataset.py --id <SOURCE>` generates S1 (Lakehouse), S2 and S3; the agent reviews the merge logs and adapts what the script reports as not generated.
- Track every stage start and end with `track.py` ([wf-1 stage 0](../wf-1-framing/stage-0-progress-tracking.md)); pause after each stage.

## Parallel execution
| When | What runs in parallel | How |
| --- | --- | --- |
| Build | S1 catalog view, S1 Lakehouse, `extract_scope_code.py` | Independent: run the scripts or subagents together |
| Build | S2 (source to RAW) and S3 (RAW to tables) | Both depend only on S1 and the catalog: one subagent each, then S4 |
| Portfolio | wf-2 for different sources | Sources are independent: one developer or agent session per source |
| Runtime | One Copy per catalog row in `PL_<SOURCE>_SOURCE_TO_RAW`; all tables in one notebook session | ForEach with `isSequential: false` and `batchCount` 10 |

S4 waits for S2 and S3, and S5 waits for S4. Record a parallel stage as `🟡 in progress` when it starts and `✅ completed` when it ends; the order of completion does not matter.
