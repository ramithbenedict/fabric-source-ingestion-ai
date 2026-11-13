---
name: skill-fabric-create-shortcut
description: Generate shortcut metadata only, using an existing lakehouse folder.
---

## Skill Purpose

This skill generates `shortcuts.metadata.json` for a Fabric Lakehouse given a list of tables, shortcut type, and variable references.

## Skill Capabilities

### In scope
- Validate that all required inputs are present (ask for missing values if needed).
- Generate `shortcuts.metadata.json` for `AdlsGen2` or `OneLake` shortcut types.
- Sanitize shortcut names per Fabric naming rules.
- Apply transformation rules to shortcut names when provided.
- Use Variable Library token syntax for environment-specific values.

### Out of Scope
- Does not resolve which tables to include (caller provides the table list).
- Does not discover ADLS folders or run discovery scripts.
- Does not create or modify Variable Libraries.
- Does not generate `.platform` or `lakehouse.metadata.json`.
- Does not create notebooks or pipelines.
- Does not determine output file locations (caller provides output path).
- Does not use MCP or API to deploy artifacts.
- Does not execute Git commands.

## Skill Instructions
All instructions are in separate files and must be read:
- Use #tool:read/readFile on [instructions](./instructions.md) for step-by-step execution instructions.
- Use #tool:read/readFile on [examples](./examples/_index.md) for worked examples.

## Skill Output Contract
- The skill generates `shortcuts.metadata.json` containing shortcut definitions for the provided tables.
- Refer to [examples](./examples/_index.md) for worked examples.