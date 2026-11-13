# Build details: RMA

Reference tables behind `../build-notes/build-notes.md`, one section per stage. Generated; do not edit.

[S1-catalog-view](#catalog-view-columns-rma) · [hand-over](#source-dataset-contract-rma)

<!-- note: S1-catalog-view -->
## Catalog view columns: RMA

| Column | Fabric type |
| --- | --- |
| `schemaName` | `varchar(50)` |
| `tableName` | `varchar(200)` |
| `isIncLoad` | `bit` |
| `DeltaMode` | `varchar(10)` |
| `isActive` | `bit` |
| `watermark` | `datetime2(6)` |
| `TableProvenance` | `varchar(20)` |
| `Comment` | `varchar(500)` |
<!-- /note -->
<!-- note: hand-over -->
## Source dataset contract: RMA

### Tables

| DPV1 table | Fabric table | Load | How DPV1 products read it |
| --- | --- | --- | --- |
| `dbo.Actions` | `dbo.actions` | full | `ADLS RAW|CLEANSED/DATASOURCE=RMA/dbo.Actions`<br>`spot_rma.actions` |
| `dbo.Business_Units` | `dbo.business_units` | full | `ADLS RAW|CLEANSED/DATASOURCE=RMA/dbo.Business_Units`<br>`spot_rma.business_units` |
| `dbo.Global_Business_Units` | `dbo.global_business_units` | full | `ADLS RAW|CLEANSED/DATASOURCE=RMA/dbo.Global_Business_Units`<br>`spot_rma.global_business_units` |
| `dbo.Iso4217_Currencies` | `dbo.iso4217_currencies` | full | `ADLS RAW|CLEANSED/DATASOURCE=RMA/dbo.Iso4217_Currencies`<br>`spot_rma.iso4217_currencies` |
| `dbo.Lookup_Values` | `dbo.lookup_values` | full | `ADLS RAW|CLEANSED/DATASOURCE=RMA/dbo.Lookup_Values`<br>`spot_rma.lookup_values` |
| `dbo.Lookup_Types` | `dbo.lookup_types` | full | `ADLS RAW|CLEANSED/DATASOURCE=RMA/dbo.Lookup_Types`<br>`spot_rma.lookup_types` |
| `dbo.organizational_entities` | `dbo.organizational_entities` | full | `ADLS RAW|CLEANSED/DATASOURCE=RMA/dbo.organizational_entities`<br>`spot_rma.organizational_entities` |
| `dbo.PreBids` | `dbo.prebids` | full | `ADLS RAW|CLEANSED/DATASOURCE=RMA/dbo.PreBids`<br>`spot_rma.prebids` |
| `dbo.Projects` | `dbo.projects` | full | `ADLS RAW|CLEANSED/DATASOURCE=RMA/dbo.Projects`<br>`spot_rma.projects` |
| `dbo.RBS` | `dbo.rbs` | full | `ADLS RAW|CLEANSED/DATASOURCE=RMA/dbo.RBS`<br>`spot_rma.rbs` |
| `dbo.Risk_Registers` | `dbo.risk_registers` | full | `ADLS RAW|CLEANSED/DATASOURCE=RMA/dbo.Risk_Registers`<br>`spot_rma.risk_registers` |
| `dbo.Risks` | `dbo.risks` | full | `ADLS RAW|CLEANSED/DATASOURCE=RMA/dbo.Risks`<br>`spot_rma.risks` |
| `dbo.Risks_History` | `dbo.risks_history` | full | `ADLS RAW|CLEANSED/DATASOURCE=RMA/dbo.Risks_History`<br>`spot_rma.risks_history` |
| `dbo.RPETS` | `dbo.rpets` | full | `ADLS RAW|CLEANSED/DATASOURCE=RMA/dbo.RPETS`<br>`spot_rma.rpets` |
| `dbo.Threat_Matrices` | `dbo.threat_matrices` | full | `ADLS RAW|CLEANSED/DATASOURCE=RMA/dbo.Threat_Matrices`<br>`spot_rma.threat_matrices` |
| `dbo.Opportunity_Matrices` | `dbo.opportunity_matrices` | full | `ADLS RAW|CLEANSED/DATASOURCE=RMA/dbo.Opportunity_Matrices`<br>`spot_rma.opportunity_matrices` |
| `dbo.Permissions` | `dbo.permissions` | full | `ADLS RAW|CLEANSED/DATASOURCE=RMA/dbo.Permissions`<br>`spot_rma.permissions` |
| `dbo.Users` | `dbo.users` | full | `ADLS RAW|CLEANSED/DATASOURCE=RMA/dbo.Users`<br>`spot_rma.users` |

### Data products that read this source in DPV1 (analysis only, migrated by Data Product Migration)

| Data product | Tables used | Evidence |
| --- | --- | --- |
| QHSES | 0:  | notebook NTBK_INTELEX_MAPPING reads SPOT lake database SPOT_RMA |
| RMA | 18: dbo.actions, dbo.business_units, dbo.global_business_units, dbo.iso4217_currencies, dbo.lookup_types, dbo.lookup_values, dbo.opportunity_matrices, dbo.organizational_entities … | pipeline PL_CHILD_META_SSP_RMA_DB_BUILD reads SPOT lake database SPOT_RMA<br>sqlscript INP_META_RMA_VIEWS reads SPOT lake database SPOT_RMA |
<!-- /note -->
