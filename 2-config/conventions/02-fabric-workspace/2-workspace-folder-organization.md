---
description: General rules and principles for organizing workspaces in Fabric.
status: active
origin: master
---

# Workspace Organization in Fabric

This document defines the general rules and principles for organizing workspaces in Fabric. It applies to all types of workspaces (Data Product Group, Source Dataset, Data Agent, Data Playground) unless specific conventions are defined for a given workspace type.

Summary:
01. [Principles](#principles)
02. [Example of folder structure in a workspace](#example-of-folder-structure-in-a-workspace)
03. [Alternatives considered but not retained](#alternatives-considered-but-not-retained)

## Principles
- Use folders and sub-folders to organize items in the workspace.
    - Folder naming convention is `UPPER_SNAKE_CASE`.
    - Folder names are always singular (e.g. `PIPELINE` not `PIPELINES`).
    - Folder names with a number at the beginning follow the format `#-FOLDER_NAME`, e.g., `1-ORCHESTRATION`, `2-SOURCE_TO_RAW`.
- The folder structure should always follow this hierarchy:
    ```text
    📂 Scope (or deliverable)
        📂 Processing step
            📂 Optional additional level (e.g. item type)
    ```
- For source dataset external ingestion artifacts, use direct item folders under each processing-step folder (no intermediate `PIPELINE` or `NOTEBOOK` subfolder).
- A single variable library per workspace, named `VL_MAIN`, stored at the workspace root. Refer to [variable library convention](../03-fabric-items/variable-library-convention.md) for more details.

### Rationale of the principles:
- Development work is scoped by deliverable, making it the natural top-level organizer. This directly supports navigation, deployment, and maintenance workflows.
- Using the processing step as the second level of hierarchy makes the data flow explicit and groups related artifacts (pipelines, notebooks) by their role in the solution.
- Item type is a valid alternative for the second level, but organizing by processing step provides richer context about the solution design.
- While multi-level folder hierarchies require opening folders in the Fabric UI to find an item, Fabric's filtering features allow viewing all items in a flat list by type or keyword. Nested folders therefore add structure without compromising ease of navigation.


## Example of folder structure in a workspace

Example:
- Using a Source Dataset workspace (bronze layer) for construction: `DP_SDS_CONST_DEV`
- EasyPiping, EPV2, and EasyTender are 3 different sources ingested in the workspace.

<!-- AI hint: ensure this is sync with workspace-sds-convention.md file -->
```text
🏢 DP_SDS_CONST_DEV/
├── 📂 EASY_PIPING
|   ├── ♒ LH_SDS_EASY_PIPING
│   ├── 📂 0-ORCHESTRATION
│   │   └── 🔗 PL_EASY_PIPING_MASTER_ORCHESTRATOR
│   ├── 📂 1-SOURCE_TO_RAW
│   │   └── 🔗 PL_EASY_PIPING_SOURCE_TO_RAW
│   └── 📂 2-RAW_TO_DELTA
│   │   ├── 📓 NB_EASY_PIPING_RAW_TO_DELTA
│   │   └── 🔗 PL_EASY_PIPING_RAW_TO_DELTA
├── 📂 EPV2
|   ├── ♒ LH_SDS_EPV2
│   ├── 📂 0-ORCHESTRATION
│   │   └── 🔗 PL_EPV2_MASTER_ORCHESTRATOR
│   ├── 📂 1-SOURCE_TO_RAW
│   │   └── 🔗 PL_EPV2_SOURCE_TO_RAW
│   └── 📂 2-RAW_TO_DELTA
│   │   ├── 📓 NB_EPV2_RAW_TO_DELTA
│   │   └── 🔗 PL_EPV2_RAW_TO_DELTA
├── 📂 EASY_TENDER
|   ├── ♒ LH_SDS_EASY_TENDER
│   ├── 📂 0-ORCHESTRATION
│   │   └── 🔗 PL_EASY_TENDER_MASTER_ORCHESTRATOR
│   ├── 📂 1-SOURCE_TO_RAW
│   │   └── 🔗 PL_EASY_TENDER_SOURCE_TO_RAW
│   └── 📂 2-RAW_TO_DELTA
│   │   ├── 📓 NB_EASY_TENDER_RAW_TO_DELTA
│   │   └── 🔗 PL_EASY_TENDER_RAW_TO_DELTA
```



## Alternatives considered but not retained

### Not recommended (by item type at level 2)

Example:
```text
DP_SDS_CONST_DEV/
├── 📂 EASY_PIPING
│   ├── 📂 LAKEHOUSE
│   │   └── ♒ LH_SDS_EASY_PIPING
│   ├── 📂 PIPELINE
│   │   ├── 🔗 PL_EASY_PIPING_SOURCE_TO_RAW
│   │   ├── 🔗 PL_EASY_PIPING_RAW_TO_DELTA
│   │   └── 🔗 PL_EASY_PIPING_MASTER_ORCHESTRATOR
│   └── 📂 NOTEBOOK
│       ├── 📓 NB_EASY_PIPING_SOURCE_TO_RAW
│       └── 📓 NB_EASY_PIPING_RAW_TO_DELTA
├── 📂 EPV2
│   ├── 📂 LAKEHOUSE
│   │   └── ♒ LH_SDS_EPV2
│   ├── 📂 PIPELINE
│   │   ├── 🔗 PL_EPV2_SOURCE_TO_RAW
│   │   ├── 🔗 PL_EPV2_RAW_TO_DELTA
│   │   └── 🔗 PL_EPV2_MASTER_ORCHESTRATOR
│   └── 📂 NOTEBOOK
│       ├── 📓 NB_EPV2_SOURCE_TO_RAW
│       └── 📓 NB_EPV2_RAW_TO_DELTA
└── 📂 EASY_TENDER
    ├── 📂 LAKEHOUSE
    │   └── ♒ LH_SDS_EASY_TENDER
    ├── 📂 PIPELINE
    │   ├── 🔗 PL_EASY_TENDER_SOURCE_TO_RAW
    │   ├── 🔗 PL_EASY_TENDER_RAW_TO_DELTA
    │   └── 🔗 PL_EASY_TENDER_MASTER_ORCHESTRATOR
    └── 📂 NOTEBOOK
        ├── 📓 NB_EASY_TENDER_SOURCE_TO_RAW
        └── 📓 NB_EASY_TENDER_RAW_TO_DELTA
```


### Not allowed (by item type at level 1)

Example:
```text
LAKEHOUSE/
├── GAIA/
├── EPV2/
├── SERVICENOW/
PIPELINE/
├── GAIA/
├── EPV2/
├── SERVICENOW/
NOTEBOOK/
├── GAIA/
├── EPV2/
├── SERVICENOW/
```