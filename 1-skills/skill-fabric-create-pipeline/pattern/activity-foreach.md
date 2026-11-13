# Activity Pattern — ForEach

Iterates over a collection (typically the output of a `Lookup`) and runs inner activities per item. Enables metadata-driven processing.

- `type`: `ForEach`
- `typeProperties.items`: the collection expression to iterate.
- `typeProperties.isSequential`: `false` for parallel (default), `true` for ordered.
- `typeProperties.batchCount`: max parallel iterations (when not sequential).
- `typeProperties.activities`: the inner activity array (each item is `item()`).

## Variant — Parallel stored-procedure execution driven by a Lookup

source: ✅ microsoft_doc | ✅ ten_curated

```json
{
  "name": "For_each_procedure",
  "type": "ForEach",
  "dependsOn": [
    { "activity": "Get_procedure_list", "dependencyConditions": [ "Succeeded" ] }
  ],
  "typeProperties": {
    "items": {
      "value": "@activity('Get_procedure_list').output.value",
      "type": "Expression"
    },
    "batchCount": 10,
    "activities": [
      {
        "name": "Run_procedure",
        "type": "SqlServerStoredProcedure",
        "dependsOn": [],
        "policy": {
          "timeout": "0.12:00:00",
          "retry": 1,
          "retryIntervalInSeconds": 30,
          "secureInput": false,
          "secureOutput": false
        },
        "typeProperties": {
          "storedProcedureName": {
            "value": "@{item().SCHEMA_NAME}.@{item().PROCEDURE_NAME}",
            "type": "Expression"
          }
        },
        "connectionSettings": {
          "name": "<AI_GENERATED_SLUG: random UUID v4 with hyphens replaced by underscores, e.g. a1b2c3d4_e5f6_7890_abcd_ef1234567890>",
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
      }
    ]
  }
}
```

Notes:
- Reference item fields with `@item().<FIELD>` (or `@{item().<FIELD>}` inside a string).
- Set `isSequential: true` and remove `batchCount` when ordering matters.
