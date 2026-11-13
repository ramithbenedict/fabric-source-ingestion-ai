---
name: skill-tsql-dedicated-to-fabric
description: Translate Synapse Dedicated SQL Pool and serverless T-SQL to Fabric Warehouse T-SQL. The code stays T-SQL; intermediate serverless hops collapse into CTEs. Used by wf-3 D2 and wf-4 K3.
---

# skill-tsql-dedicated-to-fabric

**T-SQL stays T-SQL.** Never rewrite a table, view or procedure as a notebook. Apply the Fabric dialect rules in `1-skills/skill-sql-generation/` together with this skill. Check every result with `0-shared/scripts/tsql_fabric_lint.py`.

## Remove or replace
| Synapse | Fabric Warehouse |
|---|---|
| `WITH (DISTRIBUTION = …, HEAP, CLUSTERED COLUMNSTORE INDEX)`, indexes, partitions | remove |
| `CREATE EXTERNAL TABLE`, `OPENROWSET(BULK …)` | read `LH_INP_SDS_<SRC>.dbo.<table>` (three-part name) |
| CETAS (`CREATE EXTERNAL TABLE … AS SELECT`) | remove: the table or view is the output |
| `nvarchar` / `nchar` | `varchar` / `char` (UTF-8 collation) |
| `datetime`, `smalldatetime` | `datetime2(6)` |
| `money` | `decimal(19,4)` |
| `tinyint` | `smallint` |
| `IDENTITY` | follow skill-sql-generation; else `ROW_NUMBER()` + max key |
| `RENAME OBJECT` swap | `sp_rename`, or truncate + insert in a transaction |
| `USE <db>` | remove (database project) |

## Collapse the serverless hops
DPV1 chain: `inp_<x>` view => `ldw_<x>` view => CETAS `out.<t>` => `stg.<t>` => `dw_<x>.sp_*`.

Fabric: one silver load procedure.
1. Inline the INP and LDW logic as named CTEs, keeping the view names as CTE names.
2. Read the input Lakehouse instead of CLEANSED files or external tables.
3. Keep the DW procedure's load pattern (truncate-insert, merge, SCD2).
4. Drop the OUT and STG copies.

## Dynamic SQL
Pipelines like `SP_EXEC_SP_ALIM_DW_TABLES` loop over procedures by name. Keep the pattern only if it is still needed. Otherwise list the procedures explicitly in the pipeline (wf-3 D4).

## Output format
- One file per object: `<schema>.<object>.sql`.
- A header comment with the legacy objects absorbed and the behaviour changes.
- One line per object in `translation-log.md`.
