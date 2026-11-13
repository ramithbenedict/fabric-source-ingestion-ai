---
title: Internal Shortcut to Lakehouse - Template & Example
description: Template and example for creating internal shortcuts to Lakehouse.
---

## File - `shortcuts.metadata.json`

Note: the template and the example already incorporate some T.EN conventions.

### Template

shortcuts.metadata.json
```json
[
  {
    "name": "{{shortcut_name}}",
    "path": "/Tables/{{schema_name}}",
    "target": {
      "type": "OneLake",
      "oneLake": {
        "path": "Tables/{{schema_name}}/{{table_name}}",
        "itemId": "$(/**/VL_MAIN/{{onelake_item_id_variable_name}})",
        "workspaceId": "$(/**/VL_MAIN/{{onelake_workspace_id_variable_name}})"
      }
    }
  }
]
```

**Instructions**:  
- `name` must be sanitized and lowercase.
- `{{schema_name}}` is most of the time `dbo`
- `itemId` and `workspaceId` must remain Variable Library tokens.


### Example

shortcuts.metadata.json
```json
[
  {
    "name": "cv_full",
    "path": "/Tables/dbo",
    "target": {
      "type": "OneLake",
      "oneLake": {
        "path": "Tables/dbo/cv_full",
        "itemId": "$(/**/VL_MAIN/LH_SDS_FLOWCASE_ID)",
        "workspaceId": "$(/**/VL_MAIN/LH_SDS_FLOWCASE_WORKSPACE_ID)"
      }
    }
  },
  {
    "name": "project_full",
    "path": "/Tables/dbo",
    "target": {
      "type": "OneLake",
      "oneLake": {
        "path": "Tables/dbo/project_full",
        "itemId": "$(/**/VL_MAIN/LH_SDS_FLOWCASE_ID)",
        "workspaceId": "$(/**/VL_MAIN/LH_SDS_FLOWCASE_WORKSPACE_ID)"
      }
    }
  },
  {
    "name": "users",
    "path": "/Tables/dbo",
    "target": {
      "type": "OneLake",
      "oneLake": {
        "path": "Tables/dbo/users",
        "itemId": "$(/**/VL_MAIN/LH_SDS_FLOWCASE_ID)",
        "workspaceId": "$(/**/VL_MAIN/LH_SDS_FLOWCASE_WORKSPACE_ID)"
      }
    }
  }
]
```