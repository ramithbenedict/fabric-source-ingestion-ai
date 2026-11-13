---
description: Naming and organizational conventions for Lakehouse items in Fabric.
status: proposal
origin: master
---

# Lakehouse conventions

The purpose of this document is to define the conventions for using ♒ Lakehouse in T.EN Fabric data platform.

Summary:
01. [General](#1-general)
02. [Naming conventions for Lakehouse items](#2-naming-conventions-for-lakehouse-items)
03. [Shortcuts](#3-shortcuts)
04. [RAW file storage convention](#4-raw-file-storage-convention)
05. [Delta table metadata columns](#5-delta-table-metadata-columns)
06. [References to other conventions](#6-references-to-other-conventions)

## 1. General
- Lakehouse implementation must rely on Notebooks for creation, ingestion, transformation, and operational logic.
- Lakehouses must use a multi-schema design. Schemas must be used to separate sources or logical zones instead of placing all objects in the default schema.

## 2. Naming conventions for Lakehouse items:
- Prefix: `LH_`
- **General item naming convention:** refer to the [item naming convention](./item-general-convention.md) for the general naming rules to apply.
- **Lakehouse for a source dataset:** refer to the [Source Dataset Workspace Convention](../02-fabric-workspace/6-workspace-sds-convention.md) for the naming convention of source dataset Lakehouses.
- **Lakehouse for a data product:** refer to the [Data Product Workspace Convention](../02-fabric-workspace/5-workspace-dpg-convention.md#naming-for-warehouselakehouse-for-data-product) 
- **Lakehouse for input to a data product:** refer to the [Data Product Workspace Convention](../02-fabric-workspace/5-workspace-dpg-convention.md#naming-for-lakehouse-for-inputs-to-the-data-product)

## 3. Shortcuts
- Each source system must have a dedicated target schema for its shortcuts.
- The schema must follow the naming pattern `<SOURCE_NAME>_SHORTCUTS` to ensure consistency and discoverability.
- Shortcut configuration values must be parameterized through variables stored in variable libraries.
- Shortcut should be created using VS Code.
- All logic that creates or refreshes shortcuts must resolve connection and path values from variable libraries.

## 4. RAW file storage convention
- RAW files stored through Lakehouse shortcuts or ingestion processes must follow the canonical path pattern:
	`/{source_system}/{instance}/{entity}/{yyyy}/{mm}/{dd}/{HHhMM}/`
- Example:
	`/sap/plant_eu/sales_orders/2026/05/18/14h30/`
- Path segments must follow these rules:
	- `source_system`: canonical technical source name in lowercase
	- `instance`: source instance, plant, tenant, region, or equivalent discriminator in lowercase
	- `entity`: business entity or extracted object name in lowercase snake case
	- `yyyy/mm/dd`: ingestion or extraction date partition
	- `HHhMM`: ingestion or extraction time partition in 24-hour format
- Path name must only include **lowercase** letters, numbers, and underscores, and use `/` as separator. No spaces or special characters allowed.

## 5. Delta table metadata columns
- All Delta tables, excluding raw files, must contain the following mandatory metadata columns:
	- `meta_loaded_at`
	- `meta_source_file`
- `meta_loaded_at` must store the technical timestamp at which the record was loaded into the Delta table, in UTC+0 timezone.
- `meta_source_file` must store the originating file path (including the file name) used to load the record.

## 6. References to other conventions
- Variable names and variable library usage must follow [variable library conventions](./variable-library-convention.md).
- General item naming must follow [item convention](./item-general-convention.md).

## Decision rationale
- Lowercase vs Uppercase: the usage of lowercase is the de facto standard in data engineering (dbt, Spark, etc.). Moreover, lowercase letters are easier to read and are less error prone.
- Paths are case sensitive, hence the need to enforce the usage of the same case across all Lakehouse implementations to avoid confusion and potential errors.