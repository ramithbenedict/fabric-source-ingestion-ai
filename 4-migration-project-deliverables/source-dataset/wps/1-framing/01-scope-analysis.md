# Scope Analysis: WPS (Source Dataset Migration)

Last update: 2026-10-28

Sections: 1. scope card · 2. identification and name check · 3. as-is (DPV1). Mapping: `02-object-mapping.md`; target and plan: `03-target-design-and-plan.md`.

## Scope Card: WPS (Source Dataset Migration)


Framed on 2026-10-28 from `../../../MS_FABRIC_REPO/MS_FABRIC_NEW_SERVICES/Migration/DPV1/TEN Data Platform` (hub generated 2026-10-28 15:55). Resolved from name `WPS`.

### Service

- wf-2-migration-source-dataset: Synapse source ingestion up to SPOT_DB source
- Domain: **COST**

### Target in Fabric

- Workspace: `Platform-Hub_<ENV>`
- Folder: `WPS`
- Lakehouse: `LH_SDS_WPS` (ingested directly from the source: databases => Files/raw (parquet), APIs and files => Files/landing => Files/raw; then tables; no shortcut)

### Size

- DPV1 objects mapped: 42 · pipelines 4 · notebooks 3 · linked services 3
- Complexity (repo-measured): Small (15 objects); register: WPS Small
- Actions: translate 29, merge 5, drop 4, replace 3, rebuild 1

### Lineage with the other service offering

- Data products that read WPS in DPV1: none found
- Entry points: `PL_MASTER_WPS`
- Triggers: PL_WPS (Stopped)

## Scope Identification: WPS


Rules applied to the DPV1 export (see skill `skill-scope-resolution`). Every object in `02-object-mapping.md` carries its evidence in "Found by".

| Rule | Objects |
|---|---|
| Catalog table | 27 |
| Used by | 6 |
| Scope folder | 4 |
| Called by | 3 |
| Entry point | 1 |
| Starts | 1 |

### Name check: 0 other DPV1 objects match "WPS"

- In the other service for this project: 0
- In other scopes: 0
- **Not included: 0** - confirm each one is out of scope or add it before building.

_Nothing to decide._

_The full list of matching objects is in `analysis/dpv1-inventory.md`._

## As-is Inventory (DPV1): WPS


### As-is tree

Where each object lives in the Synapse export, and what happens to it (🟢 converted, 🔵 merged, 🟣 replaced, ⚪ elsewhere, 🟠 decision, 🔴 not migrated).

```text
DPV1 · WPS (source dataset)/                            # 42 objects
├── ADLS data (catalog tables)/                         # 27 objects
│   └── DWHADMIN/                                       # 27 objects
│       ├── DP_DETAILEDRESOURCE                         # 🟢 translate => dbo.dp_detailedresource
│       ├── DP_DETAILEDWORKLOAD                         # 🟢 translate => dbo.dp_detailedworkload
│       ├── DP_PROJECTMASTERLIST                        # 🟢 translate => dbo.dp_projectmasterlist
│       ├── DP_SUMMARYRESOURCE                          # 🟢 translate => dbo.dp_summaryresource
│       ├── DP_SUMMARYWORKLOAD                          # 🟢 translate => dbo.dp_summaryworkload
│       ├── TBL_AUTH_ROLE                               # 🟢 translate => dbo.tbl_auth_role
│       └── … +21 more
├── dataset/                                            # 3 objects
│   ├── DS_CORE_ORACLE_WPS_RAW                          # 🔴 drop
│   ├── DS_GENERIC_ASQL_METABASE_CATALOG                # 🔴 drop
│   └── rawGenericParquetDataSet                        # 🔴 drop
├── linkedService/                                      # 3 objects
│   ├── AzureDataLakeStorageRawZone                     # 🔴 drop
│   ├── LS_CORE_ORACLE_WPS                              # 🟢 translate => CONN_WPS_ORACLE_<ENV>
│   └── LS_PROJ_ASQL_METABASE_CATALOG                   # 🟣 replace => [CATALOG].[wps_catalog] in the catalog warehouse
├── notebook/                                           # 3 objects
│   ├── COMMON/                                         # 2 objects
│   │   ├── NTBK_COMMON_CHILD_META_RAW_TO_CLEAN         # 🔵 merge => NB_WPS_RAW_TO_DELTA
│   │   └── NTBK_COMMON_MASTER_RAW_TO_CLEAN             # 🔵 merge => NB_WPS_RAW_TO_DELTA
│   └── WPS/
│       └── NTBK_WPS_CHILD_FULL_RAW_TO_CLEAN            # 🔵 merge => NB_WPS_RAW_TO_DELTA
├── pipeline/                                           # 4 objects
│   ├── 01_CORE_DATA/                                   # 2 objects
│   │   └── 20_WPS/                                     # 2 objects
│   │       ├── PL_CLNDATA_WPS_TO_ADLS                  # 🔵 merge => PL_WPS_RAW_TO_DELTA
│   │       └── PL_RAWDATA_WPS_TO_ADLS                  # 🔵 merge => PL_WPS_SOURCE_TO_RAW
│   ├── 04_SHARED_TEMPLATES/
│   │   └── 02_GENERIC_CATALOG_CREATION/
│   │       └── PL_GENERIC_METABASE_CATALOG_CREATION    # 🟣 replace => Catalog view [CATALOG].[<source>_catalog] built by create_catalog_view.py
│   └── 99_EXTERNAL_ORCHESTRATION/
│       └── 20_WPS/
│           └── PL_MASTER_WPS                           # 🟢 rebuild => PL_WPS_MASTER_ORCHESTRATOR
├── sqlscript/
│   └── Catalog_Wps                                     # 🟣 replace => [CATALOG].[wps_catalog]
└── trigger/
    └── PL_WPS                                          # 🟢 translate => Schedule on PL_WPS_MASTER_ORCHESTRATOR
```

_Pipelines, linked services, notebooks, datasets and SQL of the scope: `analysis/dpv1-inventory.md`._
