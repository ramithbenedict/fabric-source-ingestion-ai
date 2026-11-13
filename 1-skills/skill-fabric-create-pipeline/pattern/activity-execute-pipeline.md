# Activity Pattern — Execute Pipeline

Invokes another Fabric Data Pipeline. Used by master/orchestrator pipelines to chain child pipelines sequentially or in parallel.

- `type`: `ExecutePipeline`
- `typeProperties.pipeline.referenceName`: the target pipeline's **logicalId / artifactId GUID**.
- `waitOnCompletion`: `true` to block until the child pipeline finishes.

## Variant — Sequential orchestration

source: ✅ microsoft_doc | ✅ ten_curated

```json
{
  "name": "DEPLOY_META",
  "type": "ExecutePipeline",
  "dependsOn": [],
  "policy": { "secureInput": false },
  "typeProperties": {
    "pipeline": {
      "referenceName": "<CHILD_PIPELINE_GUID>",
      "type": "PipelineReference"
    },
    "parameters": {},
    "waitOnCompletion": true
  }
}
```

Chain the next child by adding a `dependsOn` entry pointing at the previous `ExecutePipeline` activity:

```json
{
  "name": "PROCESS_DATA_PRODUCT",
  "type": "ExecutePipeline",
  "dependsOn": [
    { "activity": "DEPLOY_META", "dependencyConditions": [ "Succeeded" ] }
  ],
  "policy": { "secureInput": false },
  "typeProperties": {
    "pipeline": { "referenceName": "<CHILD_PIPELINE_GUID>", "type": "PipelineReference" },
    "parameters": {},
    "waitOnCompletion": true
  }
}
```

Notes:
- To pass runtime values, populate `parameters` with `{ "<PARAM>": { "value": "@pipeline().parameters.<PARAM>", "type": "Expression" } }`.
- For a child pipeline in a different workspace, reference it via a Variable Library variable holding its artifact ID.
