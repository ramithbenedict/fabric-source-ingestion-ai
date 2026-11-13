## Example 11 — Row-by-Row Iteration (Cursor Replacement)

### Input

Instruction: "Iterate over each active project and run per-row processing logic."

### Context

Fabric Warehouse does not support T-SQL `CURSOR` (no `DECLARE CURSOR` / `OPEN` /
`FETCH` / `@@FETCH_STATUS` / `CLOSE` / `DEALLOCATE`). Prefer a set-based
operation whenever possible. When row-by-row logic is genuinely unavoidable,
replace the cursor with a `WHILE` loop over a numbered temp table.

### Output

```sql
-- Materialize the working set with a contiguous row number to iterate on
CREATE TABLE #PROJECTS_TO_PROCESS (
    [ITER_KEY]       BIGINT
    , [PROJECT_ID]   BIGINT
    , [PROJECT_CODE] VARCHAR(50)
)
;

INSERT INTO #PROJECTS_TO_PROCESS (
    [ITER_KEY]
    , [PROJECT_ID]
    , [PROJECT_CODE]
)
SELECT
    [ITER_KEY]       = ROW_NUMBER() OVER (ORDER BY prj.[PROJECT_ID])
    , [PROJECT_ID]   = prj.[PROJECT_ID]
    , [PROJECT_CODE] = prj.[PROJECT_CODE]
FROM
    [DBO].[DIM_PROJECT] AS prj
WHERE
    prj.[PROJECT_ACTIVE_FLAG] = 1
;

DECLARE @IterKey        BIGINT = 1
    , @MaxIterKey       BIGINT = (SELECT MAX([ITER_KEY]) FROM #PROJECTS_TO_PROCESS)
    , @CurrentProjectId BIGINT
    , @CurrentCode      VARCHAR(50)
;

WHILE @IterKey <= @MaxIterKey
BEGIN
    SELECT
        @CurrentProjectId = itr.[PROJECT_ID]
        , @CurrentCode    = itr.[PROJECT_CODE]
    FROM
        #PROJECTS_TO_PROCESS AS itr
    WHERE
        itr.[ITER_KEY] = @IterKey
    ;

    -- Per-row processing logic goes here, using @CurrentProjectId / @CurrentCode

    SET @IterKey = @IterKey + 1
    ;
END
;

DROP TABLE #PROJECTS_TO_PROCESS
;
```

### Notes

- `ROW_NUMBER()` guarantees a contiguous, gap-free key so the counter never
  skips a row. Never rely on `IDENTITY` here — it produces gaps.
- Always prefer converting the loop body into a single set-based statement first.
  A `WHILE` loop remains a last resort.
- Drop the temp table explicitly at the end even though it is session-scoped, to
  keep re-runnable batches clean.
