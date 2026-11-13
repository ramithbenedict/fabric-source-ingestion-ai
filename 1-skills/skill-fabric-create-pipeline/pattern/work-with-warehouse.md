## Connection Rules (Warehouse)

These rules apply whenever any activity connects to a Fabric Warehouse.

### Generic rules

- `endpoint`: resolved from the Variable Library.
- `externalReferences.connection`: hardcoded connection GUID — read from [technical setup](../../../2-config/technical-setup/fabric-connections-setup.md) or #tool:vscode/askQuestions if not found.
- `connectionSettings.name` / `linkedService.name`: AI must auto-generate a random UUID v4 formatted as **lowercase with underscores replacing hyphens** (e.g. `a1b2c3d4_e5f6_7890_abcd_ef1234567890`). Do **not** use a semantic name. Never leave as a placeholder.

### The warehouse is in the same workspace as the pipeline:
- `artifactId`: the warehouse **logicalId** hardcoded. Can be found in the warehouse's `.platform` file in `REPO-FABRIC-DEPLOYMENT`.
- `workspaceId`: `"00000000-0000-0000-0000-000000000000"`.

### The warehouse is in a different workspace than the pipeline:
- `artifactId`: resolved via Variable Library (physical item ID).
- `workspaceId`: resolved from the Variable Library.
