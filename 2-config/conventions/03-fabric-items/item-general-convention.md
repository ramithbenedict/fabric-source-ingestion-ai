---
description: General rules for item naming and organization in Microsoft Fabric.
status: active
origin: master
---

# Item Convention

- This document covers general rules for item naming in Fabric.
- For specific item naming rules, please refer to the respective sections.
- For workspace, please refer to [workspace naming](../02-fabric-workspace/1-workspace-naming.md) for workspace naming rules.

## Fabric item naming convention

### General rules

Fabric item names must follow these rules:
- use `UPPER_SNAKE_CASE`
- use `_` as the only separator
- use only `A-Z`, `0-9`, and `_`
- start with the item prefix when a prefix exists for that item type
- use a prefix (see after)

### Prefixes

| Item Type | Prefix |
| --- | --- |
| Lakehouse | `LH` |
| Warehouse | `WH` |
| KQL database | `KQL` |
| SQL database | `SQL` |
| Pipeline | `PL` |
| Notebook | `NB` |
| Variable library | `VL` |
| Semantic Model | `SM` |
| Data agents | `AGT` |
| Power BI Report | `PBI` |
