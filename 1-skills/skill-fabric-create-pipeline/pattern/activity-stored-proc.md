# Activity Pattern — Stored Procedure

Executes a stored procedure on a Fabric Warehouse (or SQL endpoint).

- `type`: `SqlServerStoredProcedure`
- Key property: `typeProperties.storedProcedureName` (optionally `storedProcedureParameters`).
- The target warehouse is referenced through the activity-level `connectionSettings` object (NOT `linkedService`).

## General rules

- `connectionSettings.name`: auto-generated slug — AI must generate a random UUID v4, formatted as **lowercase with underscores replacing hyphens** (e.g. `"a1b2c3d4_e5f6_7890_abcd_ef1234567890"`). Never leave this as a placeholder; always generate a concrete value. Do not replace if exists.
- `externalReferences.connection`: the connection ID of the connection used to connect to the Warehouse — retrieve it from `2-config/technical-setup/`.
- `policy.timeout`: default `0.02:00:00` (2 hours).
- `policy.retry`: default 2 retries, 30-second interval.
- **Same workspace rule**: when the target item is in the **same** workspace as the pipeline, set `workspaceId` to `"00000000-0000-0000-0000-000000000000"` and `artifactId` to the item's **logicalId** (found in the item's `.platform` file in `REPO-FABRIC-DEPLOYMENT`).
- **Different workspace rule**: when the target item is in a **different** workspace, set both `workspaceId` and `artifactId` from the Variable Library (physical/item IDs, not logicalIds).

## Variant A — Warehouse in the SAME workspace

source: ✅ microsoft_doc | ✅ ten_curated

- `artifactId`: the **logicalId** of the warehouse — found in the warehouse's `.platform` file in `REPO-FABRIC-DEPLOYMENT`.
- `workspaceId`: hardcoded to `"00000000-0000-0000-0000-000000000000"` (same-workspace sentinel value).
- `endpoint`: resolved from the Variable Library — use the exact variable name as defined in the library (SNAKE_UPPER_CASE, no import-time prefix).

```json
{
  "name": "Load_DIM_CUSTOMER",
  "type": "SqlServerStoredProcedure",
  "dependsOn": [],
  "policy": {
    "timeout": "0.02:00:00",
    "retry": 2,
    "retryIntervalInSeconds": 30,
    "secureInput": false,
    "secureOutput": false
  },
  "typeProperties": {
    "storedProcedureName": "PRC.SP_LOAD_DIM_CUSTOMER",
    "storedProcedureParameters": {
      "LoadMode": {
        "value": {
          "value": "@pipeline().parameters.LOAD_MODE",
          "type": "Expression"
        },
        "type": "String"
      }
    }
  },
  "connectionSettings": {
    "name": "<AI_GENERATED_SLUG: random UUID v4 with hyphens replaced by underscores, e.g. a1b2c3d4_e5f6_7890_abcd_ef1234567890>",
    "properties": {
      "annotations": [],
      "type": "DataWarehouse",
      "typeProperties": {
        "artifactId": "<WH_LOGICAL_ID from .platform file>",
        "endpoint": "@pipeline().libraryVariables.SQL_ENDPOINT",
        "workspaceId": "00000000-0000-0000-0000-000000000000"
      },
      "externalReferences": {
        "connection": "<WH_CONN_ID from 2-config/technical-setup/>"
      }
    }
  }
}
```

## Variant B — Warehouse in a DIFFERENT workspace (Variable Library)

source: ✅ ten_curated

When the target warehouse is in a different workspace, both `artifactId` (physical item ID) and `workspaceId` are resolved from the Variable Library:

```json
{
  "name": "Load_FACT_SALES",
  "type": "SqlServerStoredProcedure",
  "dependsOn": [],
  "policy": {
    "timeout": "0.02:00:00",
    "retry": 2,
    "retryIntervalInSeconds": 30,
    "secureInput": false,
    "secureOutput": false
  },
  "typeProperties": {
    "storedProcedureName": "PRC.SP_LOAD_FACT_SALES"
  },
  "connectionSettings": {
    "name": "<AI_GENERATED_SLUG: random UUID v4 with hyphens replaced by underscores, e.g. a1b2c3d4_e5f6_7890_abcd_ef1234567890>",
    "properties": {
      "annotations": [],
      "type": "DataWarehouse",
      "typeProperties": {
        "artifactId": "@pipeline().libraryVariables.WH_ID",
        "endpoint": "@pipeline().libraryVariables.WH_SQL_ENDPOINT",
        "workspaceId": "@pipeline().libraryVariables.WH_WORKSPACE_ID"
      },
      "externalReferences": {
        "connection": "<WH_CONN_ID from 2-config/technical-setup/>"
      }
    }
  }
}
```

Required `libraryVariables` block (at `properties` root):

```json
"libraryVariables": {
  "WH_<DATA_PRODUCT_GROUP>_ID": {
    "type": "String",
    "variableName": "WH_<DATA_PRODUCT_GROUP>_ID",
    "libraryName": "VL_MAIN"
  },
  "WH_<DATA_PRODUCT_GROUP>_SQL_ENDPOINT": {
    "type": "String",
    "variableName": "WH_<DATA_PRODUCT_GROUP>_SQL_ENDPOINT",
    "libraryName": "VL_MAIN"
  },
  "WH_<DATA_PRODUCT_GROUP>_WORKSPACE_ID": {
    "type": "String",
    "variableName": "WH_<DATA_PRODUCT_GROUP>_WORKSPACE_ID",
    "libraryName": "VL_MAIN"
  }
}
```

> Variable names used above (`WH_<DATA_PRODUCT_GROUP>_ID`, `WH_<DATA_PRODUCT_GROUP>_SQL_ENDPOINT`, `WH_<DATA_PRODUCT_GROUP>_WORKSPACE_ID`) are illustrative and contain place holders. Use the actual variable names defined in the Variable Library for that workspace.

`<WH_CONN_ID>` is read from `2-config/technical-setup/` and hardcoded (it is environment-specific, not workspace-specific).
