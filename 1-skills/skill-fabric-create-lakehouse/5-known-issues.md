---
title: Fabric Create Lakehouse - Known Issues
description: Execution-derived issues and workarounds for the WF1 Stage 2 lakehouse generation skill.
author: Core Data Team
ms.date: 2026-05-05
ms.topic: reference
---

## Known Issues And Workarounds

| # | Date | Issue | Severity | Status | Workaround |
| --- | --- | --- | --- | --- | --- |
| 1 | 2026-05-05 | Invalid or all-zero `logicalId` in an existing `.platform` file can cause duplicate lakehouse sync conflicts. | high | Open | Treat all-zero or empty `logicalId` values as invalid and replace them with a fresh UUID v4. |
| 2 | 2026-05-05 | Writing a new lakehouse folder instead of overwriting the existing folder can create duplicate item names in Fabric. | high | Open | Reuse the existing lakehouse folder and overwrite files in place whenever the same lakehouse already exists in the same workspace. |
| 3 | 2026-05-05 | Wrong workspace Git sync folder prevents the lakehouse from appearing after commit. | medium | Open | Confirm that the repo workspace folder matches the Fabric Git integration sync folder exactly. |
