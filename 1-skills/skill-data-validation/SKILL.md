---
name: skill-data-validation
description: Live DPV1 => DPV2 data validation of a migrated project (inventory, schema, row count, column profile, keys, full or random-row data compare, deployment drift, view health). Read-only on both sides, connections from the VS Code MSSQL profiles. Used by wf-5 and the m-data-validator.
---

# skill-data-validation

Proves, on live data, that the Fabric objects of a project hold the same data as their DPV1 objects. `skill-equivalence-tests` (wf-3 D5) writes paired SQL tests; this skill runs a full comparison with `0-shared/scripts/validate_data.py` and explains the gaps.

## What is compared
| Service | DPV1 side | Fabric side | Pairs |
| --- | --- | --- | --- |
| Data product (`dp`) | dedicated SQL pool: `DW_<P>` (silver), `DM_<P>` (gold) | Warehouse `WH_DPG_<P>`: `OUT_SILV_<P>` tables, `OUT_GOLD_<P>` views | same object name per layer |
| Source dataset (`sds`) | serverless SQL pool, lake database `spot_<src>` (`dbo`) | Lakehouse SQL analytics endpoint `LH_SDS_<SRC>` (`dbo`) | `source-dataset-contract.json` tables |

The layers come from the database project (`CREATE SCHEMA`) or the contract and are saved in `validation-config.json`; edit them there if a project differs. STG and PROJ objects are not compared: they are collapsed into the silver loads (wf-3).

## Levels
Every level runs all the tests; the level sets how deep the content tests go. Set `settings.level` in `validation-config.json`, or `run --level`.

| Level | Row-by-row data (T5) | Column profile (T4) | Time budget | Use |
| --- | --- | --- | --- | --- |
| **quick** (default) | 50 random rows per object | NULLs, min, max, sum, lengths (no distinct counts) | 5 min (run ends ~5-7 min) | high-level check after each load, ~5-7 min |
| standard | every row up to 20 000 rows, else 200 random rows | + distinct counts up to 1 M rows | 20 min | before UAT sign-off |
| deep | every row up to 100 000 rows, else 500 random rows | + distinct counts up to 5 M rows | none | before go-live, on demand (can take over an hour) |

After the time budget, the remaining objects get only the cheap tests (T1-T3, T6); the report names how many.

## Checks
| ID | Category | Test | Pass rule | Fails when |
| --- | --- | --- | --- | --- |
| T1 | 🏗️ Structure | Object inventory | every DPV1 object of the layer has a Fabric object | missing in Fabric (❌), extra in Fabric (⚠️) |
| T2 | 🏗️ Structure | Schema | same columns; type changes imposed by Fabric are ℹ️ (nvarchar => varchar, datetime => datetime2, money => decimal...) | column missing (❌), incompatible type (❌), shorter text, lower precision, NULL => NOT NULL (⚠️) |
| T3 | 📊 Volume | Row count | `COUNT_BIG(*)` equal | empty Fabric (❌), difference above `row_count_tolerance_pct` |
| T4 | 🔬 Content | Column profile | per column: NULLs, distinct, min, max, sum (numbers), min/max length (text) | values differ with the same row count (❌) |
| T5 | 🔬 Content | Row-by-row data | every row compared when both sides have ≤ `full_compare_max_rows` rows, else `sample_rows` random DPV1 keys (`ORDER BY NEWID()`) | rows missing, column values different (❌; trim, case, precision only: ⚠️) |
| T6 | 🔑 Integrity | Keys | no duplicate, no NULL key in Fabric beyond DPV1 (primary keys are NOT ENFORCED in Fabric) | duplicates or NULL keys (❌) |
| T7 | ⏱️ Freshness | Data freshness | max of the change-date column (`LastModified`, `ModifiedDate`...) on both sides | Fabric older: reload. Fabric newer: see the snapshot rule below |
| T8 | 🚀 Deployment | Warehouse = database project (dp) | every object of the database project exists in the Warehouse | not deployed (❌), not in the repo (⚠️) |
| T9 | 🚀 Deployment | Views run (dp) | `SELECT TOP 0 *` runs on every Warehouse view | broken view (❌) |

**Key**: from `validation-config.json` `objects.<name>.key`, else the Fabric primary key, the DPV1 primary key, the key of the same object in the other layer, or an `Id` / `<Object>Id` column. Without a key, small tables are compared as whole rows; large ones are not compared (⚠️).

**Snapshot rule**: when Fabric holds newer data than DPV1, a Fabric row whose change date is after the DPV1 maximum is "changed after the snapshot". It is counted, not reported as a gap. Only rows unchanged since the snapshot can fail the data check.

**Normalisation before comparing**: trailing spaces ignored (`trim_strings`); date-times equal within the coarser precision of both types (`datetime` 3.33 ms, `datetime2(0)` 1 s); decimals within half a unit of the smaller scale; floats within `float_rel_tolerance`; binary compared as hex; `bit` as 0/1.

