---
name: column-naming-convention
description: Convention for column names in data products across the Fabric platform.
status: active
origin: master
---

# Column Naming Convention for Silver Data Products

This convention is for column names in data product.
This convention does not apply to source dataset column names, which should be kept as-is.

**Table of contents:**
- [Rules for understandable names](#rules-for-understandable-names)
- [Rules for contextualized and consistent names](#rules-for-contextualized-and-consistent-names)
- [Rules for consistent syntax](#rules-for-consistent-syntax)
- [Specific rules - dates](#specific-rules---dates)
- [Specific rules - keys](#specific-rules---keys)
- [Examples and errors to avoid](#examples-and-errors-to-avoid)

## Rules for understandable names
- Use descriptive naming that’s beginner-friendly
- Define names in collaboration with business users
- Avoid acronyms and abbreviations as much as possible. Acronyms that are widely used and understood by the business users can be kept, but they should be the exception rather than the norm. Refer to [allowed acronyms](../01-general/acronyms-convention.md) for the list of allowed and forbidden acronyms.

## Rules for contextualized and consistent names
- Maximize naming consistency across columns
    - Example 1: ORDER_DATE, AMOUNT => ORDER_DATE, ORDER_AMOUNT
    - Example 2: AMOUNT_TAX, DISCOUNT_AMOUNT, AMOUNT_TOTAL => ORDER_TAX_AMOUNT, ORDER_DISCOUNT_AMOUNT, ORDER_TOTAL_AMOUNT
- Do **not** systematically prefix every column with its entity/table name. Use the entity prefix selectively, only where it adds meaning or prevents ambiguity. Use the minimum name that remains unambiguous in its normal consumption context.
- Add the entity prefix when at least one of the following applies:
    - The column identifies or references an entity (technical or foreign key), e.g., `PROJECT_ID`, `PARENT_PROJECT_FK`.
    - Multiple entities coexist at the same grain in the same schema or output (e.g., a denormalized table or view combining `PROJECT` and `CUSTOMER`), e.g., `PROJECT_NAME`, `CUSTOMER_NAME`.
    - The column has multiple semantic roles that must be distinguished, e.g., `SALES_AMOUNT`, `ORDER_AMOUNT`, `COST_AMOUNT`.
    - Omitting the prefix creates genuine ambiguity.
- Otherwise, rely on the table as the naming namespace and keep the column name contextualized but without repeating the table name

## Rules for consistent syntax
- Use CONSTANT_CASE: keep names uppercase and use underscores as separators  
- Follow the `<object>_<attribute>_<variant>` pattern. The variant is put at the end so that columns related to the same object are grouped together when sorted alphabetically.  
  - Example 1: `CUSTOMER_NAME`, `CUSTOMER_ADDRESS`, `CUSTOMER_PHONE`
  - Example 2: `ORDER_DATE`, `ORDER_AMOUNT`, `ORDER_STATUS`
- The name must be obvious on its type; if not, suffix with a type indicator:
  - `CUSTOMER_NAME` => it's obvious that it's a string and a "name"
  - `PROVIDER` =>² is it a name, an id, a code => add a suffix to clarify: `PROVIDER_NAME`, `PROVIDER_ID`, `PROVIDER_CODE`
  - if `ORDER_STATUS` is a label (e.g., `pending`) it's fine.  If it's a code (e.g., `S01`), add a suffix to clarify: `ORDER_STATUS_CODE`
- The name must be precise and unvague:
  - e.g., `AMOUNT` is vague, it could be a TAX_AMOUNT, a DISCOUNT_AMOUNT, a TOTAL_AMOUNT, etc. => add a suffix to clarify: `TAX_AMOUNT`, `DISCOUNT_AMOUNT`, `TOTAL_AMOUNT`
- Prefer nouns forms over verbal form, unless it's less natural:
  - e.g., use `MANAGER_NAME` instead of `MANAGED_BY`. This allows to clarify the type of the column (it's a name, not an id or a code).
  - e.g., it's more natural to keep `OPENED_BY_USER_NAME`, than `OPENER_NAME` (even if it's a verbal form).
- Prefer past participle form for action columns (e.g., CREATED, UPDATED, DELETED)

## Specific rules - dates
- Datetime columns: A datetime column contains both date and time information. Use _TS suffix for datetime columns.
  - `CREATED_TS`
  - `UPDATED_TS`
- Date columns: A date column does not contain time information. Use _DATE suffix for date columns.
  - `CREATED_DATE`
  - `UPDATED_DATE`

## Specific rules - keys

| Type of column | Technical suffix | Role | Examples of technical name | Functional suffix | Examples of functional name |
|----------------|------------------|------|-----------------------------|--------------------|------------------------------|
| **Primary surrogate key column** | _ID | An attribute that uniquely identifies a record and does not exist in the source/application system; it is generated in the data warehouse. | SALES_ID | n.a. | SALES_ID |
| **Foreign surrogate key column** | _FK | An attribute used to refer to another record in another table (for example, to reference dimensions from a fact table). The foreign key is an artificial key that does not exist in the source/application system and is generated in the data warehouse. | SALES_FK; CLIENT_FK | n.a. | SALES_FK; CLIENT_FK |
| **Natural Key / Matching key** | _NK | The designated source identifier used for joins in the processing layer. Can be built from source system id or a business key. Can be a single source field or a concatenation of several source fields. Every source field contributing to the NK must also appear as a standalone column with its natural name (`_SK`, `_CODE`, `_NUMBER`, `_NAME`, etc.). The NK never replaces its component fields. | CUSTOMER_NK; PROVIDER_NK | n.a. | CUSTOMER_NK; PROVIDER_NK |
| **Source system identifier** | _SK | The identifier generated by the source system, stored as-is in the data platform. Kept as a separate column alongside the `_NK` column when used as its source. | CUSTOMER_SK; ORDER_SK | … source ID | Customer source ID |
| **Composite key** (deprecated) | _CK | Deprecated — use `_NK` instead. Was used for a single column built by concatenating multiple source fields to uniquely identify a record (e.g., `PURCHASE_CK` = PurchaseId + DatabaseId). This role is now covered by `_NK`, which applies to both single-field and multi-field matching keys. | PURCHASE_CK | n.a. | n.a. |


## Focus on the `_NK` column: a technical 'slot' for the matching source identifier 

### NK slot contract
The NK column is designed at a data platform level to hold the source identifier used for operations in the processing layer (joins, etc.). It is an ELT back-room field, not a business-facing column. The NK column is not exposed in gold or consumer-facing tables, and it is not used in Power BI models. 
- Joins between source objects in the processing layer use `_NK` columns only. Note: joins between silver and gold tables use `_ID` / `_FK` columns, not `_NK`.
- Every source field contributing to the `_NK` must also appear as a standalone column with its natural name (`_SK`, `_CODE`, `_NUMBER`, `_NAME`, etc.). The `_NK` never replaces its component fields.
- `_NK` columns are processing-layer plumbing: not exposed in gold or consumer-facing tables, and not used in Power BI models. Joins and distinct counts in gold use `_ID` / `_FK`.


### The _NK column refers to the entity it names

The _NK column refers to the entity it names. If the prefix matches the table's grain entity, it is the table's own natural key (`CUSTOMER_NK` in `CUSTOMER_DIM`); otherwise it references another entity (`SUPPLIER_NK` in `PRODUCT_DIM`).


### Migration from `_CK` to `_NK`

| Before | After |
|---|---|
| `PROVIDER_CK` (concat of product_code + customer_code + location_code) | `PROVIDER_NK` — same value, same construction |
| `CUSTOMER_NK` (single source field) | `CUSTOMER_NK` — unchanged |

Existing deployed tables keep `_CK` columns as-is. The new standard applies to new development only.

### Rationale

- One suffix per role, not per construction detail: whether an NK is built from one field or several is a construction property, not a naming category.
- Uniform join shape: every join/MERGE/key-retrieval has the same single-column shape regardless of key arity.
- Avoids collision with `CK_` check-constraint prefix and "candidate key" terminology.

## Examples and errors to avoid

### Overdoing the contextualization
- Source field: `teamsuseractivitycount_schema.Meetings_Attended_Count`
- ❌ Incorrect: `TEAMS_USER_MEETINGS_ATTENDED_COUNT` 
- ✅ Correct: `TEAM_MEETINGS_ATTENDED_COUNT`

### Systematic prefixing where the table already provides context
- Context: normalized `PROJECT` table
- ❌ Incorrect: `PROJECT_ID`, `PROJECT_NAME`, `PROJECT_DESCRIPTION`, `PROJECT_PLANNED_START_DATE`, `PROJECT_ACTUAL_START_DATE`
- ✅ Correct: `PROJECT_ID`, `NAME`, `DESCRIPTION`, `PLANNED_START_DATE`, `ACTUAL_START_DATE`
- Note: in a denormalized analytical view combining `PROJECT` with other entities (e.g., `CUSTOMER`), prefixing becomes appropriate: `PROJECT_ID`, `PROJECT_NAME`, `CUSTOMER_ID`, `CUSTOMER_NAME`

### Keeping acronyms in the field name
Example 1:
- Source field: `CUSTNM`
- ❌ Incorrect: `CUST_NM`
- ✅ Correct: `CUSTOMER_NAME`

Example 2:
- Source field: `MROWNER`
- ❌ Incorrect: `MR_OWNER`
- ✅ Correct: `MATERIAL_REQUEST_OWNER`

### Using prefixes instead of suffixes
- Source field: `trackingnumber`
- ❌ Prefix variant: `SMAT_TRACKING_NUMBER`
- ✅ Suffix variant: `TRACKING_NUMBER_SMAT`

### Not using the right suffix `_NK`
- Source field: `ProjectId`
- ❌ Incorrect: `PROJECT_ID`
- ✅ Correct: `PROJECT_NK`

### Not using the right suffix `_FK`
- Source field: Not relevant
- ❌ Incorrect: In `ORDERS_FACT`: `CURRENCY_ID`, `CURRENCY_NK`
- ✅ Correct: In `ORDERS_FACT`: `CURRENCY_FK`, `CURRENCY_NK`



### No consistency and no contextualization
- Source field: Source table `currency`: `CurrCode`, `Country`, `Description`
- ❌ Incorrect: In `CURRENCY_DIM`: `CURRENCY_CODE`, `CURRENCY_COUNTRY`, `DESCRIPTION`
- ✅ Correct: In `CURRENCY_DIM`: `CURRENCY_CODE`, `COUNTRY`, `DESCRIPTION`

### Not using suffixes, but prefixes
- Source field: `TRACKINGNUMBER`, `SMAT_TRACKINGNUMBER`
- ❌ Incorrect: `TRACKING_NUMBER`, `SMAT_TRACKING_NUMBER`
- ✅ Correct: `TRACKING_NUMBER`, `TRACKING_NUMBER_SMAT`

### Lack of consistency across columns
- Source field: `CreatedDateTime`, `LastModifiedAt`
- ❌ Incorrect: `CREATED_DATE`, `LAST_MODIFICATION_DT` (DATE: it is not a date, it's a datetime, and DT is not a suffix we use)
- ✅ Correct: `CREATED_TS`, `UPDATED_TS`

### Not business-friendly naming
- Source field: `OracleMRNumber`
- ❌ Incorrect: `MATERIAL_REQUISITION_ORACLE_NUMBER`
- ✅ Correct: `MATERIAL_REQUISITION_PEOPLECONNECT_NUMBER`