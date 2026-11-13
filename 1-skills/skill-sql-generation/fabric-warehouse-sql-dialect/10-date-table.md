## Example 10 — Date Table

### Input

Instruction: "Create a date dimension table covering full calendar years, generated with a numbers cross join technique, with day/week/month/quarter/semester/year attributes as number, label, short label, and combination columns."

### Output

```sql
-- Pin session locale so weekday numbers and day/month names are deterministic:
--   DATEFIRST 1     -> Monday = 1 ... Sunday = 7 (DATEPART(WEEKDAY, ...))
--   LANGUAGE us_english -> English day/month names (DATENAME(...))
SET DATEFIRST 1;
SET LANGUAGE us_english;

-- Numbers generator: 10 rows cross joined 4x = 10,000 rows (enough for ~27 years of days)
-- Adjust start/end date and cross join count to cover the required date range
DECLARE @START_DATE DATE = '20200101';
DECLARE @END_DATE   DATE = '20291231'; -- always ends on 31-Dec; can be computed from fact data or NOW, i.e. `DATEFROMPARTS(YEAR(GETDATE()) + 1, 12, 31)`

WITH
[NUMBERS_1] AS (
    SELECT [N] FROM (VALUES (1),(2),(3),(4),(5),(6),(7),(8),(9),(10)) AS [T]([N])
)
, [NUMBERS] AS (
    SELECT
        [SEQUENCE_NUMBER] = ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) - 1
    FROM
        [NUMBERS_1] AS [A]
    CROSS JOIN 
        [NUMBERS_1] AS [B]
    CROSS JOIN
        [NUMBERS_1] AS [C]
    CROSS JOIN
        [NUMBERS_1] AS [D]
)
, [DATES] AS (
    SELECT
        [CALENDAR_DATE] = DATEADD(DAY, [SEQUENCE_NUMBER], @START_DATE)
    FROM
        [NUMBERS]
    WHERE
        DATEADD(DAY, [SEQUENCE_NUMBER], @START_DATE) <= @END_DATE
)
SELECT
    -- Date identifiers
    [DATE_ID]                 = CONVERT(INT, FORMAT([CALENDAR_DATE], 'yyyyMMdd'))
    , [CALENDAR_DATE]         = [CALENDAR_DATE]

    -- Day attributes
    , [DAY_NUMBER_IN_MONTH]   = DATEPART(DAY, [CALENDAR_DATE])
    , [DAY_NUMBER_IN_WEEK]    = DATEPART(WEEKDAY, [CALENDAR_DATE]) -- Monday = 1 ... Sunday = 7, assumes SET DATEFIRST 1 (see notes)
    , [DAY_NUMBER_IN_YEAR]    = DATEPART(DAYOFYEAR, [CALENDAR_DATE])
    , [DAY_LABEL]             = CONVERT(VARCHAR(20), DATENAME(WEEKDAY, [CALENDAR_DATE]))
    , [DAY_LABEL_SHORT]       = CONVERT(VARCHAR(3), LEFT(DATENAME(WEEKDAY, [CALENDAR_DATE]), 3))

    -- Week attributes
    , [WEEK_NUMBER]           = DATEPART(ISO_WEEK, [CALENDAR_DATE])
    , [WEEK_LABEL]            = CONCAT('Week ', DATEPART(ISO_WEEK, [CALENDAR_DATE]))
    , [WEEK_LABEL_SHORT]      = CONCAT('W', DATEPART(ISO_WEEK, [CALENDAR_DATE]))
    , [YEAR_WEEK_LABEL]       = CONCAT(YEAR([CALENDAR_DATE]), ' Week ', DATEPART(ISO_WEEK, [CALENDAR_DATE]))
    , [YEAR_WEEK_LABEL_SHORT] = CONCAT(YEAR([CALENDAR_DATE]), '-W', RIGHT(CONCAT('0', DATEPART(ISO_WEEK, [CALENDAR_DATE])), 2))
    , [YEAR_WEEK_LABEL_EXTRA_SHORT] = CONCAT(RIGHT(YEAR([CALENDAR_DATE]), 2), '-W', RIGHT(CONCAT('0', DATEPART(ISO_WEEK, [CALENDAR_DATE])), 2)) -- e.g. 26-W01
    , [YEAR_WEEK_LABEL_FINANCE] = CONCAT('W', RIGHT(CONCAT('0', DATEPART(ISO_WEEK, [CALENDAR_DATE])), 2), '''', RIGHT(YEAR([CALENDAR_DATE]), 2)) -- e.g. W01'26
    , [YEAR_WEEK_NUMBER]      = (YEAR([CALENDAR_DATE]) * 100) + DATEPART(ISO_WEEK, [CALENDAR_DATE]) -- sort key, e.g. 202601

    -- Month attributes
    , [MONTH_NUMBER]          = MONTH([CALENDAR_DATE])
    , [MONTH_LABEL]           = CONVERT(VARCHAR(20), DATENAME(MONTH, [CALENDAR_DATE]))
    , [MONTH_LABEL_SHORT]     = CONVERT(VARCHAR(3), LEFT(DATENAME(MONTH, [CALENDAR_DATE]), 3))
    , [YEAR_MONTH_LABEL]      = CONVERT(VARCHAR(30), CONCAT(YEAR([CALENDAR_DATE]), ' ', DATENAME(MONTH, [CALENDAR_DATE])))
    , [YEAR_MONTH_LABEL_SHORT] = CONVERT(VARCHAR(10), CONCAT(YEAR([CALENDAR_DATE]), '-', LEFT(DATENAME(MONTH, [CALENDAR_DATE]), 3))) -- e.g. 2020-Jan
    , [YEAR_MONTH_LABEL_EXTRA_SHORT] = CONVERT(VARCHAR(10), CONCAT(RIGHT(YEAR([CALENDAR_DATE]), 2), '-', LEFT(DATENAME(MONTH, [CALENDAR_DATE]), 3))) -- e.g. 26-Jan
    , [YEAR_MONTH_LABEL_FINANCE] = CONVERT(VARCHAR(10), CONCAT(LEFT(DATENAME(MONTH, [CALENDAR_DATE]), 3), '''', RIGHT(YEAR([CALENDAR_DATE]), 2))) -- e.g. Jan'26
    , [YEAR_MONTH_LABEL_YYYY_MM] = CONCAT(YEAR([CALENDAR_DATE]), '-', RIGHT(CONCAT('0', MONTH([CALENDAR_DATE])), 2)) -- e.g. 2020-01
    , [YEAR_MONTH_NUMBER]     = (YEAR([CALENDAR_DATE]) * 100) + MONTH([CALENDAR_DATE]) -- sort key, e.g. 202601

    -- Quarter attributes
    , [QUARTER_NUMBER]        = DATEPART(QUARTER, [CALENDAR_DATE])
    , [QUARTER_LABEL]         = CONCAT('Quarter ', DATEPART(QUARTER, [CALENDAR_DATE]))
    , [QUARTER_LABEL_SHORT]   = CONCAT('Q', DATEPART(QUARTER, [CALENDAR_DATE]))
    , [YEAR_QUARTER_LABEL]    = CONCAT(YEAR([CALENDAR_DATE]), ' Quarter ', DATEPART(QUARTER, [CALENDAR_DATE]))
    , [YEAR_QUARTER_LABEL_SHORT] = CONCAT(YEAR([CALENDAR_DATE]), '-Q', DATEPART(QUARTER, [CALENDAR_DATE]))
    , [YEAR_QUARTER_LABEL_EXTRA_SHORT] = CONCAT(RIGHT(YEAR([CALENDAR_DATE]), 2), '-Q', DATEPART(QUARTER, [CALENDAR_DATE])) -- e.g. 26-Q1
    , [YEAR_QUARTER_LABEL_FINANCE] = CONCAT('Q', DATEPART(QUARTER, [CALENDAR_DATE]), '''', RIGHT(YEAR([CALENDAR_DATE]), 2)) -- e.g. Q1'26
    , [YEAR_QUARTER_NUMBER]   = (YEAR([CALENDAR_DATE]) * 10) + DATEPART(QUARTER, [CALENDAR_DATE]) -- sort key, e.g. 20261

    -- Semester attributes
    , [SEMESTER_NUMBER]       = CASE WHEN MONTH([CALENDAR_DATE]) <= 6 THEN 1 ELSE 2 END
    , [SEMESTER_LABEL]        = CONCAT('Semester ', CASE WHEN MONTH([CALENDAR_DATE]) <= 6 THEN 1 ELSE 2 END)
    , [SEMESTER_LABEL_SHORT]  = CONCAT('S', CASE WHEN MONTH([CALENDAR_DATE]) <= 6 THEN 1 ELSE 2 END)
    , [YEAR_SEMESTER_LABEL]   = CONCAT(YEAR([CALENDAR_DATE]), ' Semester ', CASE WHEN MONTH([CALENDAR_DATE]) <= 6 THEN 1 ELSE 2 END)
    , [YEAR_SEMESTER_LABEL_SHORT] = CONCAT(YEAR([CALENDAR_DATE]), '-S', CASE WHEN MONTH([CALENDAR_DATE]) <= 6 THEN 1 ELSE 2 END)
    , [YEAR_SEMESTER_LABEL_EXTRA_SHORT] = CONCAT(RIGHT(YEAR([CALENDAR_DATE]), 2), '-S', CASE WHEN MONTH([CALENDAR_DATE]) <= 6 THEN 1 ELSE 2 END) -- e.g. 26-S1
    , [YEAR_SEMESTER_LABEL_FINANCE] = CONCAT('S', CASE WHEN MONTH([CALENDAR_DATE]) <= 6 THEN 1 ELSE 2 END, '''', RIGHT(YEAR([CALENDAR_DATE]), 2)) -- e.g. S1'26
    , [YEAR_SEMESTER_NUMBER]  = (YEAR([CALENDAR_DATE]) * 10) + CASE WHEN MONTH([CALENDAR_DATE]) <= 6 THEN 1 ELSE 2 END -- sort key, e.g. 20261

    -- Year attributes
    , [YEAR_NUMBER]           = YEAR([CALENDAR_DATE])
    , [YEAR_LABEL]            = CONCAT('Year ', YEAR([CALENDAR_DATE]))
    , [YEAR_LABEL_SHORT]      = RIGHT(YEAR([CALENDAR_DATE]), 2) -- last 2 digits, e.g. 26

    -- Flags
    , [IS_WEEKEND_FLAG]       = CASE WHEN DATEPART(WEEKDAY, [CALENDAR_DATE]) IN (6, 7) THEN 1 ELSE 0 END -- Saturday (6) or Sunday (7), assumes SET DATEFIRST 1
INTO [DBO].[DATE_DIM]
FROM
    [DATES]
;
```

