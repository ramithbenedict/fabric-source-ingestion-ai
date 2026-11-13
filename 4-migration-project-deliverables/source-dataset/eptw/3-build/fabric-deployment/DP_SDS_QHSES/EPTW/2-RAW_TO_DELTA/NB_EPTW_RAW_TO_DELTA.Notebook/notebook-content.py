# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   }
# META }

# MARKDOWN ********************

# # NB_EPTW_RAW_TO_DELTA
# Loads the EPTW tables that copied in this run (and were flattened by `NB_EPTW_FLATTEN`) from raw into `dbo` tables of `LH_SDS_EPTW`, all tables in one Spark session. A table that fails is reported; the others still load.
# 
# **Replaces (DPV1):** `NTBK_COMMON_CHILD_META_RAW_TO_CLEAN`, `NTBK_COMMON_MASTER_RAW_TO_CLEAN`, `NTBK_EPTW_CHILD_FULL_RAW_TO_CLEAN`, `NTBK_EPTW_CHILD_META_RAW_TO_CLEAN`, `NTBK_EPTW_CHILD_RAW_TO_CLEANSED`, `NTBK_EPTW_MASTER_RAW_TO_CLEANSED` (a master notebook that started one child and one META notebook per table).
# 
# **Method:** semi-structured, incremental: MERGE on the keys, newest row wins.
# 
# **Per table:** read raw => `clean()` => write. Cleaning steps kept from DPV1:
# - timestamps before 1900-01-01 set to 1900-01-01 (DPV1 `NTBK_EPTW_CHILD_FULL_RAW_TO_CLEAN`)
# 
# The functions come from `0-shared/templates/raw-to-delta-snippets.py` of the migration repository: change them there and regenerate.

# CELL ********************

# Parameters: PL_EPTW_RAW_TO_DELTA overrides them; the values below let the notebook run on its own.
lakehouse_name = globals().get("lakehouse_name", "LH_SDS_EPTW")   # looked up in the workspace this notebook runs in: no default lakehouse needed
tables_json = globals().get("tables_json", "[]")        # catalog rows of the tables that copied (or flattened) in this run
run_partition = globals().get("run_partition", "")      # yyyy/MM/dd/HHhmm of this run; empty = newest folder
raw_root = globals().get("raw_root", "raw/eptw").strip("/")
target_schema = globals().get("target_schema", "dbo")
max_parallel = int(globals().get("max_parallel", "8"))
pipeline_name = globals().get("pipeline_name", "NB_EPTW_RAW_TO_DELTA")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Settings, catalog rows, small helpers
import json, re, time
from concurrent.futures import ThreadPoolExecutor
import notebookutils
from delta.tables import DeltaTable
from pyspark.sql import functions as F, Window

# Source lakehouse: found by name in the workspace this notebook runs in (same name in DEV, UAT and PRD), so nothing has to be attached
_lh = notebookutils.lakehouse.get(lakehouse_name, notebookutils.runtime.context["currentWorkspaceId"])
LH_ROOT = _lh["properties"]["abfsPath"].rstrip("/")   # OneLake root of this lakehouse

# Spark settings of DPV1 NTBK_COMMON_MASTER_RAW_TO_CLEAN (%%configure)
spark.conf.set("spark.sql.parquet.datetimeRebaseModeInRead", "CORRECTED")   # dates before 1582
spark.conf.set("spark.sql.parquet.int96RebaseModeInRead", "CORRECTED")
spark.conf.set("spark.sql.parquet.enableVectorizedReader", "false")  # DPV1 decimal workaround
spark.conf.set("spark.databricks.delta.schema.autoMerge.enabled", "true")     # new source columns are added by MERGE

rows = [json.loads(r) if isinstance(r, str) else r for r in json.loads(tables_json or "[]")]  # only the tables that copied
data_rows = rows


def keys_of(row):
    """KeyColumns of a catalog row ('A|B', 'A,B' or 'A.B')."""
    return [k.strip() for k in re.split(r"[|,.]", row.get("KeyColumns") or "") if k.strip()]

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Reusable functions (0-shared/templates/raw-to-delta-snippets.py in the migration repository)

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


def read_parquet(path):
    """The parquet of a folder, with the file each row came from; (None, path) when there is nothing to read."""
    if not path or not has_files(path):
        return None, path
    return spark.read.parquet(path).withColumn("meta_source_file", F.col("_metadata.file_path")), path


def table_path(row):
    """Parquet the FLATTEN notebook wrote for this run: Files/raw/<src>/<run>/<table>/."""
    base = f"{LH_ROOT}/Files/{raw_root}"
    run = run_partition or latest_run(base)
    return f"{base}/{run}/{row['EntityName']}" if run else None


def read_table(row):
    return read_parquet(table_path(row))


def clamp_dates_1900(df):
    """Timestamps before 1900-01-01 become 1900-01-01. DPV1: NTBK_EPTW_CHILD_FULL_RAW_TO_CLEAN."""
    low = F.lit("1900-01-01 00:00:00").cast("timestamp")
    return df.select(*[F.when(F.col(c) < low, low).otherwise(F.col(c)).alias(c) if t.startswith("timestamp") else F.col(c) for c, t in df.dtypes])


