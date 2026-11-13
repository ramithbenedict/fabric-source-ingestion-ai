---
name: skill-equivalence-tests
description: Paired DPV1 / Fabric SQL tests (row count, keys, checksum, KPI totals) proving migrated outputs match. Written in this phase, run in the later data phase. Used by wf-3 D5.
---

# skill-equivalence-tests

Every replaced output table or view gets four tests. Each is written once for DPV1 (`<object>.dpv1.sql`) and once for Fabric (`<object>.fabric.sql`), returning the same columns: `test_id, partition_key, metric, value`.

| Test | Query | Pass rule |
|---|---|---|
| T1 row count | `COUNT_BIG(*)` | equal |
| T2 keys | duplicate and null business keys | 0 on both sides |
| T3 checksum | `CHECKSUM_AGG(BINARY_CHECKSUM(<cols>))` per business month, with columns cast the same way on both sides | equal per partition |
| T4 KPI totals | `SUM(measure)`, `COUNT(DISTINCT key)` per month | difference ≤ documented tolerance |

- Cast before hashing: `varchar(4000)`, fixed decimal scale, `datetime2(0)`.
- Behaviour changes accepted in the translation log become exclusions in `test-plan.md`.
- **Never run these against production in this phase.**
