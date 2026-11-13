## Example 7 — Cross-Warehouse Query

### Input

Instruction: "Join cost facts with a reference table in another warehouse in the same workspace."

### Output

```sql
-- Three-part naming: <warehouse_or_lakehouse>.<schema>.<table>
-- Both items must be in the same workspace and same region
SELECT
    [COST_DATE]         = cst.[COST_DATE]
    , [COST_AMOUNT]     = cst.[COST_AMOUNT]
    , [REFERENCE_LABEL] = ref.[REFERENCE_LABEL]
FROM
    [DBO].[FACT_COST] AS cst
INNER JOIN
    [OTHER_WAREHOUSE].[DBO].[DIM_REFERENCE] AS ref
    ON  cst.[CURRENCY_CODE] = ref.[REFERENCE_CODE]
;
```
