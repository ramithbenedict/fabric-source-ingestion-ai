# Activity Pattern — Lookup

Reads rows (or a first row) from a Warehouse or Lakehouse to drive downstream logic (e.g. a `ForEach`).

- `type`: `Lookup`
- `firstRowOnly`: `false` to return all rows, `true` for a single row.
- The source object is referenced through `datasetSettings.linkedService` (Warehouse or Lakehouse).

## Variant A — Warehouse is in SAME workspace as the pipeline

source: ✅ microsoft_doc | ✅ ten_curated

- `artifactId`: the **logicalId** of the warehouse — found in the warehouse's `.platform` file in `REPO-FABRIC-DEPLOYMENT`.
- `endpoint`: always resolved from the Variable Library — name pattern `<WH_NAME>_SQL_ENDPOINT`.
- `workspaceId`: hardcoded to `"00000000-0000-0000-0000-000000000000"` (same-workspace sentinel value).
- `connectionSettings.name`: auto-generated slug (AI generates a UUID-based lowercase string, e.g. `"a1b2c3d4_e5f6_7890_abcd_ef1234567890"`).
- `externalReferences.connection`: the connection GUID for this warehouse — read `{{WH_CONN_ID}}` from `2-config/technical-setup/`.

```json
{
  "name": "Get_procedure_list",
  "type": "Lookup",
  "dependsOn": [],
  "policy": {
    "timeout": "0.12:00:00",
    "retry": 0,
    "retryIntervalInSeconds": 30,
    "secureInput": false,
    "secureOutput": false
  },
  "typeProperties": {
    "source": {
      "type": "DataWarehouseSource",
      "sqlReaderQuery": {
        "value": "SELECT SCHEMA_NAME(SCHEMA_ID) AS SCHEMA_NAME, NAME AS PROCEDURE_NAME FROM SYS.PROCEDURES WHERE SCHEMA_NAME(SCHEMA_ID) = 'PRC' ORDER BY NAME;",
        "type": "Expression"
      },
      "queryTimeout": "02:00:00",
      "partitionOption": "None"
    },
    "firstRowOnly": false,
    "datasetSettings": {
      "annotations": [],
      "type": "DataWarehouseTable",
      "schema": [],
      "typeProperties": {},
      "connectionSettings": {
        "name": "<AI_GENERATED_SLUG>",
        "properties": {
          "annotations": [],
          "type": "DataWarehouse",
          "typeProperties": {
            "artifactId": "<WH_LOGICAL_ID from .platform file>",
            "endpoint": "@pipeline().libraryVariables.<WH_NAME>_SQL_ENDPOINT",
            "workspaceId": "00000000-0000-0000-0000-000000000000"
          },
          "externalReferences": {
            "connection": "<WH_CONN_ID>"
          }
        }
      }
    }
  }
}
```

## Variant B — Warehouse is in a DIFFERENT workspace than the pipeline

source: ✅ ten_curated

Same as Variant A but `artifactId` and `workspaceId` are also resolved from the Variable Library:

```json
"connectionSettings": {
  "name": "<AI_GENERATED_SLUG>",
  "properties": {
    "annotations": [],
    "type": "DataWarehouse",
    "typeProperties": {
      "artifactId": "@pipeline().libraryVariables.<WH_NAME>_ID",
      "endpoint": "@pipeline().libraryVariables.<WH_NAME>_SQL_ENDPOINT",
      "workspaceId": "@pipeline().libraryVariables.<WH_NAME>_WORKSPACE_ID"
    },
    "externalReferences": {
      "connection": "<WH_CONN_ID>"
    }
  }
}
```

Declare `<WH_NAME>_SQL_ENDPOINT`, `<WH_NAME>_ID`, and `<WH_NAME>_WORKSPACE_ID` in the pipeline `libraryVariables` block. `<WH_CONN_ID>` is read from `2-config/technical-setup/` and hardcoded (it is environment-specific, not workspace-specific).

## Variant C — Lakehouse, SAME workspace as the pipeline

source: ✅ microsoft_doc

```json
{
  "name": "Lookup_LH_table",
  "type": "Lookup",
  "dependsOn": [],
  "policy": {
    "timeout": "0.12:00:00",
    "retry": 0,
    "retryIntervalInSeconds": 30,
    "secureInput": false,
    "secureOutput": false
  },
  "typeProperties": {
    "source": {
      "type": "LakehouseTableSource"
    },
    "firstRowOnly": false,
    "datasetSettings": {
      "annotations": [],
      "type": "LakehouseTable",
      "schema": [],
      "typeProperties": {
        "table": "<TABLE_NAME>"
      },
      "linkedService": {
        "name": "<AI_GENERATED_SLUG: random UUID v4 with hyphens replaced by underscores, e.g. a1b2c3d4_e5f6_7890_abcd_ef1234567890>",
        "properties": {
          "annotations": [],
          "type": "Lakehouse",
          "typeProperties": {
            "artifactId": "<LAKEHOUSE_GUID>",
            "workspaceId": "00000000-0000-0000-0000-000000000000",
            "rootFolder": "Tables"
          }
        }
      }
    }
  }
}
```

## Variant D — Lakehouse, DIFFERENT workspace than the pipeline

source: ✅ ten_curated

Same as Variant C but the Lakehouse `linkedService.typeProperties` references the Variable Library:

```json
"typeProperties": {
  "artifactId": "@pipeline().libraryVariables.LH_TARGET_ID",
  "workspaceId": "@pipeline().DataFactory",
  "rootFolder": "Tables"
}
```

Declare `LH_TARGET_ID` in the pipeline `libraryVariables` block.