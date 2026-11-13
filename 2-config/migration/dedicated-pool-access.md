# Connecting to the DPV1 dedicated SQL pool (read-only)

Used by wf-3/wf-4 to extract missing DDL (D1/K1), read procedure definitions and run the equivalence tests (D5: row counts and checksums). The pool is **never written to**: only `SELECT`, `sqlpackage /Action:Extract` and catalog views.

## Connection facts
| Item | Value |
| --- | --- |
| Environment | DPV1 non-production (UAT) |
| Server | `azswne08weuatsynapse01.sql.azuresynapse.net` |
| Database | `AZSQLPNE08WEUAT` |
| VS Code MSSQL profile | `DP Non-prod` (profile id `77887507-16f7-4cb2-b828-9985b29a64d7`) |
| Authentication | Microsoft Entra ID, browser sign-in with the `_AZR` account (`gbadhani_azr@technip.onmicrosoft.com`). No SQL logins, no device code, no password or token in files. |
| DPV1 linked service name | `SQLPoolConstruction` (the pipelines' name for this pool) |

## Ways to connect
| Need | Route |
| --- | --- |
| Browse schemas, tables, functions | MSSQL extension: connect with profile `DP Non-prod`; the agent tools `mssql_connect`, `mssql_list_tables`, `mssql_list_schemas`, `mssql_list_functions` (list only, they cannot run queries) |
| Run `SELECT` (counts, checksums, `sys.sql_modules` definitions) | MSSQL extension query editor (developer runs it and pastes or saves the result), or `sqlcmd -S <server> -d <db> -G -Q "<select>"` (`-G` = Entra browser/interactive sign-in) |
| Extract DDL as a DACPAC | `sqlpackage /Action:Extract /SourceServerName:<server> /SourceDatabaseName:<db> /UniversalAuthentication:True /TargetFile:<project>/4-dacpac/source/<name>.dacpac` (browser sign-in, schema only, no data) |
| Procedure text without sqlpackage | `SELECT m.definition FROM sys.sql_modules m JOIN sys.objects o ON o.object_id = m.object_id JOIN sys.schemas s ON s.schema_id = o.schema_id WHERE s.name IN (<scope schemas>)` |

## Rules
- Read-only: no `CREATE`, `ALTER`, `DROP`, `INSERT`, `UPDATE`, `DELETE`, `TRUNCATE`, `EXEC` of a procedure that writes. If a query is not obviously read-only, do not run it.
- Scope the queries to the product schemas (RMA: `STG_RMA`, `DW_RMA`, `DM_RMA`).
- Save what you extract under the project folder (`2-legacy-code/database-extract/` or `3-build/analysis/`), and name the pool object and date in `build-notes.md`. Do not store credentials.
- If access fails (firewall, Entra group, paused pool), stop and tell the developer which of those it is; do not try another login method.
- The equivalence tests (`skill-equivalence-tests`) compare the pool result with the Fabric Warehouse result per table: row count and checksum, with the query used saved next to the result.