def keep_latest_per_key(df, keys, date_column):
    """One row per key: the newest by date_column. DPV1: NTBK_COMMON_CHILD_META_RAW_TO_CLEAN, NTBK_COMMON_MASTER_RAW_TO_CLEAN, NTBK_EPTW_CHILD_FULL_RAW_TO_CLEAN, NTBK_EPTW_CHILD_META_RAW_TO_CLEAN, NTBK_EPTW_CHILD_RAW_TO_CLEANSED, NTBK_EPTW_MASTER_RAW_TO_CLEANSED."""
    if not keys or date_column not in df.columns:
        return df
    w = Window.partitionBy(*keys).orderBy(F.col(date_column).desc())
    return df.withColumn("_rn", F.row_number().over(w)).filter("_rn = 1").drop("_rn")


def add_loading_date(df):
    """LOADING_DATE (DPV1 column, kept for consumers) and meta_loaded_at (UTC, lakehouse convention)."""
    return df.withColumn("LOADING_DATE", F.current_timestamp()).withColumn("meta_loaded_at", F.to_utc_timestamp(F.current_timestamp(), "UTC"))


def delta_path(name):
    """abfss path of the table '<schema>.<table>' in the source lakehouse (Tables/<schema>/<table>)."""
    return f"{LH_ROOT}/Tables/{name.replace('.', '/')}"


def overwrite_table(df, name):
    """Full load: the table is replaced, schema included; 90 days of history.
    DPV1 write_delta_table(mode="overwrite", overwriteSchema=True) and NTBK_COMMON_MASTER_RAW_TO_CLEAN retention settings."""
    (df.write.format("delta").mode("overwrite").option("overwriteSchema", "true")
       .option("delta.logRetentionDuration", "interval 90 days").option("delta.deletedFileRetentionDuration", "interval 90 days")
       .save(delta_path(name)))


def merge_table(df, name, keys, date_column):
    """Incremental load: MERGE on the keys; a matched row is updated only when it is not older; new rows inserted.
    DPV1 NTBK_RAPID7_CHILD_RAW_TO_CLEAN / NTBK_SERVICENOW_CHILD_JSON_TO_CLEANSED (deltaTable.merge ... whenMatchedUpdateAll ... whenNotMatchedInsertAll)."""
    target = DeltaTable.forPath(spark, delta_path(name))
    on = " AND ".join(f"t.`{k}` <=> u.`{k}`" for k in keys)
    m = target.alias("t").merge(df.alias("u"), on)
    m = m.whenMatchedUpdateAll(condition=f"u.`{date_column}` >= t.`{date_column}`") if date_column in df.columns else m.whenMatchedUpdateAll()
    m.whenNotMatchedInsertAll().execute()
    return target

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cleaning of one table: the steps of the DPV1 child notebook, in its order
def clean(df, row):
    """timestamps before 1900-01-01 set to 1900-01-01."""
    df = clamp_dates_1900(df)                   # DPV1: NTBK_EPTW_CHILD_FULL_RAW_TO_CLEAN
    keys = [k for k in keys_of(row) if k in df.columns]
    df = keep_latest_per_key(df, keys, row.get("WatermarkColumn"))  # DPV1: MERGE on UnicityKeys, newest row wins
    return add_loading_date(df)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Load one table: read => clean => write
def load_table(row):
    name = f"{target_schema}.{(row.get('TargetName') or row['TableName']).lower()}"
    df, path = read_table(row)
    if df is None:
        return {"table": name, "mode": "no new data", "source": path}
    df = clean(df, row)
    keys = [k for k in keys_of(row) if k in df.columns]
    if row.get("LoadMethod") == "incremental" and keys and DeltaTable.isDeltaTable(spark, delta_path(name)):
        target = merge_table(df, name, keys, row.get("WatermarkColumn"))
        mode = "merge"
    else:  # full load, or first load of an incremental table
        overwrite_table(df, name)
        mode = "overwrite"
    metrics = DeltaTable.forPath(spark, delta_path(name)).history(1).first()["operationMetrics"] or {}
    return {"table": name, "mode": mode, "source": path, "rows": metrics.get("numOutputRows") or metrics.get("numTargetRowsInserted")}

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Run the tables in parallel in this one session (max_parallel at a time), 3 attempts each.
# A table that fails is reported, not raised: the others still load, and the master lists the failures at the end.
start = time.time()


def run_with_retry(row):
    for attempt in range(1, 4):
        try:
            return dict(load_table(row), SchemaName=row.get("SchemaName"), TableName=row.get("TableName"), LoadMethod=row.get("LoadMethod"), error=None)
        except Exception as exc:
            error = str(exc)[:600]
            print(f"LOAD {row.get('TableName')} attempt {attempt} failed: {error}")
            time.sleep(30)
    return {"SchemaName": row.get("SchemaName"), "TableName": row.get("TableName"), "error": error}


with ThreadPoolExecutor(max_parallel) as pool:
    results = list(pool.map(run_with_retry, data_rows))

loaded = [r for r in results if not r["error"]]
failed = [f"{r['SchemaName']}.{r['TableName']} (load): {r['error']}" for r in results if r["error"]]
summary = {"pipeline_name": pipeline_name, "run_partition": run_partition, "tables": len(data_rows), "loaded": loaded, "failed": failed,
           "execution_time_sec": round(time.time() - start, 1)}
print(json.dumps(summary, indent=2, default=str))
notebookutils.notebook.exit(json.dumps(summary, default=str))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
