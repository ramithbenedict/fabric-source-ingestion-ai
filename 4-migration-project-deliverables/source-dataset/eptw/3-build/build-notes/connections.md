# Fabric connections to create: EPTW

Create each connection in Fabric (Settings => Manage connections and gateways => New), with the name and values below, then put its id in VL_MAIN.
Values come from the DPV1 linked service, which the export holds for one environment only: confirm UAT and PRD with the source owner.
Passwords are never in this repository: take them from the Key Vault secret DPV1 used.

## CONN_EPTW_REST_SERVICE_DEV (UAT, PRD: same name with `_UAT`, `_PRD`)

| Setting | Value |
| --- | --- |
| Connection name | `CONN_EPTW_REST_SERVICE_DEV` / `CONN_EPTW_REST_SERVICE_UAT` / `CONN_EPTW_REST_SERVICE_PRD` |
| Connection type | Web v2 (REST) |
| Gateway | **on-premises data gateway required** (DPV1 used a self-hosted integration runtime) |
| Url | `https://apis-uat.lab.technipenergies.com/Construction/ePTW` (DPV1 export) |
| Authentication | as DPV1 (Basic, OAuth2 or anonymous); DPV1 used `Anonymous` |
| Secret | none in DPV1 |
| Replaces (DPV1) | linked service `LS_CORE_REST_EPTW` (RestService) |
| VL_MAIN | `EPTW_REST_SERVICE_CONN_ID` = connection id (DEV / UAT / PRD); `EPTW_REST_SERVICE_CONN_NAME` = connection name |

## Key Vault connection (API key header of LS_CORE_REST_EPTW)

A Fabric REST connection cannot carry a header. The pipeline reads the secret with a Web activity and sends it as an additional header in every REST Copy.

| Setting | Value |
| --- | --- |
| Connection type | Web v2 (Web) to the Key Vault, authentication Organizational account or Service principal (token audience `https://vault.azure.net`) |
| Url | `https://az-kv-ne07we-synapseprd.vault.azure.net/` / `https://az-kv-ne08we-synapse-dev.vault.azure.net/` / `https://az-kv-ne08we-synapseuat.vault.azure.net/` (DPV1 pipeline, per environment: DEV / UAT / PRD) |
| Secret(s) | `AZ-REST-EPTW-APIM-SUBKEY` (header `ocp-apim-subscription-key`), read as `secrets/<name>?api-version=7.0` |
| Access | the identity of the connection needs `get` on the secrets of the vault |
| VL_MAIN | `EPTW_KEYVAULT_CONN_ID` = connection id (DEV / UAT / PRD) |

## Lakehouse and warehouse connections (Fabric items)

| Connection | Type | Used by | VL_MAIN | Known value |
| --- | --- | --- | --- | --- |
| Lakehouse `LH_SDS_EPTW` | Lakehouse (OAuth2 or workspace identity) | Copy sinks, the raw to table Copy | `EPTW_LH_CONN_ID` | none: create one connection per environment and reuse it for every source |
| Warehouse `WH_CATALOG_COMMON` | Warehouse (OAuth2 or workspace identity) | catalog Lookup, watermark Script | `CATALOG_WAREHOUSE_CONN_ID` | create after the warehouse exists |

Both are required in the pipeline files: without the connection reference, Fabric's Git import fails with "Object reference not set".

## Item ids to fill in VL_MAIN after the first sync

- `LH_SDS_EPTW_ID`: item id of `LH_SDS_EPTW`
- `CATALOG_WAREHOUSE_ID` and `CATALOG_WAREHOUSE_SQL_ENDPOINT`: item id and SQL connection string of `WH_CATALOG_COMMON`
