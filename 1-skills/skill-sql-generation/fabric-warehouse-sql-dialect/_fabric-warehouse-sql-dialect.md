# Fabric Warehouse T-SQL — What's Different

This document describes the differences and specificities of the T-SQL dialect and features used in Fabric Warehouse compared to standard SQL.

## Rules

### Blocked Data Types

| Blocked | Use instead |
|---|---|
| `tinyint` | `smallint` |
| `money`, `smallmoney` | `decimal` |
| `datetime`, `smalldatetime` | `datetime2` |
| `datetimeoffset` | `datetime2` + `AT TIME ZONE` |
| `nchar`, `nvarchar` | `char`, `varchar` (UTF-8) |
| `text`, `ntext` | `varchar` |
| `image` | `varbinary` |
| `json` | `varchar` |
| `xml` | — |
| `geography`, `geometry` | `varbinary` (WKB) / `varchar` (WKT) |
| CLR types | — |

- `datetime2` / `time`: precision **0–6 only**. **Always specify it** (`datetime2(6)`, `time(0)`). Unspecified = defaults to 7 at DACPAC build = deploy fails.
- `IDENTITY`columns must be `BIGINT` only. 
- `varchar(max)`, `varbinary(max)`: 16 MB cap.
- `uniqueidentifier`: stored as binary, unreadable outside Warehouse.
- Hashes: use `varbinary`, not `varchar`. Native `HASHBYTES` return type, smaller, faster.
- **Implicit `nvarchar` trap**: some built-ins return `nvarchar` even when inputs are not — notably `DATENAME`, `FORMAT`, `SPACE`, `STR`, and `N'...'` literals. `CONCAT`, `COALESCE`, `LEFT`, `RIGHT`, `SUBSTRING`, `REPLACE` propagate `nvarchar` when any argument is `nvarchar`. In `SELECT ... INTO` / CTAS this silently materializes a blocked `nvarchar` column. Wrap the final expression in `CONVERT(VARCHAR(n), ...)` to force a `varchar` target.

### DDL

