## Example 13 — Stored Procedure NULL Parameter Handling

### Context

A pipeline parameter with no value set (empty field in the GUI) sends `NULL` to the stored procedure, **not** "nothing/undefined". This means a T-SQL parameter default (`@Param = <default>`) is **only** applied when the caller omits the argument entirely — it is **never** applied when the caller explicitly passes `NULL`. Because Fabric pipelines pass `NULL` for empty dynamic expression, such as empty pipeline parameters, the SP must handle `NULL` explicitly and decide what it means:

### Instructions
Be explicit on how `NULL` is handled; from one SP to another, `NULL` can mean different things. Never rely on the T-SQL default clause to protect against an explicit `NULL`.
- **Required parameter**: `NULL` is invalid. Validate at the top of the SP and raise an error so the run fails fast with a clear message.
- **Optional parameter**: 
    - An explicit `NULL` means "use the default". Re-apply the intended default value inside the body with `COALESCE` / `ISNULL`.
    - Keep the signature default and `COALESCE` fallback in sync so both call paths resolve to the same value.
    - When `NULL` is a *legitimate* business value for an optional parameter, do not coalesce it away — instead document that `NULL` is accepted and handle it explicitly in the body. Be deliberate about what `NULL` means per parameter.


### Output

```sql
CREATE PROCEDURE [PRC].[SP_PRC_EXAMPLE_LOAD]
    -- Required: caller MUST supply a value; NULL is not acceptable.
      @ExecutionId        VARCHAR(30)
    , @ExecutionDate      VARCHAR(10)
    -- Optional: NULL (or omission) reverts to the documented default.
    , @LoadMode           VARCHAR(20) = 'INCREMENTAL'
    , @BatchSize          BIGINT      = 10000
AS
BEGIN
    SET NOCOUNT ON
    ;

    -----------------------------------------------------------------------
    -- Required parameters: reject explicit NULL by raising an error.
    -----------------------------------------------------------------------
    IF @ExecutionId IS NULL
    BEGIN
        THROW 50001, 'SP_PRC_EXAMPLE_LOAD: @ExecutionId is required and cannot be NULL.', 1;
    END
    ;

    IF @ExecutionDate IS NULL
    BEGIN
        THROW 50001, 'SP_PRC_EXAMPLE_LOAD: @ExecutionDate is required and cannot be NULL.', 1;
    END
    ;

    -----------------------------------------------------------------------
    -- Optional parameters: an explicit NULL reverts to the default value.
    -- The default in the signature only covers the "argument omitted" case;
    -- re-apply the default here to also cover the "NULL passed by caller" case.
    -----------------------------------------------------------------------
    SET @LoadMode  = COALESCE(@LoadMode, 'INCREMENTAL');
    SET @BatchSize = COALESCE(@BatchSize, 10000);

    -- Procedure body uses the validated / defaulted parameters below.
    -- ...

END
;
```
