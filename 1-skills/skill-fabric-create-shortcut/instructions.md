---
title: Fabric Create Shortcut - Instructions
description: Generate shortcuts.metadata.json given a table list, shortcut type, and variable references.
---

## Inputs Required

All inputs must be provided by the caller (stage or user) before invoking this skill. The skill validates inputs and asks for missing values only when necessary.

### Common (all shortcut types)
- `${input:shortcut_type}`: `AdlsGen2` | `OneLake`
- `${input:vl_name}`: Variable Library name used for token syntax (e.g. `VL_MAIN`)
- `${input:tables}`: list of tables to create shortcuts for (each entry has a `folder_name` and optionally a `shortcut_name` override)
- `${input:schema_name}`: target schema name (default: `dbo`)
- `${input:output_path}`: absolute path where `shortcuts.metadata.json` should be written
- `${input:name_transformation_rules}`: string | null - naming rules to apply to shortcut names

### For AdlsGen2 shortcuts
- `${input:ADLS_FABRIC_CONNECTION_VARIABLE_NAME}`: VL variable name for `connectionId`
- `${input:ADLS_DFS_ENDPOINT_VARIABLE_NAME}`: VL variable name for `location`
- `${input:ADLS_CONTAINER}`: ADLS container name (used in `subpath`)
- `${input:ADLS_BASE_PATH}`: ADLS base path before the table folder (used in `subpath`)

### For OneLake shortcuts
- `${input:ONELAKE_ITEM_ID_VARIABLE_NAME}`: VL variable name for `itemId`, which is the Lakeouse item ID.
- `${input:ONELAKE_WORKSPACE_ID_VARIABLE_NAME}`: VL variable name for the `workspaceId` the Lakehouse resides in.

## Key instructions

- Never hardcode GUIDs, ADLS endpoints, connection IDs, container names, or storage paths.
- Do not use these schemas: `public`, `sys`, `INFORMATION_SCHEMA`, `queryinsights`.
- Preserve the original folder name exactly in the final `subpath` or `path` segment (case-sensitive).
- Sanitize shortcut `name` by lowercasing and replacing forbidden characters with `_`.
- Ensure shortcut names are unique within a schema.
- Never create or modify `.platform` or `lakehouse.metadata.json`.
- Read `known-issues.md` before generating.
- Read the matching example from `examples/` for the selected shortcut type.

## Workflow

### Step 0 - Plan
- Use #tool:todo to adapt the todo and incorporate the following steps:
  1. Shortcuts - Validate inputs
  2. Shortcuts - Generate `shortcuts.metadata.json`
  3. Write output to `${input:output_path}` and any additional paths provided by the caller.

### Step 1 - Validate Inputs

- Check that all required inputs for the selected `shortcut_type` are present.
- If any required input is missing, ask the user for the missing value(s) one at a time, always ending with `Z) Other (user input)`.
- Read `known-issues.md`.
- Read [examples](./examples/_index.md) for the matching shortcut type.
- Done condition: all required inputs are present and validated.

### Step 2 - Generate `shortcuts.metadata.json`

- **Refer to the [examples](./examples/_index.md) for the selected `shortcut_type` to determine the correct template pattern.**
- Use the exact template pattern from the shortcut examples matching `shortcut_type`.
- Write one entry per table in `${input:tables}`.
- Determine the shortcut `name`:
  - If `shortcut_name` override is provided for the table entry, use it.
  - Otherwise, derive from `folder_name` by lowercasing and replacing forbidden Fabric characters (`"`, `\`, `/`, `:`, `|`, `<`, `>`, `*`, `?`, `.`, `%`, `+`) with `_`.
  - Apply `${input:name_transformation_rules}` if provided.
- Set `path` to `/Tables/${input:schema_name}`.
- Validate that shortcut names within a schema are unique.
- Done condition: `shortcuts.metadata.json` content is ready.

### Step 3 - Write Output

- Write `shortcuts.metadata.json` to `${input:output_path}`.
- If additional output paths are provided by the caller, write copies there as well.
- Done condition: file(s) written.

## Completion Checklist

- [ ] All required inputs validated
- [ ] `shortcuts.metadata.json` generated with correct template
- [ ] Shortcut names sanitized and unique within schema
- [ ] Variable Library tokens used (no hardcoded GUIDs, endpoints, or paths)
- [ ] Subpath leaf segments match original folder names exactly (case-sensitive)
- [ ] Output file(s) written