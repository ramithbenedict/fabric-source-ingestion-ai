---
status: active
---

# F2 · Scope analysis

## Objective
Find every DPV1 object of the scope, with evidence, and map each one to its Fabric target.

## Input
- Service and identifier from F1.
- Skill: [skill-scope-resolution](../../1-skills/skill-scope-resolution/SKILL.md).

## Workflow Instructions
1. Run the framing script with the answers from F1. The domain, group and shared names are saved to `2-config/migration/` for later stages.
   - Source dataset: `python -I 0-shared/scripts/frame_scope.py --service sds --id <SOURCE> --domain <DOMAIN>`
   - Data product: `python -I 0-shared/scripts/frame_scope.py --service dp --id <PROJECT|MASTER|DW_SCHEMA> --group <GROUP>`
   - When the shared catalog warehouse becomes available, add once: `--catalog-warehouse <NAME> --catalog-location shared`.
2. Read `01-scope-analysis.md`. For each name-check object marked **not included**, open it in DPV1 and decide with the developer:
   - **in scope:** add it to the mapping by hand in `02-object-mapping.md`, with "Found by: manual review"
   - **out of scope:** write why in `03-target-design-and-plan.md` under "Analyst notes"
3. Read `02-object-mapping.md` and list every row whose action is `review`. Propose an action for each.
4. Summarise for the developer: size, complexity, entry points, related scopes, open points.

## Output
Rows marked `review` need an owner decision. Record it in `2-config/migration/scope-decisions.json` (action, reason, who, date) and log it with `track.py log --type decision`; every refresh then applies it.

`4-migration-project-deliverables/<source-dataset|data-product>/<project>/1-framing/`, three short pages and one reference page (the hub mapper shows the same trees):
- `01-scope-analysis.md`: scope card, identification and the name-check objects still to decide, as-is tree
- `02-object-mapping.md`: every DPV1 object, its evidence, action and Fabric target
- `03-target-design-and-plan.md`: to-be tree, decisions to confirm, VL_MAIN (DEV / UAT / PRD), migration plan, analyst notes
- `analysis/dpv1-inventory.md` (reference only): DPV1 pipelines, linked services, notebooks, datasets, SQL, the full name check, DPV1 environment values, Fabric items and what they replace

## Rules Checklist
- [ ] No name-check object left unexplained
- [ ] Every `review` row has a proposed action
- [ ] Related scopes (upstream / downstream) named in the summary
