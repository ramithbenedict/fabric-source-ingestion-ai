---
description: Naming convention for workspaces in T.EN data platform v2 (Fabric), including canonical format, examples, rationale, exceptions, and alternatives considered.
origin: master
status: active
---

# Workspace Naming

The purpose of this document is to define the naming convention for workspaces in T.EN data platform v2 (Fabric).

For understanding the workspace strategy & architecture, please refer to the [Fabric architecture overview](../01-general/fabric-architecture-overview.md) document.

## Naming convention:

### Canonical format

Canonical workspace naming format:  
🏢 `DP_<WORKSPACE_TYPE>_<SCOPE>_<ENV>`


With `WORKSPACE_TYPE`:
- `SDS` for workspaces dedicated to source datasets (bronze)
- `DPG` for workspaces dedicated to data products (silver/gold)
- `AGT` for workspaces dedicated to data agents
- `PGR` for workspaces dedicated to data playgrounds
- `SCOPE` refers to a domain, a data product group, or any other scope.
    - `<DOMAIN_CODE>` see [domain codes](../01-general/domains.md) for the list of domain trigrams
    - We recommend keeping the scope part concise (ideally less than 15 characters).
- `<ENV>` = `DEV` | `UAT` | `PRD`

### Examples by type of workspace

Source:
- 🏢 `DP_SDS_FIN_DEV`: workspace for all finance source datasets in development
- 🏢 `DP_SDS_CONST_DEV`: workspace for all construction source datasets in development

Data products group:
- 🏢 `DP_DPG_EPV2BI_DEV`: workspace for all data products related to the EPV2BI group of data products in development environment.
- 🏢 `DP_DPG_ERPBI_DEV`: workspace for all data products related to the ERPBI group of data products in development environment.
- 🏢 `DP_DPG_CBP_DEV`: workspace for all data products related to the CBP group of data products in development environment.
- 🏢 `DP_DPG_SERVICENOW_DEV`: workspace for all data products related to the ServiceNow data product group in development environment.
- 🏢 `DP_DPG_SERVICENOW_UAT`: workspace for all data products related to the ServiceNow data product group in UAT environment.

Data agent:
- 🏢 `DP_AGT_FIN_DEV`: workspace for all data agents related to finance domain in development environment
- 🏢 `DP_AGT_HCM_DEV`: workspace for all data agents related to HCM domain in development environment

Data playground:
- 🏢 `DP_PGR_CONST`: workspace for all data playgrounds related to construction domain in development environment
- No multiple environment, only one environment.

### Rationale of the naming convention:
- using prefix DP_ to create a namespace for workspaces managed by data platform teams. The alternative would be to share a common naming convention with Power BI workspaces but we exclude this option as it would require massive efforts to rename all Power BI workspaces (> 9000 workspaces).
- as silver/gold are in a single workspace, we do not use the layer (bronze/silver/gold) in the name of the workspace.
- instead, we differentiate workspaces if they are "Source datasets" (SDS) or for a group of "Data products" (DPG).
- order is first WORKSPACE_TYPE (SDS/DPG) then SCOPE to preserve alignment and readability.

## Exceptions

### Confidential source-datasets
For confidential source datasets, a dedicated workspace must be created and used. In this case, the workspace name must include the source name and the `CONF` marker to distinguish it from non-confidential source dataset workspaces. 
- Canonical pattern: 🏢 `DP_CONF_SDS_<DOMAIN_CODE>_<SOURCE_NAME>_<ENV>`
- Example: 🏢 `DP_CONF_SDS_HR_HCM_DEV` for a workspace dedicated to confidential finance payroll source datasets in development environment


### Confidential data products
For confidential data products, a dedicated workspace must be created and used. In this case, the workspace name must include the data product name and the `CONF` marker to distinguish it from non-confidential data product workspaces. 
- Canonical pattern: 🏢 `DP_CONF_DPG_<DATA_PRODUCT_NAME>_<ENV>`
- Example: 🏢 `DP_CONF_DPG_HCM_DEV` for a workspace dedicated to confidential HCM data products in development environment

## Open questions

#### Question 1: prefix for source dataset workspaces (bronze)
**Retained: SDS for consistency with CDP/CRDP (acronyms, not abbreviations).**
- `DP_SDS_FIN_DEV` <- retained option
or
- `DP_SRC_FIN_DEV`


## Alternatives considered

### Sharing a common convention with Power BI workspaces

Description:
- No DP_ for Data Platform workspace and add instead a new `WORKSPACE_TYPE` value for Power BI workspaces
- Canonical pattern: `<WORKSPACE_TYPE>_<DOMAIN_OR_GROUP>_<ENV>`
- Finally:
    - `PBI_FIN_DEV` for Power BI workspace related to finance domain in development environment
    - `PBI_EPV2BI_DEV` for Power BI workspace related to EPV2BI data product group in development environment
    - `SDS_FIN_DEV` for workspace for all finance source datasets in development
    - `DPG_EPV2BI_DEV` for workspace for all data products related to EPV2BI data product group in development environment
    - `PGR_CONST_DEV` for workspace for all data playgrounds related to construction domain in development environment


We refused this alternative as the drawback weighs more than the benefit.

✅ Benefits:
- Consistency between Power BI and Fabric workspaces naming conventions

❌ Drawbacks:
- All Power BI workspaces must be renamed to align with the convention, which is a significant effort



### 5 letters for `WORKSPACE_TYPE`

#### Alternative with 5 characters for the workspace type:
- `SOURC` for workspaces dedicated to source datasets (bronze)
- `DPROD` for workspaces dedicated to data products (silver/gold)
- `AGENT` for workspaces dedicated to data agents
- `DPLAY` for workspaces dedicated to data playgrounds


#### Retained option (3 letters)
- `SDS` for workspaces dedicated to source datasets (bronze)
- `DPG` for workspaces dedicated to data products (silver/gold)
- `AGT` for workspaces dedicated to data agents
- `PGR` for workspaces dedicated to data playgrounds

✅ More readable
✅ More intuitive
✅ Shorter
🟡 Minor risk of similarity
