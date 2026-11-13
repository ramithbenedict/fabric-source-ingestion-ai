---
title: Fabric Create Lakehouse - Template
description: Fixed output contract for WF1 Stage 2 lakehouse-only Git artifacts.
author: Core Data Team
ms.date: 2026-05-05
ms.topic: reference
---

## File 1 - `.platform`

```json
{
  "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
  "metadata": {
    "type": "Lakehouse",
    "displayName": "<LAKEHOUSE_DISPLAY_NAME>"
  },
  "config": {
    "version": "2.0",
    "logicalId": "<RESOLVED_LOGICAL_ID>"
  }
}
```

## File 2 - `lakehouse.metadata.json`

```json
{"defaultSchema":"dbo"}
```

## Execution Report Template

```markdown
## WF1 Stage 2 Execution Report - Fabric Lakehouse Generation

**Date:** <ISO_DATETIME>
**Source:** <SOURCE_NAME>
**Status:** SUCCESS

## Configuration

| Field | Value |
| --- | --- |
| Source type | <DPv1 or External> |
| Workspace folder | <WORKSPACE_FOLDER> |
| Lakehouse display name | <LAKEHOUSE_NAME> |
| Destination | <Fabric deployment repo or AI project staging> |
| logicalId source | <reused from repo or Fabric, or freshly generated> |

## Generated Files

* `<OUTPUT_PATH>/.platform`
* `<OUTPUT_PATH>/lakehouse.metadata.json`

## Git Sync Instructions

<include the Stage 2 handoff block>
```
