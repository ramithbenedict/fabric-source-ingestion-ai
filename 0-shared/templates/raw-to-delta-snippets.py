# Reusable code of NB_<SRC>_RAW_TO_DELTA, maintained once here and copied by 0-shared/scripts/ingestion.py.
# Each "# --- snippet: <name>" block is one function, taken from a DPV1 notebook (named in its first comment line).
# The generator copies only the snippets a source needs. Change a snippet here, then regenerate S3 for the sources.
# Names available at run time: spark, notebookutils, F, Window, DeltaTable, json, time, fnmatch, LH_ROOT and the notebook parameters.
# LH_ROOT = abfss root of the source lakehouse, found by its name: no default lakehouse has to be attached to the notebook.

# --- snippet: folders
def has_files(path):
    """True when the folder exists and holds at least one file."""
    try:
        return any(not e.isDir for e in notebookutils.fs.ls(path))
    except Exception:
        return False


def latest_run(base):
    """Newest <yyyy>/<mm>/<dd>/<HHhMM> folder under base: used when the notebook runs on its own."""
    path = base
    for _ in range(4):
        try:
            subs = sorted(e.name.rstrip("/") for e in notebookutils.fs.ls(path) if e.isDir and e.name[:1].isdigit())
        except Exception:
            return None
        if not subs:
            return None
        path = f"{path}/{subs[-1]}"
    return path[len(base) + 1:]


def folder_size(path, depth=3):
    """Bytes under path, used only to start the largest tables first (0 when the folder is missing)."""
    try:
        return sum(e.size if not e.isDir else (folder_size(e.path, depth - 1) if depth else 0) for e in notebookutils.fs.ls(path))
    except Exception:
        return 0


def read_parquet(path):
    """The parquet of a folder, with the file each row came from; (None, path) when there is nothing to read."""
    if not path or not has_files(path):
        return None, path
    return spark.read.parquet(path).withColumn("meta_source_file", F.col("_metadata.file_path")), path


# --- snippet: read_raw_flat
def table_path(row):
    """Raw parquet of the table: Files/raw/<src>/<table>/ (one folder, overwritten at each run).
    DPV1 NTBK_<SRC>_CHILD_FULL_RAW_TO_CLEAN: spark.read.parquet(RAW/DATASOURCE=<SRC>/<SCHEMA>.<TABLE>/)."""
    return f"{LH_ROOT}/Files/{raw_root}/{row['EntityName']}{row.get('FolderTail') or ''}"


def read_table(row):
    return read_parquet(table_path(row))


# --- snippet: read_raw_dated
def table_path(row):
    """Raw parquet of this run: Files/raw/<src>/<table>/<yyyy>/<mm>/<dd>/<HHhMM>[/HISTORY|/DELETE_LOGS], as DPV1 kept it."""
    base = f"{LH_ROOT}/Files/{raw_root}/{row['EntityName']}"
    run = run_partition or latest_run(base)
    return f"{base}/{run}{row.get('FolderTail') or ''}" if run else None


def read_table(row):
    return read_parquet(table_path(row))


# --- snippet: flatten
def flatten(df):
    """a.b.c => a_b_c, recursively. DPV1 NTBK_SERVICENOW_CHILD_JSON_TO_CLEANSED: flatten_json_df."""
    def columns(schema, prefix=""):
        out = []
        for f in schema.fields:
            path = f"{prefix}.`{f.name}`" if prefix else f"`{f.name}`"
            if f.dataType.typeName() == "struct":
                out += columns(f.dataType, path)
            else:
                out.append(F.col(path).alias(path.replace("`", "").replace(".", "_")))
        return out
    return df.select(*columns(df.schema))


# --- snippet: flatten_to_raw
def landing_files(row):
    """(run folder in landing, [(file name, bytes)]) of this table: REST <table>.json, files the SourcePath wildcard."""
    land = f"{LH_ROOT}/Files/{landing_root}/{run_partition or latest_run(f'{LH_ROOT}/Files/{landing_root}')}"
    pattern = (f"{row['EntityName']}.json" if IS_REST else (row.get("SourcePath") or "*")).lower()
    if not has_files(land):
        return land, []
    return land, [(e.name, e.size) for e in notebookutils.fs.ls(land) if not e.isDir and fnmatch.fnmatch(e.name.lower(), pattern)]


