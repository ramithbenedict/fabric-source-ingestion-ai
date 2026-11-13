## Example 9 — Temp Tables

### Input

Instruction: "Create a staging temp table, load data into it, then add a column."

### Output

```sql
-- Session-scoped distributed #temp table
-- Dropped automatically at session end
CREATE TABLE #STAGING_PROJECTS (
    [PROJECT_CODE]      VARCHAR(50)
    , [PROJECT_NAME]    VARCHAR(200)
    , [PROJECT_START_DATE] DATE
    , [PROJECT_LOADED_TS]  DATETIME2(6)
)
;

INSERT INTO #STAGING_PROJECTS (
    [PROJECT_CODE]
    , [PROJECT_NAME]
    , [PROJECT_START_DATE]
    , [PROJECT_LOADED_TS]
)
SELECT
    [PROJECT_CODE]         = raw.[SOURCE_CODE]
    , [PROJECT_NAME]       = raw.[SOURCE_NAME]
    , [PROJECT_START_DATE] = raw.[SOURCE_START_DATE]
    , [PROJECT_LOADED_TS]  = SYSDATETIME()
FROM
    [DBO].[RAW_PROJECTS] AS raw
;

-- ALTER TABLE on distributed temp tables is supported
ALTER TABLE #STAGING_PROJECTS
    ADD [LOAD_BATCH_NK] BIGINT NULL
;
```
