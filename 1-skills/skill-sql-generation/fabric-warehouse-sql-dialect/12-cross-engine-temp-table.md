## Example 12 — Populating a Temp Table from a Cross-Engine Source

### Context

`INSERT INTO #temp ... SELECT` and `SELECT ... INTO #temp` **fail with
`Msg 15816 — The query references an object that is not supported in distributed
processing mode`** whenever the `SELECT` reads an object that runs *outside* the
local Warehouse's distributed engine: cross-database / cross-lakehouse tables
(three-part names, Lakehouse SQL endpoints, shortcut-backed tables read
cross-database) and system views. The cause is the cross-engine read — not the
temp table and not dynamic SQL, so wrapping it in `EXEC(@sql)` does **not** help.

**Workaround** — land the cross-engine rows into a **permanent work table** in
the local Warehouse first, scoped per session with `@@SPID`, then read from it.

### Output

```sql
-- Permanent work table lives in the local Warehouse (created once, in DDL).
-- CREATE TABLE [PRC].[DQ_EVAL_CNT_WORK] (
--       [SESSION_SPID]   BIGINT
--     , [REFERENCE_CODE]  VARCHAR(50)
--     , [REFERENCE_LABEL] VARCHAR(200)
-- );

-- Clear this session's rows before loading (defensive re-run cleanup)
DELETE FROM [PRC].[DQ_EVAL_CNT_WORK]
WHERE [SESSION_SPID] = @@SPID
;

-- Land the cross-engine source into the LOCAL permanent work table
INSERT INTO [PRC].[DQ_EVAL_CNT_WORK] (
    [SESSION_SPID]
    , [REFERENCE_CODE]
    , [REFERENCE_LABEL]
)
SELECT
    [SESSION_SPID]      = @@SPID
    , [REFERENCE_CODE]  = ref.[REFERENCE_CODE]
    , [REFERENCE_LABEL] = ref.[REFERENCE_LABEL]
FROM
    [OTHER_WAREHOUSE].[DBO].[DIM_REFERENCE] AS ref
;

-- Now the temp table can be populated from the LOCAL work table (same engine)
INSERT INTO #REFERENCE_STAGE (
    [REFERENCE_CODE]
    , [REFERENCE_LABEL]
)
SELECT
    [REFERENCE_CODE]    = wrk.[REFERENCE_CODE]
    , [REFERENCE_LABEL] = wrk.[REFERENCE_LABEL]
FROM
    [PRC].[DQ_EVAL_CNT_WORK] AS wrk
WHERE
    wrk.[SESSION_SPID] = @@SPID
;

-- Clean up this session's rows at the end of the procedure
DELETE FROM [PRC].[DQ_EVAL_CNT_WORK]
WHERE [SESSION_SPID] = @@SPID
;
```

### Notes

- Scope the work table per session with `@@SPID` and delete its rows at both the
  start and the end of the procedure so concurrent runs never collide.
- The work table must live in the **local** Warehouse — that is what keeps the
  temp-table load a same-engine read.
