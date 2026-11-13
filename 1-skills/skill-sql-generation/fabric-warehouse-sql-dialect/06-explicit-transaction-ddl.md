## Example 6 — Explicit Transaction with DDL

### Input

Instruction: "Atomically add two columns and drop one in a single migration."

### Output

```sql
BEGIN TRAN;

    ALTER TABLE [DBO].[DIM_PROJECT]
        ADD [PROJECT_REGION_CODE] VARCHAR(10) NULL
    ;

    ALTER TABLE [DBO].[DIM_PROJECT]
        ADD [PROJECT_COUNTRY_CODE] VARCHAR(3) NULL
    ;

    ALTER TABLE [DBO].[DIM_PROJECT]
        DROP COLUMN [PROJECT_ACTIVE_FLAG]
    ;

COMMIT;
-- If any statement fails, all changes roll back
```

### What Cannot Run Inside a Transaction

```sql
-- ❌ ADD non-nullable column
-- ❌ ALTER COLUMN
-- ❌ ALTER on non-distributed temp tables
```
