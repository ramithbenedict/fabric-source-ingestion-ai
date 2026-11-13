---
description: Conventions for organizing and managing a Data Product Group (DPG) workspace in Microsoft Fabric.
status: proposal
origin: master
---

# Workspace Convention for Data Product Group (DPG) workspace type

The purpose of this document is to define the conventions for organizing and managing a Data Product Group (DPG) workspace in Microsoft Fabric. 

A Data Product Group (DPG) workspace stores all technical artifacts related to silver and gold data products for a specific group of data products.

Summary:
01. [Workspace naming](#1-workspace-naming)
02. [Folder organization](#2-folder-organization)
03. [Item naming convention](#3-item-naming-convention)
04. [Other references](#4-other-references)
05. [Decision rationale](#5-decision-rationale)


## 1. Workspace Naming

- Canonical workspace naming pattern: `DP_DPG_<DATA_PRODUCT_GROUP>_<ENV>`.
- Example:
  - `DP_DPG_EPV2BI_DEV` for the DPG workspace for the EPV2BI group of data products in development environment.
  - `DP_DPG_SERVICENOW_DEV` for the DPG workspace for the ServiceNow group of data products in development environment.
  - `DP_DPG_ERPBI_UAT` for the DPG workspace for the ERPBI group of data products in UAT environment.

Refer to [workspace naming convention](./1-workspace-naming.md) for additional details.


## 2. Folder organization

### Folder structure
- The folder structure is organized by data product.
- With a Warehouse (default option), we do not follow the default workspace organization principles (i.e., subfolder per processing step) as in this case the bulk of the artifacts are managed in a Database Project and the workspace is mostly a container for the Database Project and its pipelines. We have an ORCHESTRATION folder. Subfolders can be added if needed; we do not push any defaults as the number of items in 📂 ORCHESTRATION is expected to be small and manageable. 
- With a Lakehouse, we follow the default workspace organization principles with folders by processing step.

#### Example using a Warehouse (default option):

```text
💎 DP_DPG_EPV2BI_DEV (Workspace)
├── 📂 ORCHESTRATION
│   └── (Pipelines, etc.)
│
├── ♒ LH_INP_SDS_EPV2 /* Proxy Lakehouse to expose input source datasets to the DPG */
│
├── ♒ WH_DPG_EPV2BI 
│
├── #️⃣ VL_MAIN
```

#### Example using a Lakehouse:
```text
💎 DP_DPG_EPV2BI_DEV (Workspace)
├── 📂 GOLD_EPV2_FEDERATED
│   ├── 📂 1-ORCHESTRATION
│   │    └── (Pipelines)
│   ├── 📂 2-INTERMEDIATE
│   │    └── (Notebooks, Pipelines, etc.)
│   ├── 📂 3-DIMENSIONS
│   │    └── (Notebooks, Pipelines, etc.)
│   └── 📂 4-FACTS
│        └── (Notebooks, Pipelines, etc.)
│
├── 📂 GOLD_EPV2_PROGRESS_MEASUREMENT
│   └── (Pipelines, etc.)
│
├── 📂 GOLD_EPV2_CERTIFIED_PROGRESS
│   └── (Pipelines, etc.)
│
├── 📂 GOLD_EPV2_COMPLETION
│   └── (Pipelines, etc.)
│
├── 📂 SILV_EPV2_BI
│   └── (Pipelines, etc.)
│
├── ♒ LH_DPG_EPV2BI
│
├── #️⃣ VL_MAIN
│
├── ◼️ PL_DPG_EPV2BI_MASTER_ORCHESTRATOR
|
```

### Naming convention for folders:

Canonical naming pattern for folders:  
📂 `<LAYER>_<DATA_PRODUCT_NAME>`  

Examples:
- 📂 `SILV_EPV2_BI` for the EPV2BI curated data product in silver layer.
- 📂 `GOLD_EPV2_FEDERATED` for the EPV2BI Federated consumption-ready data product in gold layer.
- 📂 `SILV_SERVICENOW` for the ServiceNow curated data product in silver layer.
- 📂 `GOLD_SERVICENOW` for the ServiceNow consumption-ready data product in gold layer.


## 3. Item naming convention

### Naming for Warehouse/Lakehouse for Data Product

Pattern: ♒ `<LH_OR_WH>_DPG_<DATA_PRODUCT_GROUP>`  
Example: ♒ `WH_DPG_EPV2BI` for the EPV2BI curated data product in silver layer.

Where:
- `<LH_OR_WH>`: `LH` for Lakehouse, `WH` for Warehouse
- `DPG` marker indicates it's a Data Product Group.
- `<DATA_PRODUCT_GROUP>` identifies the individual data product name.

Examples:
- ♒ `LH_DPG_EPV2BI`
- ♒ `WH_DPG_ERPBI`

Search by Data Product name will be enabled through the usage of [tags (Microsoft doc)](https://learn.microsoft.com/en-us/fabric/governance/tags-overview).  
Refer to [Fabric item conventions](../03-fabric-items/item-general-convention.md) for additional details on item naming convention.

### Naming for Lakehouse for inputs to the Data Product

ℹ️ For data to be accessible within a workspace, it must be first exposed through internal shortcuts. Shortcuts can be created with a Lakehouse, which we call an "input Lakehouse".

Pattern: ♒ `LH_INP_<SDS|DPG>_<NAME>`  
Example:  
- ♒ `LH_INP_SDS_EPV2` for the EPV2 source dataset used as input to the EPV2BI data product.
- ♒ `LH_INP_DPG_EPV2BI` for the EPV2BI curated data product Lakehouse used as input to another data product.

Where:
- `INP` marker indicates it's an input Lakehouse to the Data Product.
- `<SDS|DPG>`: `SDS` for Source Dataset, `DPG` for Data Product Group
- `<NAME>`: identifies the individual source dataset or data product name used as input.


## 4. Other references
- [workspace naming convention](./1-workspace-naming.md)
- [workspace folder structure convention](./2-workspace-folder-organization.md)
- [workspace access management convention](./4-workspace-access-management.md)


## 5. Decision rationale

### Alternatives for Data Product naming

#### Retained option
Pattern: ♒ `<LH_OR_WH>_DPG_<DATA_PRODUCT_GROUP>`  
Example: ♒ `WH_DPG_EPV2BI` for the EPV2BI curated data product in silver layer.

Rationale:
- Not adding silver and gold in the item name because an item can cover both layers and we want to avoid overloading the name with too many details (e.g. SILV_GOLD).

#### Alternative 1
Pattern: ♒ `<FABRIC_ITEM_PREFIX>_<DATA_PRODUCT_TYPE>_<DATA_PRODUCT_NAME>`  
Example: 
- ♒ `LH_CDP_EPV2BI`
- ♒ `LH_CDP_SERVICENOW`
- ♒ `LH_CRDP_SERVICENOW`

#### Alternative 2
Pattern: ♒ `<FABRIC_ITEM_PREFIX>_<LAYER>_<DATA_PRODUCT_TYPE>_<DATA_PRODUCT_NAME>`
Examples:
- ♒ `LH_SILV_CDP_EPV2BI`
- ♒ `WH_GOLD_CRDP_EPV2BI_FEDERATED`
- ♒ `LH_SILV_CDP_SERVICENOW`
- ♒ `LH_GOLD_CRDP_SERVICENOW`


### Alternatives for Warehouse architecture:


| Importance | Criteria | Option A (1 WH per DPG) | Option B (1 WH per DP) |
|------------|----------|---------------------------|--------------------------|
| - | Description | One warehouse shared at data product group level | One warehouse per individual data product |
| - | Example (EPV2BI) | ♒ `WH_DPG_EPV2BI` | - ♒ `WH_CDP_EPV2BI`<br>- ♒ `WH_CRDP_EPV2BI_FEDERATED`<br>- ♒ `WH_CRDP_EPV2BI_PROGRESS_MEASUREMENT`<br>- ♒ `WH_CRDP_EPV2BI_CERTIFIED_PROGRESS`<br>- ♒ `WH_CRDP_EPV2BI_COMPLETION` |
| Medium | DevOps complexity | 🟢 Low (single ADO pipeline) | 🟡 Medium (multiple yaml pipelines) |
| Medium | Ability to natively search by data product name | 🟡 Medium (name is centered on data product group; tags help) | 🟢 High |
| Low | Data Product delimited by | 🟡 Schemas | 🟢 Warehouse |
| Low | Chargeback per data product | 🔴 Difficult (requires custom development) | 🟢 High (native Fabric chargeback tracks by item) |
| Low | Dev complexity - object management | 🟡 Medium (schema discipline needed) | 🟢 Low (reduced schema pressure but still cross-object coordination) |
| Low | Dev complexity - mental model | 🟢 Easy (all in one database) | 🟡 Moderate (multiple parts, but clear input/output pattern) |
| Low | Sharing overhead | 🟢 Low | 🟡 Medium |
| No difference | Repository strategy | 🟢 One shared repo | 🟢 One shared repository or one repository per data product |
| No difference | Manage DP dependency (ensure coherence) | 🟢 Easy (natively in one repo) | 🟢 Easy (natively in one repo) |
| No difference | Ability to do cross DP queries | 🟢 Yes (same workspace) | 🟢 Yes (same workspace) |
| No difference | Compute allocation | 🟢 Same (all Warehouse would be in the same workspace) | 🟢 Same (all Warehouse would be in the same workspace) |
| No difference | Ability to setup security | 🟢 Same | 🟢 Same |
| No difference | Cataloging in Purview as a Data Product | 🟢 Yes | 🟢 Yes |
| No difference | Automated lineage in purview | 🟢 Yes | 🟢 Yes |

### Example of naming

Option A (1 WH per DPG): 
- ♒ `WH_DPG_EPV2BI` for the EPV2BI curated data product in silver layer.

Option B (1 WH per DP): 
- ♒ `WH_CDP_EPV2BI`
- ♒ `WH_CRDP_EPV2BI_FEDERATED`
- ♒ `WH_CRDP_EPV2BI_PROGRESS_MEASUREMENT`
- ♒ `WH_CRDP_EPV2BI_CERTIFIED_PROGRESS`
- ♒ `WH_CRDP_EPV2BI_COMPLETION`


### Alternatives for folder structure

#### Alternative: one WH per data product

```text
💎 DP_DPG_EPV2BI_DEV (Workspace)
├── 📂 GOLD_EPV2_FEDERATED
│   ├── ♒ WH_GOLD_CRDP_EPV2BI_FEDERATED
│   └── (Pipelines, Notebooks, etc.)
│
├── 📂 GOLD_EPV2_PROGRESS_MEASUREMENT
│   ├── ♒ WH_GOLD_CRDP_EPV2BI_PROGRESS_MEASUREMENT
│   └── (Pipelines, Notebooks, etc.)
│
├── 📂 GOLD_EPV2_CERTIFIED_PROGRESS
│   ├── ♒ WH_GOLD_CRDP_EPV2BI_CERTIFIED_PROGRESS
│   └── (Pipelines, Notebooks, etc.)
│
├── 📂 GOLD_EPV2_COMPLETION
│   ├── ♒ WH_GOLD_CRDP_EPV2BI_COMPLETION
│   └── (Pipelines, Notebooks, etc.)
│
└── 📂 SILV_EPV2_BI
│   ├── ♒ WH_SILV_CDP_EPV2BI
│   └── (Pipelines, Notebooks, etc.)
│
```


Pattern:
`<LH_OR_WH>_DPG_<DATA_PRODUCT_TYPE>_<DATA_PRODUCT_NAME>`
`WH_SILV_CDP_EPV2BI` for the EPV2BI curated data product in silver layer.

Where:
- `<LH_OR_WH>`: `LH` for Lakehouse, `WH` for Warehouse
   Refer to [Fabric item naming conventions](../03-fabric-items/item-general-convention.md) for additional details.
- `<LAYER>` is `BRON`, `SILV` or `GOLD`
- `<DATA_PRODUCT_TYPE>` is `CDP` (Curated Data Product) or `CRDP` (Consumption-Ready Data Product)
- `<DATA_PRODUCT_NAME>` identifies the individual data product name

Other examples:
- `LH_SILV_CDP_EPV2BI`
- `LH_GOLD_CRDP_EPV2BI_FEDERATED`
- `WH_SILV_CDP_ERPBI`
- `WH_GOLD_CRDP_ERPBI_P2P`  