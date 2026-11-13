---
title: Fabric Create Lakehouse - Examples
description: Worked examples for generating WF1 Stage 2 lakehouse Git artifacts.
author: Core Data Team
ms.date: 2026-05-05
ms.topic: reference
---

## Example 1 - New Lakehouse

**Scenario:** Create a new lakehouse for `rma` in `DIGI_SOURCE_WS_DEV`.

**Input:**

```yaml
source_name: rma
domain_code: DIG
deployment_repo_path: C:\Ten_Fabric_Data_Platform\fabric_deployment_repository\REPO-FABRIC-DEPLOYMENT
workspace_folder: DIGI_SOURCE_WS_DEV
lakehouse_name: LH_DIG_BRON_RMA
destination: deployment repo
```

**Expected Result:**

* A fresh UUID v4 is generated because no matching lakehouse exists.
* `.platform` and `lakehouse.metadata.json` are written to both deployment and staging paths.

## Example 2 - Existing Lakehouse Reuse

**Scenario:** Refresh an existing lakehouse definition for `finance`.

**Expected Result:**

* The existing `logicalId` is reused from the current `.platform` file.
* Existing files are overwritten in place.
* No duplicate `.Lakehouse` folder is created.