def flatten_to_raw(row):
    """NB_<SRC>_FLATTEN: the files of this table in Files/landing/<src>/<run>/ (REST: <table>.json; files: the SourcePath wildcard)
    => record array exploded => nested fields flattened => parquet in Files/raw/<src>/<run>/<table>/. Returns the raw folder, or None.
    DPV1 NTBK_<SRC>_CHILD_JSON_TO_CLEANSED (first half: read LANDING, explode, flatten_json_df) and NTBK_*_EXCEL_TO_PARQUET."""
    land, files = landing_files(row)
    if not files:
        return None
    files = [n for n, _ in files]
    fmt = (row.get("SourceFormat") or SOURCE_FORMAT).lower()
    options = dict(READ_OPTIONS.get(fmt, {}), **json.loads(row.get("FileOptions") or "{}"))
    if fmt == "excel":  # Spark has no Excel reader: pandas, as DPV1 NTBK_*_EXCEL_TO_PARQUET
        import pandas as pd
        local = notebookutils.fs.getMountPath("/lh_src")   # mounted in the setup cell: pandas reads the lakehouse as a local folder
        frames = [pd.read_excel(f"{local}/{land[len(LH_ROOT) + 1:]}/{n}", dtype=str, **options) for n in files]
        df = spark.createDataFrame(pd.concat(frames, ignore_index=True))
    else:
        df = spark.read.options(**options).format(fmt).load([f"{land}/{n}" for n in files])
    root = row.get("RootPath") or JSON_ROOT
    if root and root in df.columns:
        df = df.select(F.explode_outer(F.col(root)).alias("_r")).select("_r.*")
    raw = land.replace(f"{LH_ROOT}/Files/{landing_root}", f"{LH_ROOT}/Files/{raw_root}", 1) + f"/{row['EntityName']}"
    flatten(df).write.mode("overwrite").parquet(raw)
    return raw


# --- snippet: read_raw_run
def table_path(row):
    """Parquet the FLATTEN notebook wrote for this run: Files/raw/<src>/<run>/<table>/."""
    base = f"{LH_ROOT}/Files/{raw_root}"
    run = run_partition or latest_run(base)
    return f"{base}/{run}/{row['EntityName']}" if run else None


def read_table(row):
    return read_parquet(table_path(row))


# --- snippet: clamp_1900
def clamp_dates_1900(df):
    """Timestamps before 1900-01-01 become 1900-01-01. DPV1: <ORIGIN>."""
    low = F.lit("1900-01-01 00:00:00").cast("timestamp")
    return df.select(*[F.when(F.col(c) < low, low).otherwise(F.col(c)).alias(c) if t.startswith("timestamp") else F.col(c) for c, t in df.dtypes])


# --- snippet: upper_columns
def upper_case_columns(df):
    """Column names in upper case. DPV1: <ORIGIN>."""
    return df.toDF(*[c.upper() for c in df.columns])


# --- snippet: empty_to_null
def empty_strings_to_null(df):
    """Empty strings become NULL. DPV1: <ORIGIN>."""
    return df.select(*[F.when(F.col(c) == "", None).otherwise(F.col(c)).alias(c) if t == "string" else F.col(c) for c, t in df.dtypes])


# --- snippet: tz_offset_fix
def fix_timezone_offsets(df):
    """'+hh' offsets completed to '+hh:00'. DPV1: <ORIGIN>."""
    return df.select(*[F.when(F.col(c).rlike(r"\+\d{2}$"), F.concat(F.col(c), F.lit(":00"))).otherwise(F.col(c)).alias(c) if t == "string" else F.col(c)
                       for c, t in df.dtypes])


# --- snippet: string_null_over
def null_long_strings(df, limit):
    """Strings longer than limit become NULL. DPV1: <ORIGIN>."""
    return df.select(*[F.when(F.length(F.col(c)) > limit, None).otherwise(F.col(c)).alias(c) if t == "string" else F.col(c) for c, t in df.dtypes])


