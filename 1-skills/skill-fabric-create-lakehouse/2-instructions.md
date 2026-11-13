---
title: Fabric Create Lakehouse - Instructions
description: Execution instructions for generating WF1 Stage 2 lakehouse Git artifacts only.
imports_from:
  - path: 2-config/conventions/02-fabric-workspace/6-workspace-sds-convention.md
    purpose: lakehouse naming convention, deployment folder structure
  - path: 2-config/conventions/03-fabric-items/item-general-convention.md
    purpose: item prefixes and general naming rules for Lakehouse and Variable Library artifacts
  - path: 2-config/conventions/03-fabric-items/variable-library-convention.md
    purpose: variable library naming conventions used by dependent stages
---

## Inputs Required

```yaml
source_name: string
domain_code: string
deployment_repo_path: string
workspace_folder: string
lakehouse_name: string
destination: string
```

## Procedure

Follow these steps in order.

### Step 0 - Load Skill Assets

* Read `3-template.md`.
* Read `5-known-issues.md`.

### Step 1 - Validate Inputs and Stage 1 Context

* Read `source_name` and `domain_code` from `4-project-deliverables/1_source_data/<SOURCE_NAME>/1_framing/<SOURCE_NAME>_source_framing.md`.
* Do not ask again for source name or domain.
* Read the lakehouse naming convention from `2-config/conventions/02-fabric-workspace/6-workspace-sds-convention.md` (§ Lakehouse for Source Dataset).
* Ask a mandatory lakehouse naming confirmation question before any Stage 2 file generation.
* Use native MCQ format and always include these options for the naming question:
  * `A) <suggested lakehouse name from convention>`
  * Optional additional detected existing names (if any)
  * `Z) Other (user input)` as the last option
* Never skip this question, even when only one convention-aligned name is available.
* Never auto-accept the suggested name without an explicit user selection.
* Confirm `deployment_repo_path`, `workspace_folder`, and `destination` are known.
* Done condition: the Stage 2 context is complete.

### Step 2 - Resolve Output Paths

* If destination is deployment repo, write to `<DEPLOYMENT_REPO_PATH>/<WORKSPACE_FOLDER>/<SOURCE_NAME_UPPER>/<LAKEHOUSE_NAME>.Lakehouse/`.
* If destination is staging only, write to `4-project-deliverables/1_source_data/<SOURCE_NAME>/2_ingestion_scripts/fabric_git_artifacts/<SOURCE_NAME_UPPER>/<LAKEHOUSE_NAME>.Lakehouse/`.
* Always also write the staging copy to `4-project-deliverables/1_source_data/<SOURCE_NAME>/2_ingestion_scripts/fabric_git_artifacts/<SOURCE_NAME_UPPER>/<LAKEHOUSE_NAME>.Lakehouse/`.
* Done condition: both primary and staging output paths are resolved.

### Step 3 - Resolve Existing logicalId

* Scan `<DEPLOYMENT_REPO_PATH>/<WORKSPACE_FOLDER>/<SOURCE_NAME_UPPER>/` for a matching `.Lakehouse` folder and `.platform` file (canonical).
* If not found, scan legacy path `<DEPLOYMENT_REPO_PATH>/<WORKSPACE_FOLDER>/<SOURCE_NAME_UPPER>/Lakehouse/` for backward compatibility.
* If a valid non-zero `config.logicalId` exists for the same lakehouse in the same workspace, reuse it.
* If the `.platform` exists but the `logicalId` is all zeros, empty, or null, generate a fresh UUID v4.
* If not found in the repo, check Fabric for the same lakehouse name in the same workspace.
* If still not found, generate a fresh UUID v4.
* Done condition: `resolved_logical_id` is available.

### Step 4 - Generate `.platform`

* Use the exact template from `3-template.md`.
* Set `metadata.type` to `Lakehouse`.
* Set `metadata.displayName` to the confirmed lakehouse name.
* Set `config.logicalId` to the resolved value from Step 3.
* Done condition: `.platform` is ready for both output locations.

### Step 5 - Generate `lakehouse.metadata.json`

* Use the exact fixed content from `3-template.md`.
* Do not add or remove fields.
* Done condition: `lakehouse.metadata.json` is ready for both output locations.

### Step 6 - Write Outputs

* Write `.platform` and `lakehouse.metadata.json` to the primary destination.
* Write the same files to the staging copy destination.
* Overwrite existing files in place when the target lakehouse folder already exists.
* Done condition: both lakehouse files exist in the required destinations.

### Step 7 - Write Execution Report and Handoff

* Write the execution report using the template in `3-template.md`.
* Include source name, source type, workspace folder, lakehouse name, logicalId source, generated file paths, and next stage.
* Present Git commands for the user to run manually.
* Stop and wait for the user to confirm the lakehouse is visible in Fabric before Stage 2a or Stage 2b starts.
* Done condition: Stage 2 handoff is complete.

## Completion Checklist

* [ ] Stage 1 framing read automatically
* [ ] Lakehouse naming question asked with `A) suggested` + `Z) Other (user input)`
* [ ] Output paths resolved
* [ ] Existing `logicalId` reused when valid
* [ ] `.platform` generated
* [ ] `lakehouse.metadata.json` generated
* [ ] Primary output written
* [ ] Staging copy written
* [ ] Execution report written
* [ ] Handoff instructions shown

