---
description: Strategy, structure, and conventions for the Git repositories used for the data delivery in the Fabric data platform.
status: active
origin: master
---

# Fabric Git Repository Strategy & Structure

This document defines the strategy, structure, and conventions for the Git repositories used in the Fabric data platform. There is one primary deployment repository:
- **Fabric Deployment Repository** (`REPO-FABRIC-DEPLOYMENT`): a mono-repo containing all Fabric workspaces, Fabric artifacts (pipelines, notebooks, etc.), and SQL database projects deployed to Fabric Warehouses (DACPAC deployment).

Summary:
01. [Repository strategy](#1-repository-strategy)
02. [Repository root structure](#2-repository-root-structure)
03. [Workspace folder naming](#3-workspace-folder-naming)
04. [Workspace folder contents](#4-workspace-folder-contents)
05. [Decision rationale](#5-decision-rationale)
06. [Alternatives considered](#6-alternatives-considered)

## 1. Repository strategy

### For the AI solution
- One repository for everything

### For Fabric
- One repository for all workspaces
- One folder per workspace (only once for all environments, as we have branches for each environment)
- One folder for the metabase in the `database-projects` folder (metadata for pipeline parameterization, e.g. list of tables, etc.)

### For Database projects
- Same repository as the Fabric workspaces, with one folder per database project in the `database-projects` folder

## 2. Repository root structure
The repository root must follow this layout:


### Repositories overview

```text
Repository: REPO-FABRIC-DEPLOYMENT
┌────────────────────────────────────────────────────────────────────────────────────────┐
│  📂 ci-cd/                        # CI/CD pipeline definitions                         │
|  📂 ci-cd-dacpac/                 # CI/CD pipeline definitions for DACPAC deployments  │
│  📂 wiki/                         # Documentation and wiki pages                       │
│  📂 database-projects/            # SQL database projects (DACPACs)                    │
│      ├── 📂 DPG-GAIA/             (.sqlproj)                                           │
│      ├── 📂 DPG-MDM-DATA-QUALITY/ (.sqlproj)                                           │
│      ├── 📂 METABASE/             (.sqlproj)                                           │
│      ├── 📂 EXT-LH-*/             (external lakehouse references)                      │
│      └── 📂 _TEMPLATE/            (template for new projects)                          │
│  📂 DP_COMMON/                    # Fabric workspace folder (shared/common items)      │
│  📂 DP_SDS_CONST/                 # Fabric workspace folder                            │
│  📂 DP_SDS_FIN/                   # Fabric workspace folder                            │
│  📂 DP_DPG_GAIA/                  # Fabric workspace folder                            │
│  📂 ...                           # Fabric workspace folder                            │
│  ... (all workspaces, ~100)                                                            │
└────────────────────────────────────────────────────────────────────────────────────────┘
```


### Details for Fabric Workspaces:

**Canonical pattern:**
```text
repo-fabric-deployment/
    📂 ci-cd/                       # CI/CD pipeline definitions and deployment scripts
    📂 wiki/                        # Documentation and wiki pages
    📂 <WORKSPACE_FOLDER_1>/        # First Fabric workspace
    📂 <WORKSPACE_FOLDER_2>/        # Second Fabric workspace
    ...
```

**Example:**  
```text
repo-fabric-deployment/
    📂 wiki/
    📂 ci-cd/
    📂 DP_COMMON/                    # Workspace folder for shared items (e.g. Metabase). No environment suffix.
    📂 DP_DPG_GAIA/                  # Workspace folder for the DP_DPG_GAIA Fabric workspace. No environment suffix.
    📂 DP_DPG_HELIOS/                # Workspace folder for the DP_DPG_HELIOS Fabric workspace. No environment suffix.
    ...
```

- `wiki/` — contains documentation, architecture notes, and wiki pages related to the deployment scope.
- `ci-cd/` — contains CI/CD pipeline definitions (e.g. Azure DevOps YAML pipelines) and deployment scripts.
- `<WORKSPACE_FOLDER>/` — one folder per Fabric workspace, containing all Fabric items for that workspace. No environment suffix.


### Details for Database Projects:

Database projects (DACPACs) are co-located in `REPO-FABRIC-DEPLOYMENT` under the `database-projects/` folder. Each subfolder is one `.sqlproj` targeting one Fabric Warehouse.

**Canonical pattern:**
```text
REPO-FABRIC-DEPLOYMENT/
    📂 ci-cd-dacpac/                # CI/CD pipeline definitions for DACPAC deployments
    📂 database-projects/
        📂 _TEMPLATE/                 # Template for new projects
        📂 METABASE/                  # Metabase database project (pipeline parameterization metadata)
        📂 DPG-<DATA_PRODUCT_GROUP>/  # One .sqlproj per data product group
        📂 EXT-LH-<NAME>/             # External lakehouse reference project (optional)
        ...
```

**Example:**
```text
REPO-FABRIC-DEPLOYMENT/
    📂 ci-cd-dacpac/
    📂 database-projects/
        📂 _TEMPLATE/                 # Template for new projects
        📂 DPG-DATAPLATFORM-MONITORING/
        📂 DPG-MDM-DATA-QUALITY/
        📂 METABASE/
        📂 EXT-LH-AZURE-SYNAPSE-LOGS/
```

- `ci-cd-dacpac/` - CI/CD pipeline definitions for building and deploying database projects.
- For internal folder and schema conventions within a database project, refer to [Database Project Structure](../05-data-products/database-project-structure.md).


## 3. Workspace folder naming
- Workspace folder names must be **environment-agnostic**: they must not contain the environment suffix (e.g. `_DEV`, `_UAT`, `_PRD`).
    - ✅ `DP_DPG_GAIA`
    - ❌ `DP_DPG_GAIA_DEV`
- Workspace folder names must follow the workspace naming convention (without the environment suffix). Refer to the [Workspace Naming Convention](../02-fabric-workspace/1-workspace-naming.md) for details.

## 4. Workspace folder contents
- The folder organization inside each workspace folder must match the folder organization of the corresponding Fabric workspace.
- For inner workspace organization rules, refer to the relevant workspace conventions:
    - [Workspace Folder Organization](../02-fabric-workspace/2-workspace-folder-organization.md)
    - [Source Dataset Workspace Convention](../02-fabric-workspace/6-workspace-sds-convention.md)
    - [Data Product Group Workspace Convention](../02-fabric-workspace/5-workspace-dpg-convention.md)
    - [Data Agent Workspace Convention](../02-fabric-workspace/7-workspace-agt-convention.md)
    - [Data Playground Workspace Convention](../02-fabric-workspace/8-workspace-pgr-convention.md)

## 5. Decision rationale
- **Mono-repo for Fabric workspaces**: changes often involve modifications across multiple workspaces within the same deployment scope (e.g. bronze ingestion + silver/gold transformation). A mono-repo ensures all related changes are committed, reviewed, and deployed together, guaranteeing consistency and simplifying deployment orchestration.
- **Environment-agnostic folder names**: the same repository structure is promoted across environments (DEV → UAT → PRD) via CI/CD. Environment-specific configuration is handled through variable libraries and deployment parameters, not through folder naming.
- **Database projects in the Fabric mono-repo**: SQL database projects are co-located in `REPO-FABRIC-DEPLOYMENT` under `database-projects/`. This keeps all deployment artifacts in one place, ensures changes to both are versioned together, and allow items to be deployed together.
- **Metabase co-located in the same repository**: the metabase is tightly coupled with the deployed workspaces as it contains metadata for pipeline parameterization. Keeping it in the same repository ensures that changes to the metabase are versioned and deployed together with workspace changes, maintaining consistency and simplifying development and deployment processes.

## 6. Alternatives considered

### Alternatives for Data Products
- One repository for all data products, with a folder per data product
    - Pros:
        - ✅ Single repository to manage
        - ✅ Reuse Database Project created for external references purposes only (to be confirmed)
        - ✅ Leverage the benefit of doing warehouse-to-warehouse references, enabling a native way to manage dependencies across data products and ensure data consistency across data products (e.g., shared code, shared datasets)
        - ✅ Reuse the same ADO pipeline for all data products, reducing the overhead to create and maintain multiple pipelines for each data product
    - Cons:
        - ⚫ Need custom ADO pipeline to do selective deployment (program the folder and the target warehouse)
- One repository per group of data products
    - Pros:
        - ✅ More isolated
    - Cons:
        - ⚫ More overhead to maintain (more repositories, more Warehouse items in Fabric)
        - ⚫ More complex to manage dependencies across data products (e.g., shared code, shared datasets)
