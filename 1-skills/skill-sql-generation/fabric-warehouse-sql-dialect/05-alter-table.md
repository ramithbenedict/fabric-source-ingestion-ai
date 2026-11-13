## Example 5 — ALTER TABLE

### Input

Instruction: "Add a nullable description column, add a nullable timestamp column, then drop the description."

### Output

```sql
-- ✅ ADD nullable column
ALTER TABLE [DBO].[DIM_PROJECT]
    ADD [PROJECT_DESCRIPTION] VARCHAR(500) NULL
;

-- ✅ ADD with explicit precision
ALTER TABLE [DBO].[DIM_PROJECT]
    ADD [PROJECT_ARCHIVED_TS] DATETIME2(6) NULL
;

-- ✅ DROP COLUMN
ALTER TABLE [DBO].[DIM_PROJECT]
    DROP COLUMN [PROJECT_DESCRIPTION]
;
```

### What Fails

```sql
-- ❌ ADD non-nullable column — FAILS
ALTER TABLE [DBO].[DIM_PROJECT]
    ADD [PROJECT_STATUS] VARCHAR(20) NOT NULL
;

-- ❌ ALTER COLUMN — preview only, not GA
ALTER TABLE [DBO].[DIM_PROJECT]
    ALTER COLUMN [PROJECT_NAME] VARCHAR(300)
;

-- ❌ Rename via ALTER TABLE — FAILS (use sp_rename)
```
