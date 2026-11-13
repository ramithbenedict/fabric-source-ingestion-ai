# Activity Pattern — Send Email (Office 365 Outlook)

Sends an email, typically for success/failure notifications. Requires an Office 365 Outlook connection configured after import.

- `type`: `Office365Outlook`
- The connection is referenced via `externalReferences.connection` (a GUID; leave as the zero-GUID placeholder and let the user bind it).
- Use `dependsOn` with `dependencyConditions: ["Failed"]` for failure alerts or `["Succeeded"]` for success notifications.

## Variant — Failure notification

source: ✅ microsoft_doc | ◼️ ten_curated

```json
{
  "name": "Notify_on_failure",
  "type": "Office365Outlook",
  "dependsOn": [
    {
      "activity": "<UPSTREAM_ACTIVITY>",
      "dependencyConditions": [ "Failed" ]
    }
  ],
  "policy": {
    "timeout": "0.02:00:00",
    "retry": 0,
    "retryIntervalInSeconds": 30,
    "secureInput": false,
    "secureOutput": false
  },
  "typeProperties": {
    "inputs": {
      "method": "post",
      "path": "/v2/Mail",
      "body": {
        "To": "<RECIPIENTS>",
        "Subject": {
          "value": "@concat('Pipeline failed: ', pipeline().Pipeline)",
          "type": "Expression"
        },
        "Body": "<p>The pipeline failed. Check the run details in Fabric.</p>",
        "Importance": "High"
      }
    }
  },
  "externalReferences": {
    "connection": "00000000-0000-0000-0000-000000000000"
  }
}
```

Notes:
- `To` accepts a semicolon-separated list of addresses.
- `Body` supports HTML and pipeline expressions (wrap dynamic content with `@concat(...)` and `"type": "Expression"`).