### Notes

- Numbers generator: base `VALUES` of 10 rows cross joined 4× = up to 10,000 offsets (~27 years). Add/remove a `CROSS JOIN` to change the range.
- `@START_DATE` / `@END_DATE` span full calendar years (1-Jan to 31-Dec).
- `DATEPART(WEEKDAY, ...)`, `DATENAME(...)` are locale-dependent, so the batch pins the session up front: `SET DATEFIRST 1;` (Monday = 1 ... Sunday = 7) and `SET LANGUAGE us_english;` (English names). Keep both at the top of the enclosing stored procedure. Use `DATEPART(ISO_WEEK, ...)` for ISO-8601 week numbers.
- `YEAR_MONTH_LABEL_YYYY_MM` → `2020-01`; `YEAR_MONTH_LABEL_SHORT` → `2020-Jan`.
- `*_LABEL_FINANCE` labels use the financial `'YY` convention (apostrophe before the 2-digit year, standing in for the century): `W01'26`, `Jan'26`, `Q1'26`, `S1'26`. In SQL a literal apostrophe inside `CONCAT` is written as `''''`.
- `*_EXTRA_SHORT` labels put the 2-digit year first: `26-W01`, `26-Jan`, `26-Q1`, `26-S1`.
- Every year-combined level has an integer `YEAR_..._NUMBER` sort key (year first, e.g. `YEAR_MONTH_NUMBER` = `202601`) so labels — especially the `*_LABEL_FINANCE` variants — can be ordered chronologically without parsing the text.
- Each calendar level shares a column family: `_NUMBER`, `_LABEL`, `_LABEL_SHORT`, plus year-combined `YEAR_..._LABEL[_SHORT]` (e.g. `YEAR_QUARTER_LABEL_SHORT` = `2026-Q1`).
- CTAS is not supported; use `SELECT ... INTO` (see [CTAS](./02-ctas.md) / [SELECT ... INTO](./03-select-into.md)).
- `DATENAME`/`FORMAT` return `nvarchar` (a blocked type) and propagate it through `CONCAT`/`LEFT`/`RIGHT`; text columns derived from them are wrapped in `CONVERT(VARCHAR(n), ...)` so the `SELECT ... INTO` target stays `varchar`. See the [dialect blocked-types note](./_fabric-warehouse-sql-dialect.md).
