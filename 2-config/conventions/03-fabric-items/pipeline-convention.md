---
description: Convention for pipeline naming and organization in the Fabric data platform.
status: proposal
origin: master
---

# Pipeline convention

The purpose of this document is to define conventions for pipeline naming and organization in the context of the FABRIC data platform.

**Table of contents:**
1. [Pipeline naming rule](#pipeline-naming-rule)
2. [Parameters, variables, and variables from Variable Library](#parameters-variables-and-variables-from-variable-library)

## Pipeline Naming rule

### General pattern for pipeline names

**Canonical name:**
`PL_<OBJECT>_<ACTIVITY>`

With:
- `<OBJECT>`: source name or data product name or any other object of interest
- `<ACTIVITY>`: activity or purpose of the pipeline
    - Examples: `MASTER_ORCHESTRATOR`, `SOURCE_TO_RAW`, `RAW_TO_DELTA`, `DELTA_TO_GOLD`, `DATA_QUALITY_CHECKS`, `ANOMALY_DETECTION`, etc.

**Examples:**

| Item | Convention |
| --- | --- |
| Master orchestrator pipeline | `PL_<SOURCE_NAME>_MASTER_ORCHESTRATOR` |
| Source to RAW pipeline | `PL_<SOURCE_NAME>_SOURCE_TO_RAW` |
| Processing a Data Product | `PL_<DATA_PRODUCT_NAME>_PROCESS_DATA_PRODUCT` |
| Processing dimension tables in a Data Product | `PL_<DATA_PRODUCT_NAME>_PROCESS_DIMS` |
| Processing fact tables in a Data Product | `PL_<DATA_PRODUCT_NAME>_PROCESS_FACTS` |


### Incremental Pipeline Suffix Rule

- **Default (hybrid):** A single `PL_<OBJECT>_SOURCE_TO_RAW` pipeline with a `LoadMode` parameter (`FULL` / `INCREMENTAL`). No suffix.
- **Dual-deploy exception:** If a source needs a full-load pipeline and an incremental-load pipeline deployed **at the same time**, append `_FULL` and `_INC` suffixes respectively:
  - `PL_<OBJECT>_SOURCE_TO_RAW_FULL` 
  - `PL_<OBJECT>_SOURCE_TO_RAW_INC`
  
## Parameters, variables, and variables from Variable Library
- Do not prefix dynamic values based on their types (parameter, variable, variable from VL), indeed:
  - Pipeline parameters are invoked with `@pipeline().parameters.<PARAMETER_NAME>`
  - Variables are invoked with `@variables('VARIABLE_NAME')`
  - VL Variables are invoked with `@pipeline().libraryVariables.<VARIABLE_NAME>`
- Pipeline parameters: 
  - UPPER_SNAKE_CASE (to convey the idea that they do not change during the pipeline execution)
  - follow the object-property-data type pattern, e.g., `TARGET_DATABASE_NAME`, `TARGET_DATABASE_ID`, `RETRY_COUNT`, `RETRY_INTERVAL_IN_SECONDS`, etc.
- Variables from VL:
  - Variable should have the same name as in the VL (should be UPPER_SNAKE_CASE); do not add prefix
- Pipeline variables:
  - camelCase (to convey the idea that they can change during the pipeline execution)
  - follow the `objectProperty[DataType]` pattern, e.g., `pipelineStartTime`, `tableName`, `tableId`, `schemaName`, `schemaId`, `filePath`, `fileName`, `fileSize`, `rowCount`, etc.
  
## Activity naming rule

### Key rules
- Use sentence case
- Keep it short and simple
- Follow the canonical name

**Canonical name:**  

`[<optional part>] <Action> <object> [<optional part>]`  

With:
  - `<Action>`: action performed by the activity
    - Examples: `Extract`, `Transform`, `Load`, `Validate`, `Notify`, etc.
  - `<Object>`: source name, data product name, table name, or any other object of interest. In case the activity is a generic one (e.g. in a `ForEach`), the object can be a placeholder (e.g. `table`, `file`, etc.).

**Examples:**

| Item | Convention |
| --- | --- |
| Extract data from source | `Extract Oracle table` |
| Transform RAW to DELTA | `Load raw to delta` |
| Load DELTA to GOLD | `Load ORDER_FACT`, `Load silver table` |
| Data quality checks | `Check data quality for table`, `Check data quality for ORDER_DIM` |