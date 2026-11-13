---
name: skill-fabric-create-warehouse
description: Generate Microsoft Fabric Warehouse Git artifacts from the bundled example template. Use when creating a new Warehouse item definition.
status: active
origin: master
argument-hint: "Provide the target warehouse name and Fabric workspace folder."
---

# Fabric Create Warehouse

## Objective

Generate Fabric Warehouse Git artifacts by copying and adapting the canonical example. The skill creates only the Warehouse item definition files required by Fabric Git integration.

### In scope

- Generate one Fabric Warehouse artifact folder from the bundled example input.
- Adapt the generated artifacts to the requested warehouse name and workspace folder.
- Preserve existing Warehouse identity when regenerating artifacts.

### Not in scope

- Does not create non-Warehouse Fabric items or SQL database objects.
- Does not deploy artifacts, execute Git commands, or modify the example folder.

## References
<!-- Human-facing manifest. Actual reads happen inline in Workflow. -->
- **Warehouse artifacts example**
  - path: `./template/WH_DPG_SERVICENOW.Warehouse/`
- **Warehouse artifacts template**:
  - path: `./example/WH_NAME.Warehouse/`
- **Fabric Data Product Group workspace conventions**
  - path: [../../2-config/conventions/02-fabric-workspace/5-workspace-dpg-convention.md](../../2-config/conventions/02-fabric-workspace/5-workspace-dpg-convention.md)
  - description: Naming and deployment folder conventions when applicable to the target workspace.

## Inputs
<!-- Human-facing manifest. Actual reads happen inline in Workflow. -->

### Existing assets
No inputs come from existing assets.

### User inputs
Use #tool:vscode/askQuestions to gather these inputs:
- ${WAREHOUSE_NAME}: Fabric Warehouse folder and display name, for example `WH_DPG_SERVICENOW`.
- ${WORKSPACE_FOLDER}: Fabric Workspace folder where the artifacts will be generated, for example `DP_DPG_GAIA`.

### Inferred values
- {{WAREHOUSE_DESCRIPTION}}
- {{TARGET_WAREHOUSE_FOLDER}}: Infer from {{WORKSPACE_FOLDER}}, {{WAREHOUSE_NAME}}, and the Fabric workspace convention.
  - e.g., `REPO-FABRIC-DEPLOYMENT/DP_DPG_GAIA/WH_DPG_SERVICENOW.Warehouse`
- {{LOGICAL_ID}}: Reuse from an existing matching `.platform`; otherwise generate UUID v4.

If it cannot be inferred, use #tool:vscode/askQuestions to gather any missing values.

## General Instructions
- Treat the template and the example (see inputs) as the canonical input template.
- Ask the user before overwriting an existing target Warehouse folder.
- Validate that generated JSON is parseable and generated XML is well formed.

## Workflow Instructions

0. Use #tool:todo to create or update the todo with the following steps. Each step must be a single todo item.
  1. Create WH - Read the template and example files
  2. Create WH - Collect missing inputs
  3. Create WH - Resolve target folder
  4. Create WH - Generate artifacts
  5. Create WH - Validate output
1. Read the template and example files:
  - #tool:read/readFile for files in `./template/WH_DPG_SERVICENOW.Warehouse/` and `./example/WH_NAME.Warehouse/`.
2. Collect missing user inputs with #tool:vscode/askQuestions:
  - {{WAREHOUSE_NAME}}: Fabric Warehouse folder and display name, for example `WH_DPG_SERVICENOW`.
  - {{WORKSPACE_FOLDER}}: Fabric Workspace folder where the artifacts will be generated, for example `DP_DPG_GAIA`.
  - Make proposition using [Fabric workspace conventions](../../2-config/conventions/02-fabric-workspace/5-workspace-dpg-convention.md).
3. Infer {{TARGET_WAREHOUSE_FOLDER}}, {{WAREHOUSE_DESCRIPTION}}
  - #tool:read/readFile [Fabric workspace conventions](../../2-config/conventions/02-fabric-workspace/5-workspace-dpg-convention.md) to determine the target folder path.
  - Infer {{TARGET_WAREHOUSE_FOLDER}} from {{WORKSPACE_FOLDER}}, {{WAREHOUSE_NAME}}
  - Infer {{WAREHOUSE_DESCRIPTION}} from context
  - Infer {{LOGICAL_ID}} from existing `.platform` or generate a new UUID v4.
4. Create or update the target Warehouse folder.
    - Generate `.platform` by updating template metadata.
    - Generate {{WAREHOUSE_NAME}}.sqlproj by updating template values.
    - Do not change {{Dataset_Name}} in xmla.json ; it is not a variable to change.
5. Validate file names, JSON syntax, XML syntax, and expected output paths.

## Output

- {{TARGET_WAREHOUSE_FOLDER}}/.platform
- {{TARGET_WAREHOUSE_FOLDER}}/{{WAREHOUSE_NAME}}.sqlproj
- {{TARGET_WAREHOUSE_FOLDER}}/xmla.json

## Completion Check

- [ ] The example folder remains unchanged.
- [ ] {{Dataset_Name}} in xmla.json is not changed and kept as-is.