---
description: Folder convention for database projects used in Fabric.
status: proposal
origin: master
---

# Database Project — Folder Convention

**Table of content**
- [Scope](#scope)
- [Project naming](#project-naming)
- [Root structure](#root-structure)
- [Sub-folder structure](#sub-folder-structure)
- [Object type segregation](#object-type-segregation)
- [Schema naming](#schema-naming)
- [Key Rules](#key-rules)

## Scope

A single database project contains assets for a **group of data products** (silver and/or gold). All database projects live in the `REPO-FABRIC-DEPLOYMENT` repository under `database-projects/`.

## Project naming

Project canonical name: `DPG-<DATA_PRODUCT_GROUP>`

Examples:
- `DPG-GAIA` — GAIA group of data products.
- `DPG-EPV2BI` — EPV2BI group of data products.


## Root structure

Data product group folders is located in REPO-FABRIC-DEPLOYMENT repository, under:  
`database-projects/DPG-<DATA_PRODUCT_GROUP-NAME>/`


Silver data products are assigned lower numbers than gold data products.

```
📂 DPG-<DATA-PRODUCT-GROUP-NAME>/
├── DPG-<DATA-PRODUCT-GROUP-NAME>.sqlproj
├── NuGet.config
├── 📂 00-global/
|    ├── 📂 schemas/
|    └── 📂 _utils/
├── 📂 01-silver-<data-product-name>/
|    ├── 📂 1-input/
|    ├── 📂 2-intermediate/
|    ├── 📂 3-processing/
|    ├── 📂 4-output/
|    └── 📂 5-access-rules/
├── 📂 02-silver-<data-product-name>/
├── 📂 03-gold-<data-product-name>/
|    ├── 📂 1-input/                 # optional
|    ├── 📂 2-intermediate/          # optional
|    ├── 📂 3-processing/            # optional
|    ├── 📂 4-output/
|    └── 📂 5-access-rules/          # optional
├── 📂 04-gold-<data-product-name>/
├── 📂 05-gold-<data-product-name>/
└── ...
```

## Sub-folder structure

### 00-global/
- **`schemas/`** — DDL statements for schema creation.
- **`_utils/`** — Utility objects (helper stored procedures, shared functions, reusable views) referenced across multiple data products.

### Silver data product folder structure

#### `1-input/`
Proxy layer for external references.
- Contains **views** pointing to external tables sourced from another lakehouse or warehouse.
- Purpose: decouple the codebase from external source locations. All downstream references point to these proxy views, never directly to external objects.

#### `2-intermediate/`
Precomputed reusable objects.
- **views**, **stored procedures**, or **tables**
- Contains objects consumed by multiple subsequent steps.
- **May be empty** if no intermediate computation is needed.

#### `3-processing/`
Transformation and loading logic.
- **views** compute the transformation — each view is an image of the target structure.
- **stored procedures** handle the loading step (insert, merge, etc.).
- **tables** for transient-tables used during processing (e.g., staging/payload tables)

#### `4-output/`
Published objects of the data product.
- Contains **tables** when the object is materialized.
- Contains **views** when the object is not materialized.

#### `5-access-rules/`
SQL-based security layer.
- Contains objects used to enforce access control via the SQL endpoint: **views**, **row-level security policies**, **column-level security policies**, **dynamic data masking**, **grants**, etc.

### Gold data product folder structure
Gold data products reference the output layer of silver data products. By default they do **not** have a `1-input/` or `3-processing/` folder. A `1-input/` folder may be added when the gold product consumes an external data source. A `3-processing/` folder may be added when the gold product requires its own transformation logic.

## Object type segregation

Within each numbered subfolder, files are **organized by object type** in dedicated sub-directories.

```
📂 3-processing/
├── 📂 views/
├── 📂 stored-procedures/
└── 📂 _utils/
```

## Schema naming

Each data product uses dedicated schemas to isolate its objects. Schema names follow this pattern:

| Layer | Schema pattern | Examples |
|---|---|---|
| Input | `INP_<SOURCE_NAME>` | `INP_MDM_EBX` |
| Intermediate | `INT_SILV_{{DATA_PRODUCT_NAME}}` / `INT_GOLD_{{DATA_PRODUCT_NAME}}` | `INT_SILV_MDM_DATA_QUALITY` |
| Processing | `PRC_SILV_{{DATA_PRODUCT_NAME}}` / `PRC_GOLD_{{DATA_PRODUCT_NAME}}` | `PRC_GOLD_MDM_DATA_QUALITY` |
| Output | `OUT_SILV_{{DATA_PRODUCT_NAME}}` / `OUT_GOLD_{{DATA_PRODUCT_NAME}}` | `OUT_SILV_EPV2BI`, `OUT_GOLD_FEDERATED` |

## Key Rules
- Object names use UPPER_SNAKE_CASE
- By default, one .sql file per view, stored procedure, or table. 
    - Exception: input layer => one file per source system containing all views for that source.
    - Exception: data product schemas are all defined in a single `schemas.sql` file.
### Specific to gold:
- Views reference silver output objects directly (same DB project): `[OUT_SILV_<SILVER_DATA_PRODUCT_NAME>].[<OBJECT_NAME>]`.
- If pre-computed objects are reused across multiple output views or tables, add them in the  intermediate layer.
- If materialisation logic is required, add stored procedures in `3-processing/stored-procedures/`.
- Access rules are optional as most often a gold data product is made of views, hence inheriting the access rules of the silver data products it references.