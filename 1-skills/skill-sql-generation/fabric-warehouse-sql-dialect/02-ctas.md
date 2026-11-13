## Example 2 — CTAS

### Input

Instruction: "Create a clean copy of the project dimension keeping only active rows."

### Output

```sql
-- ⚠️ Works at runtime but NOT recognized by Microsoft.Build.Sql
-- ⚠️ DACPAC build will fail — use SELECT INTO instead (see Example 3)
CREATE TABLE [DBO].[DIM_PROJECT_CLEAN]
AS
SELECT
    [PROJECT_ID]            = prj.[PROJECT_ID]
    , [PROJECT_CODE]        = prj.[PROJECT_CODE]
    , [PROJECT_NAME]        = prj.[PROJECT_NAME]
    , [PROJECT_START_DATE]  = prj.[PROJECT_START_DATE]
    , [PROJECT_UPDATED_TS]  = CAST(prj.[PROJECT_UPDATED_TS] AS DATETIME2(6))
    , [PROJECT_ROW_HASH]    = prj.[PROJECT_ROW_HASH]
    , [PROJECT_ACTIVE_FLAG] = prj.[PROJECT_ACTIVE_FLAG]
FROM
    [DBO].[DIM_PROJECT] AS prj
WHERE
    prj.[PROJECT_ACTIVE_FLAG] = 1
;
```
