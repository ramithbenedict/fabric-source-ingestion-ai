# Fabric connections to create: RMA

Create each connection in Fabric (Settings => Manage connections and gateways => New), with the name and values below, then put its id in VL_MAIN.
Values come from the DPV1 linked service, which the export holds for one environment only: confirm UAT and PRD with the source owner.
Passwords are never in this repository: take them from the Key Vault secret DPV1 used.

## CONN_RMA_SQL_SERVER_DEV (UAT, PRD: same name with `_UAT`, `_PRD`)

| Setting | Value |
| --- | --- |
| Connection name | `CONN_RMA_SQL_SERVER_DEV` / `CONN_RMA_SQL_SERVER_UAT` / `CONN_RMA_SQL_SERVER_PRD` |
| Connection type | SQL Server database |
| Gateway | **on-premises data gateway required** (DPV1 used a self-hosted integration runtime) |
| Server | `dbRISKMGMTi1.tp.tpnet.intra` (DPV1 export) |
| Database | `RISK_MGMT_APP_TRN` (DPV1 export) |
| Authentication | Basic or Windows; DPV1 used `see linked service`, user `TP\frma` |
| Secret | Key Vault `AZ-SQLSERVER-RMA-generic-pwd` |
| Replaces (DPV1) | linked service `LS_CORE_SQLSERVER_RMA` (SqlServer) |
| VL_MAIN | `RMA_SQL_SERVER_CONN_ID` = connection id (DEV / UAT / PRD); `RMA_SQL_SERVER_CONN_NAME` = connection name |

## Lakehouse and warehouse connections (Fabric items)

| Connection | Type | Used by | VL_MAIN | Known value |
| --- | --- | --- | --- | --- |
| Lakehouse `LH_SDS_RMA` | Lakehouse (OAuth2 or workspace identity) | Copy sinks, the raw to table Copy | `RMA_LH_CONN_ID` | none: create one connection per environment and reuse it for every source |
| Warehouse `WH_CATALOG_COMMON` | Warehouse (OAuth2 or workspace identity) | catalog Lookup, watermark Script | `CATALOG_WAREHOUSE_CONN_ID` | create after the warehouse exists |

Both are required in the pipeline files: without the connection reference, Fabric's Git import fails with "Object reference not set".

## Item ids to fill in VL_MAIN after the first sync

- `LH_SDS_RMA_ID`: item id of `LH_SDS_RMA`
- `CATALOG_WAREHOUSE_ID` and `CATALOG_WAREHOUSE_SQL_ENDPOINT`: item id and SQL connection string of `WH_CATALOG_COMMON`
