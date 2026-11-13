# Activity Pattern — Copy Data

Copies data from a source store to a sink store.

- `type`: `Copy`
- Key blocks: `typeProperties.source`, `typeProperties.sink`, optional `translator`.
- Each side embeds a `datasetSettings` with its own `linkedService` (or `externalReferences.connection` for external sources).

## Variant A — Lakehouse table → Lakehouse (Parquet), SAME workspace

source: ✅ microsoft_doc | ✅ ten_curated

```json
{
  "name": "Copy_LH_to_LH",
  "type": "Copy",
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
      "type": "LakehouseTableSource",
      "datasetSettings": {
        "type": "LakehouseTable",
        "typeProperties": { "table": "<SOURCE_TABLE>" },
        "schema": [],
        "linkedService": {
          "name": "<AI_GENERATED_SLUG: random UUID v4 with hyphens replaced by underscores, e.g. a1b2c3d4_e5f6_7890_abcd_ef1234567890>",
          "properties": {
            "type": "Lakehouse",
            "typeProperties": {
              "artifactId": "<LAKEHOUSE_GUID>",
              "workspaceId": "00000000-0000-0000-0000-000000000000",
              "rootFolder": "Tables"
            },
            "annotations": []
          }
        },
        "annotations": []
      }
    },
    "sink": {
      "type": "ParquetSink",
      "formatSettings": { "type": "ParquetWriteSettings", "enableVertiParquet": true },
      "storeSettings": { "type": "LakehouseWriteSettings" },
      "datasetSettings": {
        "type": "Parquet",
        "typeProperties": {
          "location": { "type": "LakehouseLocation", "folderPath": "<TARGET_FOLDER>" },
          "compressionCodec": "snappy"
        },
        "schema": [],
        "linkedService": {
          "name": "<AI_GENERATED_SLUG: random UUID v4 with hyphens replaced by underscores, e.g. a1b2c3d4_e5f6_7890_abcd_ef1234567890>",
          "properties": {
            "type": "Lakehouse",
            "typeProperties": {
              "artifactId": "<LAKEHOUSE_GUID>",
              "workspaceId": "00000000-0000-0000-0000-000000000000",
              "rootFolder": "Files"
            },
            "annotations": []
          }
        },
        "annotations": []
      }
    },
    "translator": {
      "type": "TabularTranslator",
      "typeConversion": true,
      "typeConversionSettings": { "allowDataTruncation": true, "treatBooleanAsNumber": false }
    },
    "enableStaging": false
  }
}
```

## Variant B — External database (e.g. Oracle) → Lakehouse

source: ✅ ten_curated

The external source uses `externalReferences.connection` (a connection GUID configured after import), not a `linkedService`.

```json
"source": {
  "type": "OracleSource",
  "queryTimeout": "02:00:00",
  "partitionOption": "None",
  "datasetSettings": {
    "type": "OracleTable",
    "typeProperties": { "schema": "<SRC_SCHEMA>", "table": "<SRC_TABLE>" },
    "schema": [],
    "externalReferences": { "connection": "<CONNECTION_GUID>" },
    "annotations": []
  }
}
```

## Cross-workspace note

source: ✅ ten_curated

When the source or sink store lives in a different workspace, replace hardcoded `artifactId` / `workspaceId` with Variable Library references (`@pipeline().libraryVariables.<VAR>` and `workspaceId": "@pipeline().DataFactory"`) and declare the variables in the pipeline `libraryVariables` block.