## Nature of a finding
Every finding also gets a nature, so real migration gaps stand apart from noise:

| Nature | When | What to do |
| --- | --- | --- |
| 🔴 Migration gap | structure, keys, deployment, views; or data differences with the same environment and freshness | fix (agent or manual), validate again |
| 🟡 Data timing / environment | row count, profile or data differences while the environments differ or the change dates differ | no code fix; re-run on the same environment, loaded the same day |
| ⚪ Platform behaviour | collation (case-sensitive Fabric), Fabric-imposed types | check joins, filters and consumers |
| 🔵 Accepted | matches `accepted_differences` | none |

The verdict is driven by the 🔴 findings. The report (`validation-report.md`) has a scorecard by test (§1), findings by nature (§2), results per object by category (§3), migration gaps grouped by category (§4), timing/environment differences (§5), platform and accepted differences (§6), improvements (§7), environment (§8), and the agent's analysis (§9, kept when the report is regenerated).

## Conclusion: rating and readiness
The report opens with a conclusion so a reader can decide without reading the details.

**Rating /100 and grade**: the share of tests without a 🔴 migration finding (⚠️ counts half), weighted by category. Weights: 🏗️ Structure 30, 🔬 Content 25, 📊 Volume 15, 🔑 Integrity 15, 🚀 Deployment 15. Only assessable categories count: Content and Volume are not assessable across environments, Deployment only on a full run. The report says how many categories were scored. Grades: A ≥ 95 Excellent · B ≥ 85 Good · C ≥ 70 Fair · D ≥ 50 Poor · E < 50 Bad.

**Readiness for the upper environment** (first rule that applies):
| Decision | When |
| --- | --- |
| 🔴 NOT READY | Fabric is empty, or at least one 🔴 ❌ migration gap. The blocking points are listed by ID with their fix. |
| ⚪ NOT DECIDED | partial run (`--only`), or the deployment and view checks did not run |
| 🟡 READY WITH CONDITIONS | no blocking gap, but the environments differ (data tests to confirm) or 🔴 ⚠️ warnings remain to review |
| 🟢 READY | no migration gap, same environment, full run |

**Confidence**: High (same environment, full compare) · Medium (different environments, or large tables sampled) · Low (partial run).

## Status
✅ pass · ⚠️ warning (does not block) · ❌ gap (blocks sign-off) · ℹ️ expected difference · 🟦 accepted difference (owner decision in `accepted_differences`) · ⚪ not run

Verdict: ❌ if any ❌, ⚠️ if any ⚠️, else ✅. "Fabric is not loaded yet" when every Fabric object is empty.

**Environments**: the data verdict needs both profiles to read the same environment and the same load (e.g. DPV1 UAT against Fabric UAT, both loaded the same day). When they differ, the report says so at the top. Row counts and data are then indicative only; inventory, schema, keys, deployment and view checks remain valid.

## Reading a gap: likely cause => fix
| Finding | Likely cause | Fix | Owner |
| --- | --- | --- | --- |
| Object missing in Fabric | not built, not deployed, renamed | build in the database project, run the DACPAC pipeline, or map the name in `objects` | agent / manual |
| Column missing, incompatible type | translation dropped or retyped it | fix the table or view in `database-projects/DPG-<P>/` | agent |
| Fabric empty | load not run or failed | run `PL_<P>_PROCESS_DATA_PRODUCT` (or the source pipeline), read its run | manual |
| Rows differ, Fabric older | different load dates | load both sides the same day, validate again | manual |
| Rows differ, same freshness | filter or join of the load differs | compare the load procedure with the DPV1 procedure | agent |
| Duplicate keys in Fabric | load is not idempotent | delete or merge before insert in the load procedure | agent |
| Values differ (value) | column expression changed | align the expression with DPV1 (examples in `analysis/validation-details.md`) | agent |
| Values differ (case, whitespace, precision) | cast, trim or collation | accept it or align the cast | agent / owner |
| Distinct count differs on text only | DPV1 collation is case-insensitive, Fabric `Latin1_General_100_BIN2_UTF8` is case-sensitive | check joins and filters on text | manual |
| View does not run | reads a column or object that does not exist | fix the view, redeploy | agent |

## Rules
- Read-only on both sides: the script refuses anything but `SELECT` / `WITH`. Never run against production without the owner's agreement.
- Connections come only from the VS Code MSSQL extension profiles (`mssql.connections` in VS Code `settings.json`), Microsoft Entra sign-in in the browser; no password, token or connection string in a file.
- An accepted difference always has a reason, usually an owner decision already in `scope-decisions.json` or `backlog.md`.
- The validation writes only to `<project>/data-validation/`; it never changes a deliverable.
