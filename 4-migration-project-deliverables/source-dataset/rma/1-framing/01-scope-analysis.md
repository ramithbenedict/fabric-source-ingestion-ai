# Scope Analysis: RMA (Source Dataset Migration)

Last update: 2026-10-27

Sections: 1. scope card · 2. identification and name check · 3. as-is (DPV1). Mapping: `02-object-mapping.md`; target and plan: `03-target-design-and-plan.md`.

## Scope Card: RMA (Source Dataset Migration)


Framed on 2026-10-27 from `../../../MS_FABRIC_REPO/MS_FABRIC_NEW_SERVICES/Migration/DPV1/TEN Data Platform` (hub generated 2026-10-27 17:57). Resolved from name `RMA`.

### Service

- wf-2-migration-source-dataset: Synapse source ingestion up to SPOT_DB source
- Domain: **FIN**

### Target in Fabric

- Workspace: `Platform-Hub`
- Folder: `RMA`
- Lakehouse: `LH_SDS_RMA` (ingested directly from the source: databases => Files/raw (parquet), APIs and files => Files/landing => Files/raw; then tables; no shortcut)

### Size

- DPV1 objects mapped: 31 · pipelines 3 · notebooks 3 · linked services 3
- Complexity (repo-measured): Medium (109 objects); register: RMA Small
- Actions: translate 19, merge 5, drop 4, replace 2, rebuild 1

### Lineage with the other service offering

- Data products that read RMA in DPV1 (analysis only: they are migrated by Data Product Migration, never by this workflow):
  - **QHSES**: 1 DPV1 objects, e.g. notebook NTBK_INTELEX_MAPPING reads SPOT lake database SPOT_RMA
  - **RMA**: 2 DPV1 objects, e.g. pipeline PL_CHILD_META_SSP_RMA_DB_BUILD reads SPOT lake database SPOT_RMA
- What they will need is published at the end of S4 in `source-dataset-contract.json` (tables, DPV1 access paths, VL_MAIN names).
- Entry points: `PL_MASTER_RMA`, `PL_RAWDATA_RMA_TO_ADLS`
- Triggers: none in the repository

## Scope Identification: RMA


Rules applied to the DPV1 export (see skill `skill-scope-resolution`). Every object in `02-object-mapping.md` carries its evidence in "Found by".

| Rule | Objects |
|---|---|
| Catalog table | 18 |
| Used by | 6 |
| Scope folder | 3 |
| Called by | 2 |
| Entry point | 2 |

### Name check: 18 other DPV1 objects match "RMA"

- In the other service for this project: 13
- In other scopes: 4
- **Not included: 0** - confirm each one is out of scope or add it before building.

_Nothing to decide._

_The full list of matching objects is in `analysis/dpv1-inventory.md`._

## As-is Inventory (DPV1): RMA


### As-is tree

Where each object lives in the Synapse export, and what happens to it (🟢 converted, 🔵 merged, 🟣 replaced, ⚪ elsewhere, 🟠 decision, 🔴 not migrated).

```text
DPV1 · RMA (source dataset)/                    # 31 objects
├── ADLS data (catalog tables)/                 # 18 objects
│   └── dbo/                                    # 18 objects
│       ├── Actions                             # 🟢 translate => dbo.actions
│       ├── Business_Units                      # 🟢 translate => dbo.business_units
│       ├── Global_Business_Units               # 🟢 translate => dbo.global_business_units
│       ├── Iso4217_Currencies                  # 🟢 translate => dbo.iso4217_currencies
│       ├── Lookup_Types                        # 🟢 translate => dbo.lookup_types
│       ├── Lookup_Values                       # 🟢 translate => dbo.lookup_values
│       └── … +12 more
├── dataset/                                    # 3 objects
│   ├── DS_GENERIC_ASQL_METABASE_CATALOG        # 🔴 drop
│   ├── DS_SQLSERVER_RMA                        # 🔴 drop
│   └── rawGenericParquetDataSet                # 🔴 drop
├── linkedService/                              # 3 objects
│   ├── AzureDataLakeStorageRawZone             # 🔴 drop
│   ├── LS_CORE_SQLSERVER_RMA                   # 🟢 translate => CONN_RMA_SQL_SERVER_<ENV>
│   └── LS_PROJ_ASQL_METABASE_CATALOG           # 🟣 replace => [CATALOG].[rma_catalog] in the catalog warehouse
├── notebook/                                   # 3 objects
│   └── RMA/                                    # 3 objects
│       ├── NTBK_RMA_CHILD_FULL_RAW_TO_CLEAN    # 🔵 merge => NB_RMA_RAW_TO_DELTA
│       ├── NTBK_RMA_CHILD_META_RAW_TO_CLEAN    # 🔵 merge => NB_RMA_RAW_TO_DELTA
│       └── NTBK_RMA_MASTER_RAW_TO_CLEAN        # 🔵 merge => NB_RMA_RAW_TO_DELTA
├── pipeline/                                   # 3 objects
│   ├── 01_CORE_DATA/                           # 2 objects
│   │   └── 23_RMA/                             # 2 objects
│   │       ├── PL_CLNDATA_RMA_TO_ADLS          # 🔵 merge => PL_RMA_RAW_TO_DELTA
│   │       └── PL_RAWDATA_RMA_TO_ADLS          # 🔵 merge => PL_RMA_SOURCE_TO_RAW
│   └── 99_EXTERNAL_ORCHESTRATION/
│       └── 21_RMA/
│           └── PL_MASTER_RMA                   # 🟢 rebuild => PL_RMA_MASTER_ORCHESTRATOR
└── sqlscript/
    └── Catalog_RMA                             # 🟣 replace => [CATALOG].[rma_catalog]
```

_Pipelines, linked services, notebooks, datasets and SQL of the scope: `analysis/dpv1-inventory.md`._
