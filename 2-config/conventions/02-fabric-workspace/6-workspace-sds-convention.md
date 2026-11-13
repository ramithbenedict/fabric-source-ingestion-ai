---
description: Conventions for organizing and managing a Source Dataset (SDS) workspace in Microsoft Fabric.
status: proposal
origin: master
---

# Source Dataset Workspace Convention

The purpose of this document is to define the conventions for organizing and managing a Source Dataset workspace in Fabric.

A Source Dataset workspace stores all technical artifacts related to the ingestion and preparation of source datasets (bronze layer).

Summary:
01. [Workspace naming](#1-workspace-naming)
02. [Folder organization](#2-folder-organization)
03. [Item naming convention](#3-item-naming-convention)
04. [Other references](#4-other-references)
05. [Decision rationale](#5-decision-rationale)

## 1. Workspace Naming

Workspace names must follow the canonical naming defined in the [workspace naming convention](./1-workspace-naming.md).  
  
For source dataset workspaces:
- Pattern: `DP_SDS_<DOMAIN_CODE>_<ENV>`
- Example: `DP_SDS_CONST_DEV`


## 2. Folder Organization

Refer to the [workspace folder organization convention](./2-workspace-folder-organization.md) for the detailed folder structure and organization principles.

### Rules
- One folder per source dataset.

### Examples

#### DPv1 Sources (ADLS Shortcuts / Virtualization)

Canonical pattern:
```text
DP_SDS_<DOMAIN_CODE>_<ENV>/
├── 📂 <SOURCE_NAME>
│   └── ♒ LH_SDS_<SOURCE_NAME>
```


What you see in Fabric portal:

```text
DP_SDS_CONST_DEV/
├── 📂 EASY_PIPING
│   └── ♒ LH_SDS_EASY_PIPING
├── 📂 EPV2
│   └── ♒ LH_SDS_EPV2
```

What you see in the code repository:
```text
DP_SDS_CONST_DEV/
├── 📂 EASY_PIPING
│   └── 📂 LH_SDS_EASY_PIPING.Lakehouse
│       ├── .platform
│       ├── lakehouse.metadata.json
│       └── shortcuts.metadata.json
├── 📂 EPV2
│   └── 📂 LH_SDS_EPV2.Lakehouse
│       ├── .platform
│       ├── lakehouse.metadata.json
│       └── shortcuts.metadata.json
```


#### External Sources (Oracle, SQL Server, MySQL, PostgreSQL, other structured sources)

<!-- AI hint: ensure this is sync with 2-workspace-folder-organization.md file -->

What you see in Fabric portal:

```text
DP_SDS_CONST_DEV/
├── 📂 EASY_PIPING
│   ├── 📂 0-ORCHESTRATION
│   │   └── 🔗 PL_EASY_PIPING_MASTER_ORCHESTRATOR
│   ├── 📂 1-SOURCE_TO_RAW
│   │   └── 🔗 PL_EASY_PIPING_SOURCE_TO_RAW
│   ├── 📂 2-RAW_TO_DELTA
│   │   ├── 📓 NB_EASY_PIPING_RAW_TO_DELTA
│   │   └── 🔗 PL_EASY_PIPING_RAW_TO_DELTA
│   └── ♒ LH_SDS_EASY_PIPING
├── 📂 EPV2
│   ├── 📂 0-ORCHESTRATION
│   │   └── 🔗 PL_EPV2_MASTER_ORCHESTRATOR
│   ├── 📂 1-SOURCE_TO_RAW
│   │   └── 🔗 PL_EPV2_SOURCE_TO_RAW
│   ├── 📂 2-RAW_TO_DELTA
│   │   ├── 📓 NB_EPV2_RAW_TO_DELTA
│   │   └── 🔗 PL_EPV2_RAW_TO_DELTA
│   └── ♒ LH_SDS_EPV2
├── 📂 EASY_TENDER
│   ├── 📂 0-ORCHESTRATION
│   │   └── 🔗 PL_EASY_TENDER_MASTER_ORCHESTRATOR
│   ├── 📂 1-SOURCE_TO_RAW
│   │   └── 🔗 PL_EASY_TENDER_SOURCE_TO_RAW
│   ├── 📂 2-RAW_TO_DELTA
│   │   ├── 📓 NB_EASY_TENDER_RAW_TO_DELTA
│   │   └── 🔗 PL_EASY_TENDER_RAW_TO_DELTA
│   └── ♒ LH_SDS_EASY_TENDER
```

What you see in the code repository:
```text
DP_SDS_CONST_DEV/
├── 📂 EASY_PIPING
│   ├── 📂 0-ORCHESTRATION
│   │   └── 📂 PL_EASY_PIPING_MASTER_ORCHESTRATOR.DataPipeline
│   │       ├── .platform
│   │       └── pipeline-content.json
│   ├── 📂 1-SOURCE_TO_RAW
│   │   └── 📂 PL_EASY_PIPING_SOURCE_TO_RAW.DataPipeline
│   │       ├── .platform
│   │       └── pipeline-content.json
│   ├── 📂 2-RAW_TO_DELTA
│   │   ├── 📂 NB_EASY_PIPING_RAW_TO_DELTA.Notebook
│   │   │   ├── .platform
│   │   │   └── notebook-content.py
│   │   └── 📂 PL_EASY_PIPING_RAW_TO_DELTA.DataPipeline
│   │       ├── .platform
│   │       └── pipeline-content.json
│   └── 📂 LH_SDS_EASY_PIPING.Lakehouse
│       ├── .platform
│       ├── lakehouse.metadata.json
│       └── shortcuts.metadata.json
├── 📂 EPV2
│   ├── 📂 0-ORCHESTRATION
│   │   └── 📂 PL_EPV2_MASTER_ORCHESTRATOR.DataPipeline
│   │       ├── .platform
│   │       └── pipeline-content.json
│   ├── 📂 1-SOURCE_TO_RAW
│   │   └── 📂 PL_EPV2_SOURCE_TO_RAW.DataPipeline
│   │       ├── .platform
│   │       └── pipeline-content.json
│   ├── 📂 2-RAW_TO_DELTA
│   │   ├── 📂 NB_EPV2_RAW_TO_DELTA.Notebook
│   │   │   ├── .platform
│   │   │   └── notebook-content.py
│   │   └── 📂 PL_EPV2_RAW_TO_DELTA.DataPipeline
│   │       ├── .platform
│   │       └── pipeline-content.json
│   └── 📂 LH_SDS_EPV2.Lakehouse
│       ├── .platform
│       ├── lakehouse.metadata.json
│       └── shortcuts.metadata.json
└── 📂 EASY_TENDER
    ├── 📂 0-ORCHESTRATION
    │   └── 📂 PL_EASY_TENDER_MASTER_ORCHESTRATOR.DataPipeline
    │       ├── .platform
    │       └── pipeline-content.json
    ├── 📂 1-SOURCE_TO_RAW
    │   └── 📂 PL_EASY_TENDER_SOURCE_TO_RAW.DataPipeline
    │       ├── .platform
    │       └── pipeline-content.json
    ├── 📂 2-RAW_TO_DELTA
    │   ├── 📂 NB_EASY_TENDER_RAW_TO_DELTA.Notebook
    │   │   ├── .platform
    │   │   └── notebook-content.py
    │   └── 📂 PL_EASY_TENDER_RAW_TO_DELTA.DataPipeline
    │       ├── .platform
    │       └── pipeline-content.json
    └── 📂 LH_SDS_EASY_TENDER.Lakehouse
        ├── .platform
        ├── lakehouse.metadata.json
        └── shortcuts.metadata.json
```

### External Source Ingestion Convention Tokens

Use these tokens when resolving folder and default RAW destination values for external-source ingestion patterns. Avoid hardcoded literals in implementation artifacts.

| Token | Canonical Value | Source |
| --- | --- | --- |
| `<FOLDER_ORCHESTRATION>` | `0-ORCHESTRATION` | External Sources folder structure |
| `<FOLDER_SOURCE_TO_RAW>` | `1-SOURCE_TO_RAW` | External Sources folder structure |
| `<FOLDER_RAW_TO_DELTA>` | `2-RAW_TO_DELTA` | External Sources folder structure |
| `<DEST_FOLDER_RAW_PATTERN>` | `RAW/DATASOURCE=<SOURCE_NAME_UPPER>` | External source ingestion default |

## 3. Item naming convention

### Lakehouse for Source Dataset

Pattern:  
`LH_SDS_<SOURCE_NAME>`

Where:  
- `<SOURCE_NAME>`: source dataset identifier or source subset identifier

Examples:  
- `LH_SDS_EPV2`
- `LH_SDS_ERP`
- `LH_SDS_EASYPIPING`
- `LH_SDS_SERVICENOW`

Exception:
- If a source application covers multiple domains, suffix the source name with the domain to distinguish them:  
  - `LH_SDS_PEOPLECONNECT_FIN`
  - `LH_SDS_PEOPLECONNECT_HR`

Rationale:
- Environment is not included in item names because it is encoded in the workspace name.
- Domain is not included in item names because the workspace already carries the domain. If a source application spans multiple domains, the domain is suffixed (see Exception section).
- `SDS` marker distinguishes source dataset lakehouses from data product items (which use `DPG`).
- `BRON` is not included in the name to stay consistent with the data product group naming convention which does not include layer in the name. If required in the future, layer can be added as a tag.

### Variable library
- One main variable library `VL_MAIN` stored at the workspace root
- Refer to [variable library convention](../03-fabric-items/variable-library-convention.md) for more details.

### Pipeline and Notebook Conventions for Source Datasets

| Item | Convention |
| --- | --- |
| Master orchestrator pipeline | `PL_<SOURCE_NAME>_MASTER_ORCHESTRATOR` |
| Source to RAW pipeline | `PL_<SOURCE_NAME>_SOURCE_TO_RAW` |
| RAW to Lakehouse pipeline | `PL_<SOURCE_NAME>_RAW_TO_DELTA` |
| Other child pipelines | `PL_<SOURCE_NAME>_<ACTIVITY>` |
| RAW to Lakehouse notebook | `NB_<SOURCE_NAME>_RAW_TO_DELTA` |
| Other notebooks | `NB_<SOURCE_NAME>_<ACTIVITY>` |

Refer to [pipeline convention](../03-fabric-items/pipeline-convention.md) for more details on pipeline organization and naming.
Refer to [notebook convention](../03-fabric-items/notebook-convention.md) for more details on notebook organization and naming.

## 4. Other references

- [workspace naming convention](./1-workspace-naming.md)
- [workspace folder structure convention](./2-workspace-folder-organization.md)
- [workspace access management convention](./4-workspace-access-management.md)

## 5. Decision rationale

- Grouping by source keeps all source artifacts self-contained.
- Uppercase source tokens avoid case-sensitivity mistakes in references.