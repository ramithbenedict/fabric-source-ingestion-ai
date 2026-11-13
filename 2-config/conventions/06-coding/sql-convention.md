---
description: TEN Fabric Platform SQL coding convention for Fabric Warehouse.
status: active
origin: master
---

# SQL Convention

## Identifiers

- Wrap in `[]` (SQL Server/Synapse) or `""` (PostgreSQL)
- Keywords: UPPERCASE
- Table/column names: UPPER_SNAKE_CASE

## Aliases

- Column alias: `[Alias] = src.[Column]` — use `=`, not `AS`
- Table alias: 3-letter trigram (`src`, `trg`, `stg`, `dim`, `cur`)
- Only alias a column when an operation is performed on it or if it's renamed. Do not alias a plain column reference where the alias would repeat the source column name.

```sql
-- GOOD
SELECT
    [EMPLOYEE_NAME] = emp.[NAME],
    [MANAGER_NAME] = mgr.[NAME]
FROM 
    [DW_HR].[EMPLOYEE_DIM] AS emp -- GOOD: alias matches trigram convention
LEFT JOIN
    [DW_HR].[EMPLOYEE_DIM] AS mgr
    ON  emp.[MANAGER_FK] = mgr.[EMPLOYEE_ID]


-- BAD
SELECT emp.EMPLOYEE_NAME AS EmployeeName FROM dbo.EMPLOYEE_DIM AS e -- BAD: alias is not a trigram, and column alias repeats source column name using AS instead of =
```

## Formatting

- Indent: 4 spaces, no tabs
- Commas: before column name (hanging)
- Each major clause (`SELECT`, `FROM`, `WHERE`, `ORDER BY`) on own line
- Align `=` vertically in SELECT lists
- End statements with `;`

```sql
SELECT
    cst.[CUSTOMER_ID]
    , cst.[NAME]
    , cst.[CREATED_DATE]
FROM
    [DBO].[CUSTOMER_DIM] AS cst
WHERE
    cst.[STATUS] = 'Active'
ORDER BY
    cst.[NAME] ASC
;
```

## JOINs

- Use `INNER JOIN`, not `JOIN`
- `ON` conditions on separate indented lines
- Left table left, right table right
- Multiple conditions: `AND` one per line

```sql
INNER JOIN
    [DBO].[ORDER_FACT] AS ord
    ON  cst.[CUSTOMER_ID] = ord.[CUSTOMER_FK]
    AND cst.[STATUS] = ord.[STATUS]
```

## CTEs

- Name: PascalCase, prefixed and suffixed with `_` (e.g., `_SourceData_`)
- Single-purpose per CTE
- Use CTEs only when inlining the logic in the main `SELECT` would produce complex subqueries or hard-to-read nesting. If a simple `WHERE` clause or a direct `JOIN` is sufficient, skip the CTE.

```sql
-- GOOD: CTE justified — the ranked subquery would be a complex inline subquery
WITH
_LatestOrderPerCustomer_ AS (
    SELECT
        ord.[CUSTOMER_FK]
        , ord.[ORDER_DATE]
        , ord.[TOTAL_AMOUNT]
        , [RN] = ROW_NUMBER() OVER (PARTITION BY ord.[CUSTOMER_FK] ORDER BY ord.[ORDER_DATE] DESC)
    FROM
        [DW_SALES].[ORDER_FACT] AS ord
)
SELECT
    [CUSTOMER_FK]   = lst.[CUSTOMER_FK]
    , [ORDER_DATE]  = lst.[ORDER_DATE]
    , [TOTAL_AMOUNT]= lst.[TOTAL_AMOUNT]
FROM
    _LatestOrderPerCustomer_ AS lst
WHERE
    lst.[RN] = 1
;

-- BAD: CTE adds no value — a plain SELECT with WHERE would be cleaner
WITH
_ActiveCustomers_ AS (
    SELECT
        [CUSTOMER_FK]   = cst.[CUSTOMER_FK]
        , [NAME]        = cst.[NAME]
    FROM
        [DW_SALES].[CUSTOMER_DIM] AS cst
    WHERE
        cst.[IS_ACTIVE] = 1
)
SELECT
    [CUSTOMER_FK]   = cst.[CUSTOMER_FK]
    , [NAME]        = cst.[NAME]
FROM
    _ActiveCustomers_ AS cst
;
```

