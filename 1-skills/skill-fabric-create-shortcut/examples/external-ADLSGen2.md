---
title: External Shortcut to ADLS Gen2 - Template & Example
description: Template and example for creating external shortcuts to ADLS Gen2.
---

## File - `shortcuts.metadata.json`

### Template

shortcuts.metadata.json
```json
[
  {
    "name": "{{shortcut_name}}",
    "path": "/Tables/{{schema_name}}",
    "target": {
      "type": "AdlsGen2",
      "adlsGen2": {
        "connectionId": "$(/**/{{VL_NAME}}/{{ADLS_FABRIC_CONNECTION_VARIABLE_NAME}})",
        "location": "$(/**/{{VL_NAME}}/{{ADLS_DFS_ENDPOINT_VARIABLE_NAME}})",
        "subpath": "/{{ADLS_CONTAINER}}/{{ADLS_BASE_PATH}}/{{SUBPATH}}"
      }
    }
  }
]
```

**Instructions**:  
- `{{shortcut_name}}` must be sanitized and lowercase.
- `{{schema_name}}` is most of the time `dbo`
- `connectionId` and `location` must remain Variable Library tokens.
- `{{ADLS_DFS_ENDPOINT_VARIABLE_NAME}}` and `{{ADLS_FABRIC_CONNECTION_VARIABLE_NAME}}` must remain variable names.
- `{{ADLS_CONTAINER}}`, `{{ADLS_BASE_PATH}}`, and `{{SUBPATH}}` must preserve the exact same case and spelling as the original ADLS folder structure.


### Example

shortcuts.metadata.json
```json
[
  {
    "name": "erp_sales_orders",
    "path": "/Tables/dbo",
    "target": {
      "type": "AdlsGen2",
      "adlsGen2": {
        "connectionId": "$(/**/VL_MAIN/ADLS_CLEANSED_CONNECTION_ID)",
        "location": "$(/**/VL_MAIN/ADLS_CLEANSED_DFS_ENDPOINT)",
        "subpath": "/azblb01cleansed/CLEANSED/DATASOURCE=MDM_API/workpackagesflatten"
      }
    }
  }
]
```