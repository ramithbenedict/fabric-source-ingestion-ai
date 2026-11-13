---
status: active
---

# S5 · Gap review and readiness

## Objective
Prove that every DPV1 element of the source is in DPV2, and that the items will deploy and run in Fabric.

## Input
- The whole project folder: `1-framing/`, `2-legacy-code/`, `3-build/`.
- Agents: [m-reviewer](../../.github/agents/m-reviewer.agent.md) (gap review), [m-bug-fixer](../../.github/agents/m-bug-fixer.agent.md).

## Workflow Instructions
1. Run the gap review: `python -I 0-shared/scripts/review_scope.py --service sds --id <SOURCE>`, then the agent's own checks (logic, deployment failures, lineage, bugs).
2. If there is a ❌ finding, run the m-bug-fixer (`fix_from_review.py`, then the manual fixes), and review again.
3. Repeat until the gate `gap_review_passed` is `✅ completed`.
4. Add the deployment checklist for the target workspace under the review: connections and gateway, VL_MAIN DEV values, catalog warehouse, schedule (not activated).

## Output
- `review/gap-review.md` and `.json`, `review/fix-log.md`, gate `gap_review_passed`, S5 `✅ completed`.

## Rules Checklist
- [ ] Coverage: every DPV1 object to migrate is built
- [ ] No ❌ finding left
- [ ] DPV1 per-table queries all in the catalog Lookup (none would silently run `SELECT *`)
- [ ] No hardcoded GUID, path or secret; no shortcut; no ADLS linked service
- [ ] Every dependency is in place before deployment (deployment-design.md, "Standard rule"): a fresh Git sync resolves VL_MAIN, item references and connections
