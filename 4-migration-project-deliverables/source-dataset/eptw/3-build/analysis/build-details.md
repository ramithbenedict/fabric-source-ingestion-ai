# Build details: EPTW

Reference tables behind `../build-notes/build-notes.md`, one section per stage. Generated; do not edit.

[S1-catalog-view](#catalog-view-columns-eptw) · [hand-over](#source-dataset-contract-eptw)

<!-- note: S1-catalog-view -->
## Catalog view columns: EPTW

| Column | Fabric type |
| --- | --- |
| `ApiName` | `varchar(100)` |
| `isActive` | `bit` |
| `ParamName` | `varchar(255)` |
| `UnicityKeys` | `varchar(255)` |
| `WatermarkVal` | `datetime2(6)` |
<!-- /note -->
<!-- note: hand-over -->
## Source dataset contract: EPTW

### Tables

| DPV1 table | Fabric table | Load | How DPV1 products read it |
| --- | --- | --- | --- |
| `EPTW.GetPTWProjects_V1` | `dbo.getptwprojects_v1` | incremental | `ADLS RAW|CLEANSED/DATASOURCE=EPTW/EPTW.GetPTWProjects_V1`<br>`spot_eptw.getptwprojects_v1` |
| `EPTW.GetProjectPTW_V1` | `dbo.getprojectptw_v1` | incremental | `ADLS RAW|CLEANSED/DATASOURCE=EPTW/EPTW.GetProjectPTW_V1`<br>`spot_eptw.getprojectptw_v1` |
| `EPTW.GetProjectPTWGeneralPrecautions_V1` | `dbo.getprojectptwgeneralprecautions_v1` | incremental | `ADLS RAW|CLEANSED/DATASOURCE=EPTW/EPTW.GetProjectPTWGeneralPrecautions_V1`<br>`spot_eptw.getprojectptwgeneralprecautions_v1` |
| `EPTW.GetProjectPTWHazard_V1` | `dbo.getprojectptwhazard_v1` | incremental | `ADLS RAW|CLEANSED/DATASOURCE=EPTW/EPTW.GetProjectPTWHazard_V1`<br>`spot_eptw.getprojectptwhazard_v1` |
| `EPTW.GetProjectPTWTag_V1` | `dbo.getprojectptwtag_v1` | incremental | `ADLS RAW|CLEANSED/DATASOURCE=EPTW/EPTW.GetProjectPTWTag_V1`<br>`spot_eptw.getprojectptwtag_v1` |
| `EPTW.GetProjectPTWToolsAndEquipment_V1` | `dbo.getprojectptwtoolsandequipment_v1` | incremental | `ADLS RAW|CLEANSED/DATASOURCE=EPTW/EPTW.GetProjectPTWToolsAndEquipment_V1`<br>`spot_eptw.getprojectptwtoolsandequipment_v1` |
| `EPTW.GetProjectPTWType_V1` | `dbo.getprojectptwtype_v1` | incremental | `ADLS RAW|CLEANSED/DATASOURCE=EPTW/EPTW.GetProjectPTWType_V1`<br>`spot_eptw.getprojectptwtype_v1` |
| `EPTW.GetProjectPTWWorkClass_V1` | `dbo.getprojectptwworkclass_v1` | incremental | `ADLS RAW|CLEANSED/DATASOURCE=EPTW/EPTW.GetProjectPTWWorkClass_V1`<br>`spot_eptw.getprojectptwworkclass_v1` |
| `EPTW.GetProjectPTWWorkSteps_V1` | `dbo.getprojectptwworksteps_v1` | incremental | `ADLS RAW|CLEANSED/DATASOURCE=EPTW/EPTW.GetProjectPTWWorkSteps_V1`<br>`spot_eptw.getprojectptwworksteps_v1` |
| `EPTW.GetProjectActivityType_V1` | `dbo.getprojectactivitytype_v1` | incremental | `ADLS RAW|CLEANSED/DATASOURCE=EPTW/EPTW.GetProjectActivityType_V1`<br>`spot_eptw.getprojectactivitytype_v1` |
| `EPTW.GetProjectCompany_V1` | `dbo.getprojectcompany_v1` | incremental | `ADLS RAW|CLEANSED/DATASOURCE=EPTW/EPTW.GetProjectCompany_V1`<br>`spot_eptw.getprojectcompany_v1` |
| `EPTW.GetProjectContract_V1` | `dbo.getprojectcontract_v1` | incremental | `ADLS RAW|CLEANSED/DATASOURCE=EPTW/EPTW.GetProjectContract_V1`<br>`spot_eptw.getprojectcontract_v1` |
| `EPTW.GetProjectDepartment_V1` | `dbo.getprojectdepartment_v1` | incremental | `ADLS RAW|CLEANSED/DATASOURCE=EPTW/EPTW.GetProjectDepartment_V1`<br>`spot_eptw.getprojectdepartment_v1` |
| `EPTW.GetProjectDiscipline_V1` | `dbo.getprojectdiscipline_v1` | incremental | `ADLS RAW|CLEANSED/DATASOURCE=EPTW/EPTW.GetProjectDiscipline_V1`<br>`spot_eptw.getprojectdiscipline_v1` |
| `EPTW.GetProjectFWBS_V1` | `dbo.getprojectfwbs_v1` | incremental | `ADLS RAW|CLEANSED/DATASOURCE=EPTW/EPTW.GetProjectFWBS_V1`<br>`spot_eptw.getprojectfwbs_v1` |
| `EPTW.GetProjectGeneralPrecautions_V1` | `dbo.getprojectgeneralprecautions_v1` | incremental | `ADLS RAW|CLEANSED/DATASOURCE=EPTW/EPTW.GetProjectGeneralPrecautions_V1`<br>`spot_eptw.getprojectgeneralprecautions_v1` |
| `EPTW.GetProjectGWBS_V1` | `dbo.getprojectgwbs_v1` | incremental | `ADLS RAW|CLEANSED/DATASOURCE=EPTW/EPTW.GetProjectGWBS_V1`<br>`spot_eptw.getprojectgwbs_v1` |
| `EPTW.GetProjectHazards_V1` | `dbo.getprojecthazards_v1` | incremental | `ADLS RAW|CLEANSED/DATASOURCE=EPTW/EPTW.GetProjectHazards_V1`<br>`spot_eptw.getprojecthazards_v1` |
| `EPTW.GetProjectLocationArea_V1` | `dbo.getprojectlocationarea_v1` | incremental | `ADLS RAW|CLEANSED/DATASOURCE=EPTW/EPTW.GetProjectLocationArea_V1`<br>`spot_eptw.getprojectlocationarea_v1` |
| `EPTW.GetProjectPhaseOwnership_V1` | `dbo.getprojectphaseownership_v1` | incremental | `ADLS RAW|CLEANSED/DATASOURCE=EPTW/EPTW.GetProjectPhaseOwnership_V1`<br>`spot_eptw.getprojectphaseownership_v1` |
| `EPTW.GetProjectSupportingDocuments_V1` | `dbo.getprojectsupportingdocuments_v1` | incremental | `ADLS RAW|CLEANSED/DATASOURCE=EPTW/EPTW.GetProjectSupportingDocuments_V1`<br>`spot_eptw.getprojectsupportingdocuments_v1` |
| `EPTW.GetProjectTag_V1` | `dbo.getprojecttag_v1` | incremental | `ADLS RAW|CLEANSED/DATASOURCE=EPTW/EPTW.GetProjectTag_V1`<br>`spot_eptw.getprojecttag_v1` |
| `EPTW.GetProjectToolsEquipmentRequired_V1` | `dbo.getprojecttoolsequipmentrequired_v1` | incremental | `ADLS RAW|CLEANSED/DATASOURCE=EPTW/EPTW.GetProjectToolsEquipmentRequired_V1`<br>`spot_eptw.getprojecttoolsequipmentrequired_v1` |
| `EPTW.GetProjectType_V1` | `dbo.getprojecttype_v1` | incremental | `ADLS RAW|CLEANSED/DATASOURCE=EPTW/EPTW.GetProjectType_V1`<br>`spot_eptw.getprojecttype_v1` |
| `EPTW.GetProjectWorkclass_V1` | `dbo.getprojectworkclass_v1` | incremental | `ADLS RAW|CLEANSED/DATASOURCE=EPTW/EPTW.GetProjectWorkclass_V1`<br>`spot_eptw.getprojectworkclass_v1` |
| `EPTW.GetUsers_V1` | `dbo.getusers_v1` | incremental | `ADLS RAW|CLEANSED/DATASOURCE=EPTW/EPTW.GetUsers_V1`<br>`spot_eptw.getusers_v1` |

### Data products that read this source in DPV1 (analysis only, migrated by Data Product Migration)

| Data product | Tables used | Evidence |
| --- | --- | --- |
| EASYPIPING | 0:  | notebook NTBK_COMMON_MASTER_RAW_TO_CLEAN reads ADLS folder DATASOURCE=EPTW |
| EPTW | 26: dbo.getprojectactivitytype_v1, dbo.getprojectcompany_v1, dbo.getprojectcontract_v1, dbo.getprojectdepartment_v1, dbo.getprojectdiscipline_v1, dbo.getprojectfwbs_v1, dbo.getprojectgeneralprecautions_v1, dbo.getprojectgwbs_v1 … | sqlscript EPTW_INP_VIEWS reads SPOT lake database SPOT_EPTW<br>sqlscript SP_META_CREATE_INP_VIEW reads SPOT lake database SPOT_EPTW |
<!-- /note -->