# --- snippet: string_cut
def cut_strings(df, default, wider=None):
    """Every column cut to default characters, the wider ones to their own size. DPV1: <ORIGIN>."""
    wider = wider or {}
    return df.select(*[F.substring(F.col(f"`{c}`").cast("string"), 1, wider.get(c, default)).alias(c) for c in df.columns])


# --- snippet: dedupe
def drop_duplicates(df, keys):
    """Duplicate rows removed, on the keys when there are keys. DPV1: <ORIGIN>."""
    return df.dropDuplicates(keys or None)


# --- snippet: latest_per_key
def keep_latest_per_key(df, keys, date_column):
    """One row per key: the newest by date_column. DPV1: <ORIGIN>."""
    if not keys or date_column not in df.columns:
        return df
    w = Window.partitionBy(*keys).orderBy(F.col(date_column).desc())
    return df.withColumn("_rn", F.row_number().over(w)).filter("_rn = 1").drop("_rn")


# --- snippet: loading_date
def add_loading_date(df):
    """LOADING_DATE (DPV1 column, kept for consumers) and meta_loaded_at (UTC, lakehouse convention)."""
    return df.withColumn("LOADING_DATE", F.current_timestamp()).withColumn("meta_loaded_at", F.to_utc_timestamp(F.current_timestamp(), "UTC"))


# --- snippet: write_overwrite
def delta_path(name):
    """abfss path of the table '<schema>.<table>' in the source lakehouse (Tables/<schema>/<table>)."""
    return f"{LH_ROOT}/Tables/{name.replace('.', '/')}"


def overwrite_table(df, name):
    """Full load: the table is replaced, schema included; 90 days of history.
    DPV1 write_delta_table(mode="overwrite", overwriteSchema=True) and NTBK_COMMON_MASTER_RAW_TO_CLEAN retention settings."""
    (df.write.format("delta").mode("overwrite").option("overwriteSchema", "true")
       .option("delta.logRetentionDuration", "interval 90 days").option("delta.deletedFileRetentionDuration", "interval 90 days")
       .save(delta_path(name)))


# --- snippet: write_merge
def merge_table(df, name, keys, date_column):
    """Incremental load: MERGE on the keys; a matched row is updated only when it is not older; new rows inserted.
    DPV1 NTBK_RAPID7_CHILD_RAW_TO_CLEAN / NTBK_SERVICENOW_CHILD_JSON_TO_CLEANSED (deltaTable.merge ... whenMatchedUpdateAll ... whenNotMatchedInsertAll)."""
    target = DeltaTable.forPath(spark, delta_path(name))
    on = " AND ".join(f"t.`{k}` <=> u.`{k}`" for k in keys)
    m = target.alias("t").merge(df.alias("u"), on)
    m = m.whenMatchedUpdateAll(condition=f"u.`{date_column}` >= t.`{date_column}`") if date_column in df.columns else m.whenMatchedUpdateAll()
    m.whenNotMatchedInsertAll().execute()
    return target


# --- snippet: delete_logs
def apply_delete_logs(row, keys, target):
    """Rows of the target whose keys are in the delete log of this run are deleted (not created after the deletion).
    DPV1 NTBK_<SRC>_CHILD_JSON_TO_CLEANSED (DELETE_LOGS)."""
    for log in DELETE_LOGS.get(((row.get("SchemaName") or "") + "." + (row.get("TableName") or "")).lower(), []):
        dels, _ = read_table(log)
        if dels is None:
            continue
        dels = upper_case_columns(dels) if UPPER_COLUMNS else dels
        dkeys = [k for k in keys_of(log) if k in dels.columns] or keys
        cond = " AND ".join(f"t.`{k}` <=> d.`{dk}`" for k, dk in zip(keys, dkeys))
        if "DELETEDDATE" in dels.columns and row.get("WatermarkColumn"):
            cond += f" AND t.`{col(row['WatermarkColumn'])}` <= d.DELETEDDATE"
        target.alias("t").merge(dels.dropDuplicates(dkeys).alias("d"), cond).whenMatchedDelete().execute()
