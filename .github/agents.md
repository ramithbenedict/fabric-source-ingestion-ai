# Agent guide

Eight agents. Start with one of the two **service agents**, or the **data validator** once a project is deployed and loaded; they call the specialists for you. In VS Code Copilot Chat, pick the agent and click its handoff buttons. In Claude Code, read the agent file and follow it, using subagents where it says so. Stage files stay the source of truth.

## Entry points: one per service offering
| Agent | Use it to | Runs | Writes to |
| --- | --- | --- | --- |
| 📦 [m-source-dataset](agents/m-source-dataset.agent.md) | Migrate one source end to end | knowledge check => wf-1 => wf-2 S1-S4 => S5 review and fixes => contract | `4-migration-project-deliverables/source-dataset/<SOURCE>/` |
| 🏗️ [m-data-product](agents/m-data-product.agent.md) | Migrate one data product end to end, after its sources | source readiness => wf-1 => wf-3 D1-D5 (+ wf-4 DACPAC) => D6 review and fixes | `4-migration-project-deliverables/data-product/<PROJECT>/` |

## Specialists: one job each
| Agent | Purpose | Writes to |
| --- | --- | --- |
| 🔄 [m-scope-refresher](agents/m-scope-refresher.agent.md) | On demand: refresh the hub, the knowledge base and the scope index from DPV1; verify them; answer dependencies | `5-migration-hub/` |
| 🧭 [m-framer](agents/m-framer.agent.md) | wf-1 framing F1-F4: scope, trees, plan, owner decisions and approval | `1-framing/`, `0_progress_tracking/`, `scope-decisions.json` |
| 🛠️ [m-builder](agents/m-builder.agent.md) | One build stage of wf-2, wf-3 or wf-4 | `2-legacy-code/`, `3-build/`, `4-dacpac/`, contract |
| 🔎 [m-reviewer](agents/m-reviewer.agent.md) | Stage review, or gap review of a whole migration | `3-build/build-notes/build-notes.md#<stage>-review`, `review/` |
| 🩹 [m-bug-fixer](agents/m-bug-fixer.agent.md) | Apply the fixes of the latest review | the files named in the review, `review/fix-log.md` |

## Standalone: data validation
| Agent | Use it to | Runs | Writes to |
| --- | --- | --- | --- |
| 🧪 [m-data-validator](agents/m-data-validator.agent.md) | Compare the data of a migrated source dataset or data product, DPV1 => DPV2, live and read-only, and report the gaps with cause, fix and owner | wf-5 V1-V3 (`validate_data.py`), any time after deployment and load | `<project>/data-validation/` |

## Flow
```
m-data-validator ──► profiles (MSSQL extension) ──► V1 setup ──► V2 run ──► V3 analysis ──► bug-fixer (agent gaps) ⇄ validator (--only)

m-source-dataset ──► refresher (if stale) ──► framer F1-F4 ──► builder S1..S4 ──► reviewer (each stage)
                                                                         └──► reviewer (gap, S5) ⇄ bug-fixer ──► contract published

m-data-product ──► sources ready? ──no──► m-source-dataset (per missing source)
                              │yes
                              └──► framer F1-F4 ──► builder D1..D5 (+ wf-4 K1-K4) ──► reviewer (gap, D6) ⇄ bug-fixer
```

## Where the facts come from
1. `5-migration-hub/knowledge/<sds|dp>/<NAME>.json`: what the hub knows about a scope (objects, mapping, lineage, trees, folder layout, decisions, DPV1 files). Read with `knowledge.py show`.
2. `knowledge.py check`: says whether those DPV1 files changed since the last refresh. If yes, refresh first.
3. Only then open DPV1 files, and only the ones the knowledge lists (`extract_scope_code.py` copies them to `2-legacy-code/`).

## Framing inputs and the deployment repo
Framing always asks five inputs: service offering type, domain name, source or project name, target workspace name, deployment repo path. They are saved in `0_progress_tracking/progress.json`. The project folder `4-migration-project-deliverables/<source-dataset|data-product>/<NAME>/` is the working copy; the m-builder publishes the same tree to `<deployment repo>/<workspace folder>/` after each passing stage review (`deploy_publish.py`).

## Tracking
Every stage is tracked with `track.py`. The status and activity types are defined at the end of each `<project>_tracking.md` and `<project>_tracking.md#change-log`.
