---
name: skill-spark-notebook-to-fabric
description: Port Synapse Spark notebooks and replace Mapping Data Flows in Fabric. Applies only to code that is not T-SQL. Used by wf-2 S3 and wf-3 when a scope has notebooks or data flows.
---

# skill-spark-notebook-to-fabric

This skill is for **Spark and data-flow logic only**. T-SQL never comes here (see skill-tsql-dedicated-to-fabric).

## Synapse notebook => Fabric notebook
| Synapse | Fabric |
|---|---|
| `mssparkutils.*` | `notebookutils.*` |
| `mssparkutils.credentials.getSecret(kv, name, ls)` | `notebookutils.credentials.getSecret('https://<kv>.vault.azure.net/', name)` |
| `abfss://raw@…/<path>` | `Files/landing/…` or `Files/raw/…` of the attached Lakehouse |
| `abfss://cleansed@…/<table>` | `spark.read.table('<table>')` |
| `spark.read.synapsesql(...)` / JDBC to the dedicated pool | Warehouse table by three-part name through the SQL endpoint |
| Spark pool `sparkConfiguration` | Fabric Environment |
| linked-service names in code | `VL_MAIN` / pipeline parameters |

Naming: `NB_<OBJECT>_<ACTIVITY>`. The parameters cell comes first. Write with `saveAsTable` or Delta `MERGE`.

## Mapping Data Flow
Fabric has no Mapping Data Flows. Read `scriptLines` (`2-legacy-code/dataflows/*.dfs`), then:
- **Relational logic** (joins, aggregates, derived columns on tables): **T-SQL procedure** in the database project.
- **File, JSON or schema-drift logic:** Fabric notebook (`derive` => `withColumn`, `aggregate` => `groupBy().agg()`, `alterRow` + sink => Delta `MERGE`, flowlet => shared function).

Log every legacy notebook or flow merged, and every behaviour difference.