- All DDL must be in its own batch. Every DDL statement must be followed by `GO` on its own line.
- **ALTER TABLE**: only `ADD` nullable column, `DROP COLUMN`, `ADD`/`DROP` constraint with `NOT ENFORCED`, `ALTER COLUMN` (preview).
- **Constraints**: `PK`, `UNIQUE`, `FK` — cannot be defined inline within `CREATE TABLE`. Must be added via `ALTER TABLE ... ADD CONSTRAINT` after table creation. `PK` and `UNIQUE` require `NONCLUSTERED` and `NOT ENFORCED`. `FK` requires `NOT ENFORCED`. Never enforced — metadata only.
- **IDENTITY**: `BIGINT` only (`BIGINT IDENTITY` is the full syntax — never `INTEGER IDENTITY`). No seed/increment. No `IDENTITY_INSERT`. No `ALTER TABLE ADD`. Cannot be included in `CLUSTER BY`. Values are positive only, unique, but **with gaps** and **not guaranteed to reflect insertion order**.
- **No indexes**.
- Cluster cannot use an IDENTITY field. Identity column does not control row ordering.
- **No sequences**.
- Schema/table names: no `/` or `\`.

### CLUSTER BY key selection

`CLUSTER BY` physically orders the data and speeds up filtered scans. Adding the wrong keys wastes write cost with no read benefit. Apply these rules when deciding the cluster key:
- Only cluster tables with 50M+ records. Do not add `CLUSTER BY` to smaller tables.
- Choose only columns that are frequently filtered and have mid-to-high cardinality (e.g., dates, business keys). Avoid low-cardinality flags and descriptive attributes.
- Keep the number of keys small — each additional key reduces the benefit of every other key. **4 keys maximum (engine hard limit).**
- Clustering does not improve joins. Do not add a column to the cluster key just because it is often used in join predicates.
- IDENTITY column are unsupported in `CLUSTER BY`. 
- Order of keys has no effect.


### Unsupported Commands

`BULK LOAD`, `CREATE USER`, `FOR XML`, `FOR JSON` in subqueries, `PREDICT`, `SET ROWCOUNT`, `SET TRANSACTION ISOLATION LEVEL`, `sp_showspaceused`, `CURSOR`,  multi-column stats, materialized views, recursive CTEs, synonyms, triggers.

- **Cursors**: `CURSOR` is not supported. Rewrite cursor-based iteration as a set-based operation, or, when row-by-row logic is unavoidable, as a `WHILE` loop over a table.

### Transactions

- Snapshot isolation only, not configurable.
- Table-level locking only.
- First committer wins; concurrent writers rolled back.
- No distributed transactions, save points, named/marked transactions.
- Inside explicit transactions: no non-nullable `ADD`, no `ALTER COLUMN`, no `ALTER` on non-distributed temp tables.

### Surrogate keys

#### Default case
Use `BIGINT IDENTITY` for surrogate keys. Values are positive, unique across the table, but contain gaps and are not guaranteed to reflect insertion order — treat them as opaque unique identifiers only.

#### Case requiring controlled values for surrogate keys
If a target table must retain fixed, externally-controlled surrogate keys (i.e., the key value is meaningful and must survive reloads, e.g. `0` for `Unknown` in a dimension), don't use a Fabric IDENTITY column at all (IDENTITY_INSERT Not supported).
  - For tiny tables with hardcoded values: use a plain BIGINT and generate keys yourself (hash of the business key, ROW_NUMBER() over an ordered load). Reserve IDENTITY for cases where the surrogate key is truly opaque and only needs to be unique within the warehouse.
  - For large tables, accept that the surrogate ID will be random and put/use the controlled value in another column (source surrogate key, source business key).

### DACPAC Build-Time Traps

- **CTAS not recognized** by `Microsoft.Build.Sql`. Use `SELECT ... INTO`.
- **`datetime2`/`time` without precision** → defaults to 7 → deploy fails.
- Favor`EXEC(@sql)` instead of `EXEC sp_executesql @sql`. Otherwise, DACPAC deploy fails.

### Performance

- Constraints not enforced → don't trust them for join uniqueness.
- Match data types on join columns exactly — implicit conversions kill perf.
- Keep transactions short — DDL locks contend on `sys.tables`.
- Prefer CTAS / `INSERT ... SELECT` over Copy Activity for intra-workspace moves.

### Distributed processing mode limitations

- **Cannot populate a temp table from a cross-engine source.** `INSERT INTO #temp ... SELECT` / `SELECT ... INTO #temp` fail with `Msg 15816` when the `SELECT` reads an object outside the local engine (cross-database/cross-lakehouse tables, Lakehouse SQL endpoints, shortcut-backed tables read cross-database, system views). Workaround: land the rows into a permanent table - see [Example 12](./12-cross-engine-temp-table.md).

### Stored procedure parameters

- In certain setups, a Fabric pipeline activity can send an explicit `NULL` to the called SP. A T-SQL default (`@Param = <default>`) is applied only when the argument is **omitted**, never when `NULL` is passed explicitly, which can be problematic. Handle `NULL` per parameter in the SP code: by default, raise an error for required parameters, re-apply the default with `COALESCE`/`ISNULL` for optional parameters - see [Example 13](./13-sp-null-parameter-handling.md).


## Examples

- [Create table](./01-create-table.md)
- [CTAS](./02-ctas.md)
- [SELECT ... INTO](./03-select-into.md)
- [Adding constraints](./04-adding-constraint.md)
- [Alter table](./05-alter-table.md)
- [Explicit transactions](./06-explicit-transaction-ddl.md)
- [Cross warehouse queries](./07-cross-warehouse-query.md)
- [SP rename](./08-sp-rename.md)
- [Temp table](./09-temp-table.md)
- [Date table](./10-date-table.md)
- [Row-by-row iteration (cursor replacement)](./11-iteration.md)
- [Cross-engine temp table load](./12-cross-engine-temp-table.md)
- [Stored procedure NULL parameter handling](./13-sp-null-parameter-handling.md)