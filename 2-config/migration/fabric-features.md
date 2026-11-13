---
description: Microsoft Fabric features and best practices used by the migration workflows, including what was announced at FabCon Europe 2026 (Barcelona, September 2026), with status and where each one is applied.
status: active
---

# Fabric features used by the migration

Last update: 2026-10-24

ℹ️ Statuses come from public recaps of FabCon Europe 2026 and the Fabric September 2026 feature summary. The official Microsoft page could not be read automatically, so check each status in the Fabric release notes before relying on it in production. Preview features are optional accelerators: no workflow depends on them.

## Applied in the workflows

| Feature | Status | Where it is used | Why it simplifies the migration |
| --- | --- | --- | --- |
| Variable library (`VL_MAIN`, value sets DEV / UAT / PRD) | ✅ available | Every pipeline and notebook (S2–S4, D4) | Replaces the 353 DPV1 `if(pipeline().DataFactory …)` environment chains |
| OneLake (built into every Lakehouse) | ✅ available | S1–S3: Files/landing, Files/raw, tables | Replaces the DPV1 ADLS zones and their linked services: no storage connection to migrate |
| OneLake shortcuts | ✅ available | wf-3 D3 only (`LH_INP_SDS_<SRC>` => `LH_SDS_<SRC>`) | Data products read the source dataset tables in place, with no copy. Source datasets have no shortcut: they ingest from the source |
| Warehouse cross-database queries (three-part names) | ✅ available | D2 silver procedures, catalog view | Removes the CETAS / STG hops |
| SDK-style SQL database projects (DACPAC) for Warehouse | ✅ available | wf-4, D3 | Dedicated-pool code moves as T-SQL through DACPAC |
| Migration Assistant for Fabric Data Warehouse | ✅ available (Synapse dedicated pool) | wf-4 optional cross-check | Microsoft's own conversion, compared with K2/K3 output |
| Copy job: SCD Type 2 | ✅ GA (FabCon 2026) | S2 option for incremental database tables | Fewer custom pipeline activities for incremental loads |
| Copy job: change data capture and audit columns | ⚪ status not stated | S2 option when the source supports CDC | Native incremental extraction |
| Pipeline activity retry with back-off | ⚪ status not stated | All generated pipelines (Copy, Lookup, Notebook, Stored Procedure) | Replaces DPV1 retry loops and Wait activities |
| Unified workspace monitoring, Monitor Hub, Activator job alerts, operations agent | ⚪ status not stated | S4, D4: alerts on job failure | Replaces the 106 calls to `PL_GENERIC_MAIL_NOTIFICATION` and the per-source log wrappers |
| Git: compare and commit, selective branching | ✅ GA (FabCon 2026) | Repository and deployment | Several sources per domain workspace stay manageable (open question Q7 in the hub) |
| Deployment plans, file-level commits | 🟡 preview (announced) | Later: deployment to the deployment repository | Smaller, targeted deployments per project |
| Spark Runtime 2.0 (Spark 4.1, Delta Lake 4.2, liquid clustering) | ✅ GA (FabCon 2026) | S3 notebooks (Fabric environment) | Faster RAW => tables; incremental clustering for large tables |
| Data Engineering Agent (Project Osmos) | 🟡 preview | S3 optional: draft the RAW => tables notebook from legacy notebooks | Built for migrations and Spark ETL; usable from GitHub Copilot, VS Code and Claude Code. Output still goes through the m-reviewer |

## Best practices applied
- ✔️ **One parameter source.** Every name, ID, endpoint, connection and batch size comes from `VL_MAIN`; nothing is hardcoded.
- ✔️ **Metadata-driven ingestion.** One pipeline per source, driven by the catalog view, instead of one pipeline per table.
- ✔️ **Landing then RAW.** Files keep the source format in landing and are always converted to parquet in RAW; tables are built only from RAW.
- ✔️ **T-SQL stays T-SQL.** Moved through DACPAC and checked by `tsql_fabric_lint.py`.
- ✔️ **Parallelism by default.** Pipelines use ForEach with `isSequential: false`; procedures of the same batch run in parallel; independent build stages run as parallel subagents (see each workflow's "Parallel execution").
- ✔️ **Mandatory gates.** No deployment until every gate in the progress summary is `✅ completed`.

## Sources
- [FabCon Europe 2026: the key Microsoft Fabric updates (bitmetric)](https://www.bitmetric.nl/blog/fabcon-europe-2026-microsoft-fabric-updates/)
- [FabCon Europe 2026: what's new for the people who keep it running (Coeo)](https://www.coeo.com/2026/10/fabcon-26/)
- [FabCon and SQLCon Europe 2026: the biggest announcements (ESPC)](https://espc.tech/learning-hub/blog/fabcon-and-sqlcon-europe-2026-the-biggest-announcements-from-barcelona/)
- [Fabric September 2026 Feature Summary (Microsoft)](https://community.fabric.microsoft.com/blog/fbc_fabricupdatesblogs/fabric-september-2026-feature-summary/5325825)
- [FabCon/SQLCon Barcelona 2026: what's new in Fabric Data Factory (Microsoft)](https://community.fabric.microsoft.com/t5/Fabric-Updates-Blog/FabCon-SQLCon-Barcelona-2026-What-s-new-in-Fabric-Data-Factory/ba-p/5369551)
