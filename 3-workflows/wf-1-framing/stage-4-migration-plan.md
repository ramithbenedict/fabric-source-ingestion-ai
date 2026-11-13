---
status: active
---

# F4 · Migration plan and gate

## Objective
Agree the build steps, prerequisites and open points, and get the owner's go-ahead.

## Input
- `1-framing/03-target-design-and-plan.md` (pre-filled by F2).

## Workflow Instructions
1. Complete the stage table for the matching build workflow:
   - wf-2: S1–S5
   - wf-3: D1–D6, plus wf-4 K1–K4 when dedicated-pool code exists
2. Prerequisites:
   - Data product: list each input source dataset and whether it already exists in Fabric. If one is missing, plan its wf-2 run first.
   - Source dataset: list the gateway and connections needed.
3. Add effort, risks and owner decisions under **Analyst notes**.
4. Ask the owner to approve. Record it: `track.py gate --service <sds|dp> --project <PROJECT> --gate framing_approved --evidence "<name>, <date>"`, then F4 `✅ completed`.

## Output
- `1-framing/03-target-design-and-plan.md` (completed).
- Gate `framing_approved` `✅ completed` in `0_progress_tracking/<project>_tracking.md`.

## Rules Checklist
- [ ] Every prerequisite has an owner or a planned run
- [ ] Key reference questions answered (`1-framing/04-key-reference-questions.md`): `reference_questions.py show --service <sds|dp> --id <NAME>` lists them with the evidence from DPV1 and the deployment repo; ask the open ones as multiple-choice lists (options given, recommended first, then Other) and record each with `reference_questions.py answer --q <ID> --text "..."`. Data product: gate `reference_questions_answered` blocks D1; source dataset: an open required question is a review warning
- [ ] Approval recorded before wf-2 / wf-3 starts
