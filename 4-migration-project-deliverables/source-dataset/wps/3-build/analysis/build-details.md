# Build details: WPS

Reference tables behind `../build-notes/build-notes.md`, one section per stage. Generated; do not edit.

[S1-catalog-view](#catalog-view-columns-wps) · [hand-over](#source-dataset-contract-wps)

<!-- note: S1-catalog-view -->
## Catalog view columns: WPS

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
## Source dataset contract: WPS

### Tables

| DPV1 table | Fabric table | Load | How DPV1 products read it |
| --- | --- | --- | --- |
| `DWHADMIN.TBL_RFOEC_PROJECTS` | `dbo.tbl_rfoec_projects` | full | `ADLS RAW|CLEANSED/DATASOURCE=WPS/DWHADMIN.TBL_RFOEC_PROJECTS`<br>`spot_wps.tbl_rfoec_projects` |
| `DWHADMIN.TBL_RFCO_OEC` | `dbo.tbl_rfco_oec` | full | `ADLS RAW|CLEANSED/DATASOURCE=WPS/DWHADMIN.TBL_RFCO_OEC`<br>`spot_wps.tbl_rfco_oec` |
| `DWHADMIN.TBL_RFCO_WORKLOADBS` | `dbo.tbl_rfco_workloadbs` | full | `ADLS RAW|CLEANSED/DATASOURCE=WPS/DWHADMIN.TBL_RFCO_WORKLOADBS`<br>`spot_wps.tbl_rfco_workloadbs` |
| `DWHADMIN.TBL_RFCO_PROJECTSCOPE` | `dbo.tbl_rfco_projectscope` | full | `ADLS RAW|CLEANSED/DATASOURCE=WPS/DWHADMIN.TBL_RFCO_PROJECTSCOPE`<br>`spot_wps.tbl_rfco_projectscope` |
| `DWHADMIN.TBL_RFOEC_OECBS` | `dbo.tbl_rfoec_oecbs` | full | `ADLS RAW|CLEANSED/DATASOURCE=WPS/DWHADMIN.TBL_RFOEC_OECBS`<br>`spot_wps.tbl_rfoec_oecbs` |
| `DWHADMIN.TBL_RFCO_GROUPDBS` | `dbo.tbl_rfco_groupdbs` | full | `ADLS RAW|CLEANSED/DATASOURCE=WPS/DWHADMIN.TBL_RFCO_GROUPDBS`<br>`spot_wps.tbl_rfco_groupdbs` |
| `DWHADMIN.TBL_RFCO_BUSINESS_LINE` | `dbo.tbl_rfco_business_line` | full | `ADLS RAW|CLEANSED/DATASOURCE=WPS/DWHADMIN.TBL_RFCO_BUSINESS_LINE`<br>`spot_wps.tbl_rfco_business_line` |
| `DWHADMIN.TBL_RFCO_TECHNOLOGYFIELD` | `dbo.tbl_rfco_technologyfield` | full | `ADLS RAW|CLEANSED/DATASOURCE=WPS/DWHADMIN.TBL_RFCO_TECHNOLOGYFIELD`<br>`spot_wps.tbl_rfco_technologyfield` |
| `DWHADMIN.TBL_RFCO_SUBBUSINESS_LINE` | `dbo.tbl_rfco_subbusiness_line` | full | `ADLS RAW|CLEANSED/DATASOURCE=WPS/DWHADMIN.TBL_RFCO_SUBBUSINESS_LINE`<br>`spot_wps.tbl_rfco_subbusiness_line` |
| `DWHADMIN.TBL_RFCO_SIMPL_PROJECTSCOPE` | `dbo.tbl_rfco_simpl_projectscope` | full | `ADLS RAW|CLEANSED/DATASOURCE=WPS/DWHADMIN.TBL_RFCO_SIMPL_PROJECTSCOPE`<br>`spot_wps.tbl_rfco_simpl_projectscope` |
| `DWHADMIN.TBL_RFCO_SIMPL_GROUPDBS` | `dbo.tbl_rfco_simpl_groupdbs` | full | `ADLS RAW|CLEANSED/DATASOURCE=WPS/DWHADMIN.TBL_RFCO_SIMPL_GROUPDBS`<br>`spot_wps.tbl_rfco_simpl_groupdbs` |
| `DWHADMIN.TBL_RFCO_REGIONS` | `dbo.tbl_rfco_regions` | full | `ADLS RAW|CLEANSED/DATASOURCE=WPS/DWHADMIN.TBL_RFCO_REGIONS`<br>`spot_wps.tbl_rfco_regions` |
| `DWHADMIN.TBL_RFCO_BILLINGTYPE` | `dbo.tbl_rfco_billingtype` | full | `ADLS RAW|CLEANSED/DATASOURCE=WPS/DWHADMIN.TBL_RFCO_BILLINGTYPE`<br>`spot_wps.tbl_rfco_billingtype` |
| `DWHADMIN.TBL_RFCO_ENERGYTRANSITIONPILAR` | `dbo.tbl_rfco_energytransitionpilar` | full | `ADLS RAW|CLEANSED/DATASOURCE=WPS/DWHADMIN.TBL_RFCO_ENERGYTRANSITIONPILAR`<br>`spot_wps.tbl_rfco_energytransitionpilar` |
| `DWHADMIN.TBL_RFCO_PROJECT_STATUS` | `dbo.tbl_rfco_project_status` | full | `ADLS RAW|CLEANSED/DATASOURCE=WPS/DWHADMIN.TBL_RFCO_PROJECT_STATUS`<br>`spot_wps.tbl_rfco_project_status` |
| `DWHADMIN.TBL_RFCO_PROBABILITYOFAWARD` | `dbo.tbl_rfco_probabilityofaward` | full | `ADLS RAW|CLEANSED/DATASOURCE=WPS/DWHADMIN.TBL_RFCO_PROBABILITYOFAWARD`<br>`spot_wps.tbl_rfco_probabilityofaward` |
| `DWHADMIN.TBL_RFCO_GROUPSEGMENT` | `dbo.tbl_rfco_groupsegment` | full | `ADLS RAW|CLEANSED/DATASOURCE=WPS/DWHADMIN.TBL_RFCO_GROUPSEGMENT`<br>`spot_wps.tbl_rfco_groupsegment` |
| `DWHADMIN.TBL_RFCO_WORKSHARING` | `dbo.tbl_rfco_worksharing` | full | `ADLS RAW|CLEANSED/DATASOURCE=WPS/DWHADMIN.TBL_RFCO_WORKSHARING`<br>`spot_wps.tbl_rfco_worksharing` |
| `DWHADMIN.TBL_RFCO_WORKSHARING_OECHOURS` | `dbo.tbl_rfco_worksharing_oechours` | full | `ADLS RAW|CLEANSED/DATASOURCE=WPS/DWHADMIN.TBL_RFCO_WORKSHARING_OECHOURS`<br>`spot_wps.tbl_rfco_worksharing_oechours` |
| `DWHADMIN.TBL_AUTH_ROLE` | `dbo.tbl_auth_role` | full | `ADLS RAW|CLEANSED/DATASOURCE=WPS/DWHADMIN.TBL_AUTH_ROLE`<br>`spot_wps.tbl_auth_role` |
| `DWHADMIN.TBL_AUTH_USER` | `dbo.tbl_auth_user` | full | `ADLS RAW|CLEANSED/DATASOURCE=WPS/DWHADMIN.TBL_AUTH_USER`<br>`spot_wps.tbl_auth_user` |
| `DWHADMIN.TBL_AUTH_USERPROFILE` | `dbo.tbl_auth_userprofile` | full | `ADLS RAW|CLEANSED/DATASOURCE=WPS/DWHADMIN.TBL_AUTH_USERPROFILE`<br>`spot_wps.tbl_auth_userprofile` |
| `DWHADMIN.DP_DETAILEDRESOURCE` | `dbo.dp_detailedresource` | full | `ADLS RAW|CLEANSED/DATASOURCE=WPS/DWHADMIN.DP_DETAILEDRESOURCE`<br>`spot_wps.dp_detailedresource` |
| `DWHADMIN.DP_SUMMARYRESOURCE` | `dbo.dp_summaryresource` | full | `ADLS RAW|CLEANSED/DATASOURCE=WPS/DWHADMIN.DP_SUMMARYRESOURCE`<br>`spot_wps.dp_summaryresource` |
| `DWHADMIN.DP_DETAILEDWORKLOAD` | `dbo.dp_detailedworkload` | full | `ADLS RAW|CLEANSED/DATASOURCE=WPS/DWHADMIN.DP_DETAILEDWORKLOAD`<br>`spot_wps.dp_detailedworkload` |
| `DWHADMIN.DP_SUMMARYWORKLOAD` | `dbo.dp_summaryworkload` | full | `ADLS RAW|CLEANSED/DATASOURCE=WPS/DWHADMIN.DP_SUMMARYWORKLOAD`<br>`spot_wps.dp_summaryworkload` |
| `DWHADMIN.DP_PROJECTMASTERLIST` | `dbo.dp_projectmasterlist` | full | `ADLS RAW|CLEANSED/DATASOURCE=WPS/DWHADMIN.DP_PROJECTMASTERLIST`<br>`spot_wps.dp_projectmasterlist` |

### Data products that read this source in DPV1 (analysis only, migrated by Data Product Migration)

- None found in the DPV1 code.
<!-- /note -->
