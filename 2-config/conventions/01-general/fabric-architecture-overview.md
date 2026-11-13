---
description: Architecture overview for the Fabric data platform, including bronze, silver, and gold layers definitions, source datasets, data products, and data product group definitions, workspace strategy, and warehouse high-level architecture.
status: active
origin: master
---

## Architecture-Driven Naming

The architecture has two main parts:
- source datasets
- data products

These two parts are layered as follows:
- Bronze: source datasets in their raw format
- Silver: curated data products
- Gold: consumption-ready data products

Diagram
```text
+---------------------------+
|      Source Systems       |
+---------------------------+
              |
              |
              v
+---------------------------+
|   Bronze Layer            |
|   (Source Datasets)       |
|   [ Lakehouse ]           |
+---------------------------+
              |
              |
              v
+---------------------------+
|   Silver Layer            |
|   (Curated Data Products) |
|   [ Warehouse + DB Proj (or Lakehouse) ] |
+---------------------------+
              |
              |
              v
+---------------------------+
|   Gold Layer              |
|   (Consumption-Ready DPs) |
|   [ Warehouse + DB Proj (or Lakehouse) ] |
+---------------------------+
              |
              |
              v
+-----------------------------------------------+
|              Consumption Layer                |
|  [ Power BI Service | Client Tools | Other ]  |
+-----------------------------------------------+
```

## Architecture Principles

### Key Principles

- One lakehouse per source dataset. A source dataset can contain all objects of a given source application or a subset of it.
- If a source application covers multiple domains, its data will be stored in different workspaces within different lakehouses (as each domain has its own workspace).
- A data product contains curated data and corresponds to silver and gold layers.

- Each individual data product can be implemented with a Warehouse (default) or a Lakehouse (PB-scale, Data science workloads), depending on the technical need.

Data product families used in the architecture:
- **Curated Data Product (`CDP`) for the silver** layer. It is the foundational and pivotal building block in the architecture.
- **Consumption Ready Data Product (`CRDP`) for the gold** layer. It is the data product that is directly consumed by clients. It can be generic (used by multiple use cases) or use-case-specific.

Additional clarifications:
- CDP has two internal variants: Base CDP and Composed CDP. These are only for internal use.
- CRDP has two internal variants: generic and use-case-specific
- These variants are architectural distinctions only and are not marked in the item names. The item name convention is the same for all data products, regardless of the layer or variant.

### Workspace strategy

#### Rules
- one workspace per domain for bronze ingestion
- one workspace per group of data product for silver/gold
- For confidential source dataset or data product, a dedicated workspace must be created and used.

#### Data Product Group

**Definition**:  
A data product group is a family of data products that share the same source dataset(s) and are related to the same domain or business area. For example, EPV2BI is a data product group that includes all data products related to the EPV2 source dataset and used for BI purposes.

**Examples**:  
- Example 1:  EPV2BI
    - Curated Data Product
        - EPV2 DWH
    - Consumption-Ready Data Product
        - EPV2 Federated
        - EPV2 Progress Measurement
        - EPV2 Certified Progress
        - EPV2 Completion
- Example 2: ERPBI
    - Curated Data Product (silver)
        - ERPBI DWH
    - Consumption-Ready Data Product (gold)
        - ERPBI AP
        - ERPBI AR
        - ERPBI GL
        - ERPBI OTL
        - ERPBI PPM
        - ERPBI P2P
- Example 3: ServiceNow
    - Curated Data Product (silver)
        - ServiceNow DWH
    - Consumption-Ready Data Product (gold)
        - ServiceNow Datamart


**When it stops being a Data Product Group**:  

- When a Data Product moves from mono-source to multi-source, with the newly added sources occupying a non-marginal part, it could change the nature of the Data Product. In such a situation, it may be best to move it into its own Data Product Group, and therefore its own Workspace / Warehouse / Repository.  
__Probability to occur: low__
- When a Data Product gets very large and requires more resources (more refreshes, etc.) and its performance level must be different from the other Data Products in the group, it may be best to move it into its own Data Product Group, so to have a separate Workspace, enabling a separate capacity.
__Probability to occur: very low__


### Warehouse architecture
- One Warehouse per group of data products