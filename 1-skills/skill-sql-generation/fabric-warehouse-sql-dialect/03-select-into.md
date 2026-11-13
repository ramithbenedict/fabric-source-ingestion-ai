## Example 3 — SELECT INTO (DACPAC-Safe Alternative to CTAS)

### Input

Instruction: "Same as Example 2 but safe for SQL Database Project build."

### Output

```sql
SELECT
    [PROJECT_ID]            = prj.[PROJECT_ID]
    , [PROJECT_CODE]        = prj.[PROJECT_CODE]
    , [PROJECT_NAME]        = prj.[PROJECT_NAME]
    , [PROJECT_START_DATE]  = prj.[PROJECT_START_DATE]
    , [PROJECT_UPDATED_TS]  = CAST(prj.[PROJECT_UPDATED_TS] AS DATETIME2(6))
    , [PROJECT_ROW_HASH]    = prj.[PROJECT_ROW_HASH]
    , [PROJECT_ACTIVE_FLAG] = prj.[PROJECT_ACTIVE_FLAG]
INTO
    [DBO].[DIM_PROJECT_CLEAN]
FROM
    [DBO].[DIM_PROJECT] AS prj
WHERE
    prj.[PROJECT_ACTIVE_FLAG] = 1
;
```
