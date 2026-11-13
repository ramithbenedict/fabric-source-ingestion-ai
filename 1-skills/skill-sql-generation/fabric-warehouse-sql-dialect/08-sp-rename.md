## Example 8 — sp_rename

### Input

Instruction: "Rename a column, then rename a table."

### Output

```sql
-- Rename a column
EXEC sp_rename 'DBO.DIM_PROJECT.PROJECT_NAME', 'PROJECT_LABEL', 'COLUMN'
;

-- Rename a table
EXEC sp_rename 'DBO.DIM_PROJECT', 'DIM_PROJECT_V2'
;
```
