---
name: skill-fabric-create-pipeline
description: Design and generate a Microsoft Fabric Data Pipeline Git artifact (.platform + pipeline-content.json) from an objective, requirements, and referenced Fabric items. Use when creating a new Fabric pipeline definition or scaffolding pipeline activities.
status: active
argument-hint: "Describe the pipeline objective, its requirements, and the Fabric items it references (warehouses, lakehouses, other pipelines)."
---

# Fabric Create Pipeline

## Objective
Generate Git artifacts for a Microsoft Fabric Data Pipeline. Generate (`.platform` and `pipeline-content.json`) inside a `<PIPELINE_NAME>.DataPipeline` folder. The skill turns an objective, requirements, and a set of referenced Fabric items into a valid, importable pipeline definition.

### In scope
- Generate the Data Pipeline artifacts from input information (requirements, design doc, etc.)
- Infer pipeline design if not provided

### Out of scope
- Does not deploy the pipeline, run Git operations, or create connections / linked service credentials.
- Does not create the referenced Fabric items themselves (warehouses, lakehouses, variable libraries).

## Inputs
<!-- Manifest for human reading. Actions to gather or infer inputs must be specified in Workflow Instructions. -->
### Existing assets
Use #tool:vscode/askQuestions to gather the following inputs:
- ${input:SOLUTION}: any Fabric workspace or database project to analyze to infer pipeline design and referenced items

### User inputs
Use #tool:vscode/askQuestions to gather the following user inputs:
- ${input:PIPELINE_INFORMATION}: objective, requirements, referenced items, or design document about the pipeline

### Inferred values
- {{PIPELINE_NAMES}}: derived from the objective and the pipeline naming convention.
- {{TARGET_FOLDER}}: derived from the target workspace folder and the workspace convention.
- {{LOGICAL_ID}}: reuse from an existing matching `.platform`; otherwise generate a UUID v4.
- {{ACTIVITY_SETS}}: the activities and their `dependsOn` chains derived from requirements. One per pipeline.

## General Instructions
- Target Microsoft Fabric — the generated JSON must be valid and importable via Fabric Git integration.
- For referenced items, for the workspaceId and the artifactId:
  - in the same workspace: use `"00000000-0000-0000-0000-000000000000"` and the item's logicalId from its `.platform` file.
  - in a different workspace: use variable library references.
- Item logicalIds => `.platform` files in `REPO-FABRIC-DEPLOYMENT`
- Connection GUIDs => `2-config/technical-setup/`.

## Workflow Instructions
0. Use #tool:todo to create a todo with the following steps. Each step must be a single todo item.
1. **Review / gather inputs**
  - Use #tool:vscode/askQuestions to collect the pipeline objective, requirements, referenced items, or design document (`${input:PIPELINE_INFORMATION}`), and any Fabric workspace or database project to analyze (`${input:SOLUTION}`). 
  - If a solution folder is provided, inspect its `.platform` files and pipeline artifacts to infer pipeline design and referenced items (with same-workspace vs different-workspace for each). 
  - Read the:
    - {{PIPELINE_NAME}}: infer by reading rules in [pipeline convention](../../2-config/conventions/03-fabric-items/pipeline-convention.md) 
    - {{TARGET_FOLDER}}: infer by reading rules in [DPG workspace convention](../../2-config/conventions/02-fabric-workspace/5-workspace-dpg-convention.md) to resolve .
2. **Design the pipeline** (only if not provided) 
  - 2.1. Map requirements to an activity flow: choose activity types, ordering, `dependsOn` chains, parameters, variables, and referenced items
  - 2.2 Analyze your design to refactor it into a modular set of pipelines
  - 2.3 Write the pipeline design in a temporary file
3. **Write the JSON** - start with leaf pipelines - repeat for each pipeline
  - Generate `.platform` (set `displayName` = {{PIPELINE_NAME}}, `logicalId` = {{LOGICAL_ID}})
  - Assemble `pipeline-content.json` from the design using the pattern snippets. 
  - For the overall structure, use:
    - [example pipeline](./example/PL_EXAMPLE_PROCESS_DATA_PRODUCT.DataPipeline/pipeline-content.json) 
    - [template pipeline](./template/{{PIPELINE_NAME}}.DataPipeline/pipeline-content.json)
  - For each activity, read the matching pattern file in [pattern folder](./pattern/)
4. **Review the JSON**
  - Every `dependsOn` references an existing activity
  - Every `@pipeline().libraryVariables.<VAR>` has a matching entry in `libraryVariables`
  - No same-workspace reference uses a Variable Library needlessly
  - The folder is named `{{PIPELINE_NAME}}.DataPipeline`.
  - Validate JSON is parseable

## Output
As many times as there are pipelines in the design, generate a folder with the following files:
- {{TARGET_FOLDER}}/{{PIPELINE_NAME}}.DataPipeline/.platform
- {{TARGET_FOLDER}}/{{PIPELINE_NAME}}.DataPipeline/pipeline-content.json

## References
<!-- Manifest for human reading. Links to references must be hardcoded in Workflow Instructions where they are needed. -->
- [convention: pipeline convention](../../2-config/conventions/03-fabric-items/pipeline-convention.md)
- [convention: DPG workspace convention](../../2-config/conventions/02-fabric-workspace/5-workspace-dpg-convention.md#2-folder-organization)
- [template: pipeline artifacts](./template/{{PIPELINE_NAME}}.DataPipeline/)
- [example: pipeline artifacts](./example/PL_EXAMPLE_PROCESS_DATA_PRODUCT.DataPipeline/)
- [pattern: work with warehouse](./pattern/work-with-warehouse.md) — same/different workspace variants
- [pattern: stored procedure activity](./pattern/activity-stored-proc.md) — same/different workspace variants
- [pattern: lookup activity](./pattern/activity-lookup.md) — WH/LH, same/different workspace variants
- [pattern: copy data activity](./pattern/activity-copy-data.md)
- [pattern: send email (Outlook) activity](./pattern/activity-email-outlook.md)
- [pattern: execute pipeline activity](./pattern/activity-execute-pipeline.md)
- [pattern: ForEach activity](./pattern/activity-foreach.md)
- [pattern: add variable library](./pattern/add-variable-library.md) — declare `libraryVariables` for cross-workspace references
