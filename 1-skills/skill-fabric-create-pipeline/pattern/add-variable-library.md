# Pattern — Add Variable Library

Declares the `libraryVariables` block at the `properties` root of `pipeline-content.json` to make Variable Library variables available via `@pipeline().libraryVariables.<VAR>` expressions.

## General rules

- Declare **only the variables actually used** by activities in the pipeline.
- Variable names must match the Variable Library exactly (SNAKE_UPPER_CASE). Do **not** add an import-time prefix.
- `libraryName` is always `"VL_MAIN"`.
- One entry per variable; `variableName` and the key must be identical.

## Pattern

```json
{
  "name": "<PIPELINE_NAME>",
  "objectId": "<PIPELINE_OBJECT_ID>",
  "properties": {
    "activities": [
      // ... pipeline activities ...
    ],
    "libraryVariables": {
      "MY_VARIABLE_1": {
        "type": "String",
        "variableName": "MY_VARIABLE_1",
        "libraryName": "VL_MAIN"
      },
      "MY_VARIABLE_2": {
        "type": "String",
        "variableName": "MY_VARIABLE_2",
        "libraryName": "VL_MAIN"
      }
    }
  }
}
```

## Example (real)

source: ✅ ten_curated

Single variable (`WH_SERVICENOW_BI_SQL_ENDPOINT`) used by both a Lookup and a Stored Procedure activity in the same pipeline:

```json
{
  "name": "PL_SILV_SERVICENOW_PROCESS_DIM",
  "objectId": "5b320d0b-a46c-4440-9ae0-4a9233cbdecc",
  "properties": {
    "activities": [
      // ... Lookup and StoredProcedure activities referencing @pipeline().libraryVariables.WH_SERVICENOW_BI_SQL_ENDPOINT ...
    ],
    "libraryVariables": {
      "WH_SERVICENOW_BI_SQL_ENDPOINT": {
        "type": "String",
        "variableName": "WH_SERVICENOW_BI_SQL_ENDPOINT",
        "libraryName": "VL_MAIN"
      }
    }
  }
}
```