## CREATE TABLE

- One column per line, comma before column name
- Align data types and NULL/NOT NULL vertically

```sql
-- Dimension table: IDENTITY PK first, natural key with UNIQUE constraint
CREATE TABLE [DBO].[DIM_PROJECT] (
    [PROJECT_ID]            BIGINT IDENTITY
    , [CODE_NK]             VARCHAR(50)     NOT NULL
    , [NAME]                VARCHAR(200)    NOT NULL
    , [START_DATE]          DATE
    , [CREATED_TS]          DATETIME2(0)
    , [UPDATED_TS]          DATETIME2(0)
)
;

-- Fact table: IDENTITY PK, FK references to dimension surrogate keys
CREATE TABLE [DBO].[FACT_COST] (
    [COST_ID]               BIGINT IDENTITY
    , [PROJECT_FK]          BIGINT          NOT NULL
    , [COST_DATE]           DATE            NOT NULL
    , [TOTAL_AMOUNT]        DECIMAL(19, 4)
    , [CURRENCY_CODE]       VARCHAR(3)
    , [CREATED_TS]          DATETIME2(0)
)
;
```

## WHERE

- One condition per line
- `AND`/`OR` at start of line
- `OR` can be inline if in parentheses
- Prefer `IN (...)` over OR for multiple values

```sql
WHERE
    cst.[STATUS] = 'Active'
    AND cst.[REGION] = 'EU'
    AND cst.[TYPE] IN ('A', 'B')
```

## Metadata Columns

| Column | Type |
|--------|------|
| `[META_PROCESSING_HASH_ALL_FIELDS]` | VARBINARY(32) |
| `[META_PROCESSING_CREATED_TS]` | DATETIME2(0) |
| `[META_PROCESSING_UPDATED_TS]` | DATETIME2(0) |
| `[META_IS_DELETED]` | BIT |
| `[META_DELETED_TS]` | DATETIME2(0) |

## Constraints
- Add PRIMARY KEY, FOREIGN KEY, and UNIQUE constraints even though they are not enforced in Fabric Warehouse — they serve as documentation and help query optimizers.
- Add UNIQUE constraints on natural/business keys that are unique.

## Dimensions
- **all** dimensions must have IDENTITY column. `<TABLE_NAME>_ID`. First column. Add PK constraint.

## Facts
- Use `_FK` suffix for foreign key columns in fact tables (e.g., `PROJECT_FK`). They reference the dimension's `_ID` (surrogate PK) column. Declare FOREIGN KEY constraints as NOT ENFORCED.

## CLUSTER BY strategy

- Only cluster tables with 50M+ records. Do not add `CLUSTER BY` to smaller tables.
- Choose columns that are **frequently filtered** and have **mid-to-high cardinality** (dates, business keys, natural keys). Avoid low-cardinality columns (flags, booleans, status codes) and purely descriptive attributes.
- Keep the number of keys small — each additional key reduces the benefit of every other key. **4 keys maximum** (engine hard limit).
- Clustering does not improve joins. Do not add a column solely because it appears in join predicates.
- IDENTITY columns are **not supported** in `CLUSTER BY`.
- Order of keys has no effect on query performance.

## Comments

- AI-generated: prefix with `-- AI COMMENT:`
- Explain **why**, not what

## Common Violations

| # | Bad | Fix |
|---|-----|-----|
| 1 | `select` | `SELECT` |
| 2 | `SELECT *` | List columns explicitly |
| 3 | `customers` | `[CUSTOMERS]` |
| 4 | `AS c` | Use trigram e.g. `cst` |
| 5 | `col AS Alias` | `[Alias] = tbl.[COL]` |
| 6 | `JOIN` | `INNER JOIN` |
| 7 | Missing `;` | Add `;` |
| 8 | `ON` on same line as `JOIN` | Move `ON` to next indented line |