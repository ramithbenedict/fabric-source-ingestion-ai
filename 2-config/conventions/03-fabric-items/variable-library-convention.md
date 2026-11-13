---
description: General rules and conventions for variable library items in Microsoft Fabric.
status: proposal
origin: master
---

# Variable library conventions

## General rules
- **One variable library per workspace named `VL_MAIN`** created in the workspace root and shared across all pipelines and notebooks in the workspace. This variable library contains variables that are commonly used across multiple pipelines and notebooks, such as connection strings, credentials, and other configuration values.
- For specific cases, additional variable libraries can be created for specific purposes. `VL_<SCOPE>` can be used as a naming convention for these variable libraries, where `<SCOPE>` indicates the specific scope or purpose of the variable library.
- For any variable library, the compulsory value sets are:
    - `Default` value set for default values, it should contain the DEV values by default.
    - `DEV` value set for development environment values.
    - `UAT` value set for user acceptance testing environment values.
    - `PRD` value set for production environment values.
- Value sets can be added in case values need to be modified for when working in a feature workspace, following the naming convention `FEATURE_X`, e.g., `FEATURE_NEW_INGESTION`, `FEATURE_UPDATE_SCHEMA`. The names are short lived and can therefore be kept short at the cost of being less descriptive.
- **A note describing each variable should be added to every variable in the variable library.**

## Naming rules for variables

**Rules applied to variables names in a variable library:**
- must be in UPPERCASE_SNAKE_CASE.
- must be prefixed by their object type:
    - `ADLS_` for ADLS connection strings
    - `LH_` for Lakehouse items
    - `WH_` for Warehouse items
    - other prefixes may be used as long as they are consistent and indicative of the variable's purpose.
- must be suffixed by their information type:
    - `_ID` for Guids
    - `_CONN_ID` for connection IDs
    - `_NAME` for names
    - `_CONN_NAME` for connection names
    - `_ENDPOINT` for endpoints
    - `_DFS_ENDPOINT` for DFS endpoints
    - `_URL` for URLs
    - `_FLAG` for Booleans
    - other suffixes may be used as long as they are consistent and indicative of the variable's information type.
- should not reflect environment as this should be handled in the value sets, e.g. `ADLS_CLEANSED_CONN_ID` instead of `DP_ADLS_CLEANSED_CONN_ID_DEV` or `DP_ADLS_CLEANSED_CONN_ID_UAT`. However, if in rare instances the goal is to reference a specific environment's value (e.g., the main dev workspace) regardless of the item's environment, then the variable name can reflect that, e.g. `DEV_WORKSPACE_ID`.

### Examples:
- `ADLS_RAW_CONN_ID` for the Fabric connection id used to connect to the raw ADLS account.
- `ADLS_CLEANSED_CONN_ID` for the Fabric connection id used to connect to the cleansed ADLS account.
- `ADLS_CLEANSED_DFS_ENDPOINT` for a string variable containing the DFS endpoint (datalake storage endpoint) of the cleansed ADLS account.
- `ADLS_CLEANSED_STORAGE_ACCOUNT_NAME` for the storage account name of the cleansed ADLS account.
- `ADLS_CLEANSED_CONTAINER_NAME` for the container name in the cleansed ADLS account.
- `LH_SDS_GAIA_ID` for the Fabric item id of the lakehouse named `LH_SDS_GAIA`.
- `LH_SDS_GAIA_WORKSPACE_ID` for the Fabric workspace id of the lakehouse named `LH_SDS_GAIA`.

## Example of folder structure in repository

```text
DP_SDS_<DOMAIN_CODE>_<ENV>/
├── <SOURCE_NAME>/
│   └── ...
└── VL_MAIN.VariableLibrary/
    ├── .platform
    ├── settings.json
    ├── variables.json
    └── valueSets/
        ├── DEV.json
        ├── FEATURE_DIM_PEOPLE.json
        ├── UAT.json
        └── PRD.json
```