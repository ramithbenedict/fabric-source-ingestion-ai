# Scope Analysis: EPTW (Source Dataset Migration)

Last update: 2026-11-02

Sections: 1. scope card · 2. identification and name check · 3. as-is (DPV1). Mapping: `02-object-mapping.md`; target and plan: `03-target-design-and-plan.md`.

## Scope Card: EPTW (Source Dataset Migration)


Framed on 2026-11-02 from `../../../MS_FABRIC_REPO/MS_FABRIC_NEW_SERVICES/Migration/DPV1/TEN Data Platform` (hub generated 2026-11-02 20:33). Resolved from name `EPTW`.

### Service

- wf-2-migration-source-dataset: Synapse source ingestion up to SPOT_DB source
- Domain: **QHSES**

### Target in Fabric

- Workspace: `DP_SDS_QHSES_<ENV>`
- Folder: `EPTW`
- Lakehouse: `LH_SDS_EPTW` (ingested directly from the source: databases => Files/raw (parquet), APIs and files => Files/landing => Files/raw; then tables; no shortcut)

### Size

- DPV1 objects mapped: 48 · pipelines 5 · notebooks 6 · linked services 3
- Complexity (repo-measured): Medium (117 objects); register: EPTW Medium
- Actions: translate 27, merge 9, drop 7, rebuild 3, replace 2

### Lineage with the other service offering

- Data products that read EPTW in DPV1 (analysis only: they are migrated by Data Product Migration, never by this workflow):
  - **EASYPIPING**: 1 DPV1 objects, e.g. notebook NTBK_COMMON_MASTER_RAW_TO_CLEAN reads ADLS folder DATASOURCE=EPTW
  - **EPTW**: 2 DPV1 objects, e.g. sqlscript EPTW_INP_VIEWS reads SPOT lake database SPOT_EPTW
- What they will need is published at the end of S4 in `source-dataset-contract.json` (tables, DPV1 access paths, VL_MAIN names).
- Entry points: `PL_MASTER_EPTW`
- Triggers: none in the repository

## Scope Identification: EPTW


Rules applied to the DPV1 export (see skill `skill-scope-resolution`). Every object in `02-object-mapping.md` carries its evidence in "Found by".

| Rule | Objects |
|---|---|
| Catalog table | 26 |
| Scope folder | 8 |
| Used by | 8 |
| Called by | 5 |
| Entry point | 1 |

### Name check: 24 other DPV1 objects match "EPTW"

- In the other service for this project: 17
- In other scopes: 2
- **Not included: 0** - confirm each one is out of scope or add it before building.

_Nothing to decide._

_The full list of matching objects is in `analysis/dpv1-inventory.md`._

## As-is Inventory (DPV1): EPTW


### As-is tree

Where each object lives in the Synapse export, and what happens to it (🟢 converted, 🔵 merged, 🟣 replaced, ⚪ elsewhere, 🟠 decision, 🔴 not migrated).

```text
DPV1 · EPTW (source dataset)/                      # 48 objects
├── ADLS data (catalog tables)/                    # 26 objects
│   └── EPTW/                                      # 26 objects
│       ├── GetProjectActivityType_V1              # 🟢 translate => dbo.getprojectactivitytype_v1
│       ├── GetProjectCompany_V1                   # 🟢 translate => dbo.getprojectcompany_v1
│       ├── GetProjectContract_V1                  # 🟢 translate => dbo.getprojectcontract_v1
│       ├── GetProjectDepartment_V1                # 🟢 translate => dbo.getprojectdepartment_v1
│       ├── GetProjectDiscipline_V1                # 🟢 translate => dbo.getprojectdiscipline_v1
│       ├── GetProjectFWBS_V1                      # 🟢 translate => dbo.getprojectfwbs_v1
│       └── … +20 more
├── dataset/                                       # 5 objects
│   ├── DS_CORE_REST_EPTW_APIM                     # 🔴 drop
│   ├── DS_FILE_JSON_RawLayer                      # 🔴 drop
│   ├── DS_GENERIC_ASQL_METABASE_CATALOG           # 🔴 drop
│   ├── rawGenericFolderDataSet                    # 🔴 drop
│   └── rawGenericParquetDataSet                   # 🔴 drop
├── linkedService/                                 # 3 objects
│   ├── AzureDataLakeStorageRawZone                # 🔴 drop
│   ├── LS_CORE_REST_EPTW                          # 🟢 translate => CONN_EPTW_REST_SERVICE_<ENV>
│   └── LS_PROJ_ASQL_METABASE_CATALOG              # 🟣 replace => [CATALOG].[eptw_catalog] in the catalog warehouse
├── notebook/                                      # 6 objects
│   ├── COMMON/                                    # 2 objects
│   │   ├── NTBK_COMMON_CHILD_META_RAW_TO_CLEAN    # 🔵 merge => NB_EPTW_RAW_TO_DELTA
│   │   └── NTBK_COMMON_MASTER_RAW_TO_CLEAN        # 🔵 merge => NB_EPTW_RAW_TO_DELTA
│   └── EPTW/                                      # 4 objects
│       ├── NTBK_EPTW_CHILD_FULL_RAW_TO_CLEAN      # 🔵 merge => NB_EPTW_RAW_TO_DELTA
│       ├── NTBK_EPTW_CHILD_META_RAW_TO_CLEAN      # 🔵 merge => NB_EPTW_RAW_TO_DELTA
│       ├── NTBK_EPTW_CHILD_RAW_TO_CLEANSED        # 🔵 merge => NB_EPTW_RAW_TO_DELTA
│       └── NTBK_EPTW_MASTER_RAW_TO_CLEANSED       # 🔵 merge => NB_EPTW_RAW_TO_DELTA
├── pipeline/                                      # 5 objects
│   ├── 01_CORE_DATA/                              # 4 objects
│   │   ├── 00_DSQL_OFFLOAD/
│   │   │   └── 13_EPTW_DWH/
│   │   │       └── PL_EPTW_OFFLOAD_SPOT           # 🔴 drop
│   │   └── 05_EPTW/                               # 3 objects
│   │       ├── PL_CLNDATA_EPTW                    # 🔵 merge => PL_EPTW_RAW_TO_DELTA
│   │       ├── PL_RAWDATA_EPTW                    # 🔵 merge => PL_EPTW_SOURCE_TO_RAW
│   │       └── PL_RAWDATA_EPTW_CHILD_API          # 🔵 merge => PL_EPTW_SOURCE_TO_RAW
│   └── 99_EXTERNAL_ORCHESTRATION/
│       └── 14_EPTW/
│           └── PL_MASTER_EPTW                     # 🟢 rebuild => PL_EPTW_MASTER_ORCHESTRATOR
└── sqlscript/                                     # 3 objects
    ├── CATALOG_EPTW                               # 🟣 replace => Catalog warehouse
    ├── LOGS_EPTW_INCREMENTAL_LOAD_SP              # 🟢 rebuild => [LOGS].[SP_EPTW_INCREMENTAL_LOAD]
    └── LOGS_EPTW_INCREMENTAL_LOAD_TABLE           # 🟢 rebuild => [LOGS].[EPTW_INCREMENTAL_LOAD]
```

_Pipelines, linked services, notebooks, datasets and SQL of the scope: `analysis/dpv1-inventory.md`._
