# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   }
# META }

# MARKDOWN ********************

# # NB_WPS_RAW_TO_DELTA
# Loads the WPS tables that copied in this run from raw into `dbo` tables of `LH_SDS_WPS`, all tables in one Spark session. A table that fails is reported; the others still load.
# 
# **Replaces (DPV1):** `NTBK_COMMON_CHILD_META_RAW_TO_CLEAN`, `NTBK_COMMON_MASTER_RAW_TO_CLEAN`, `NTBK_WPS_CHILD_FULL_RAW_TO_CLEAN` (a master notebook that started one child and one META notebook per table).
# 
# **Method:** structured, full: each table is replaced.
# 
# **Per table:** read raw => `clean()` => write. Cleaning steps kept from DPV1:
# - timestamps before 1900-01-01 set to 1900-01-01 (DPV1 `NTBK_WPS_CHILD_FULL_RAW_TO_CLEAN`)
# 
# The functions come from `0-shared/templates/raw-to-delta-snippets.py` of the migration repository: change them there and regenerate.

# CELL ********************

# Parameters: PL_WPS_RAW_TO_DELTA overrides them; the values below let the notebook run on its own.
lakehouse_name = globals().get("lakehouse_name", "LH_SDS_WPS")   # looked up in the workspace this notebook runs in: no default lakehouse needed
tables_json = globals().get("tables_json", "[]")        # catalog rows of the tables that copied (or flattened) in this run
run_partition = globals().get("run_partition", "")      # yyyy/MM/dd/HHhmm of this run; empty = newest folder
raw_root = globals().get("raw_root", "raw/wps").strip("/")
target_schema = globals().get("target_schema", "dbo")
max_parallel = int(globals().get("max_parallel", "8"))
pipeline_name = globals().get("pipeline_name", "NB_WPS_RAW_TO_DELTA")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Settings, catalog rows, small helpers
import fnmatch, json, re, time
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

UPPER_COLUMNS = False   # DPV1 upper-cased the column names: keys and dates are looked up in upper case

rows = [json.loads(r) if isinstance(r, str) else r for r in json.loads(tables_json or "[]")]  # only the tables that copied
truthy = lambda v: str(v).strip().lower() in ("1", "true")
data_rows = [r for r in rows if not truthy(r.get("IsDeleteLog"))]
DELETE_LOGS = {}
for r in rows:
    if truthy(r.get("IsDeleteLog")):
        DELETE_LOGS.setdefault(((r.get("SchemaName") or "") + "." + (r.get("DeleteTarget") or "")).lower(), []).append(r)


def col(name):
    """A column name as it is after cleaning."""
    return (name.upper() if UPPER_COLUMNS else name) if name else name


def keys_of(row):
    """KeyColumns of a catalog row ('A|B', 'A,B' or 'A.B')."""
    return [col(k.strip()) for k in re.split(r"[|,.]", row.get("KeyColumns") or "") if k.strip()]

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


def table_path(row):
    """Raw parquet of the table: Files/raw/<src>/<table>/ (one folder, overwritten at each run).
    DPV1 NTBK_WPS_CHILD_FULL_RAW_TO_CLEAN: spark.read.parquet(RAW/DATASOURCE=WPS/<SCHEMA>.<TABLE>/)."""
    return f"{LH_ROOT}/Files/{raw_root}/{row['EntityName']}{row.get('FolderTail') or ''}"


def read_table(row):
    return read_parquet(table_path(row))


def clamp_dates_1900(df):
    """Timestamps before 1900-01-01 become 1900-01-01. DPV1: NTBK_WPS_CHILD_FULL_RAW_TO_CLEAN."""
    low = F.lit("1900-01-01 00:00:00").cast("timestamp")
    return df.select(*[F.when(F.col(c) < low, low).otherwise(F.col(c)).alias(c) if t.startswith("timestamp") else F.col(c) for c, t in df.dtypes])


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

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cleaning of one table: the steps of the DPV1 child notebook, in its order
def clean(df, row):
    """timestamps before 1900-01-01 set to 1900-01-01."""
    df = clamp_dates_1900(df)                   # DPV1: NTBK_WPS_CHILD_FULL_RAW_TO_CLEAN
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

# Run the tables in parallel, 3 attempts each (DPV1 NTBK_COMMON_MASTER_RAW_TO_CLEAN: ThreadPoolExecutor, retries, 30 s wait).
# A table that fails is reported, not raised: the others still load, and the master lists the failures at the end.
# One Spark session for every table: max_parallel tables at a time, the others wait in the queue. The largest tables start first,
# and each table thread has its own scheduler pool, so with FAIR scheduling a large table never holds all the cores.
start = time.time()
FAIR = spark.sparkContext.getConf().get("spark.scheduler.mode", "FIFO").upper() == "FAIR"
print(f"{len(data_rows)} tables, {max_parallel} at a time, scheduler {'FAIR' if FAIR else 'FIFO (set spark.scheduler.mode=FAIR in the workspace Spark settings)'}")
with ThreadPoolExecutor(max_parallel) as pool:
    sizes = list(pool.map(lambda r: folder_size(table_path(r) or ""), data_rows))
data_rows = [r for _, r in sorted(zip(sizes, data_rows), key=lambda x: -x[0])]


def run_with_retry(row):
    spark.sparkContext.setLocalProperty("spark.scheduler.pool", (row.get("TableName") or "table")[:80])
    for attempt in range(1, 4):
        try:
            return dict(load_table(row), SchemaName=row.get("SchemaName"), TableName=row.get("TableName"), error=None)
        except Exception as exc:
            error = str(exc)[:600]
            print(f"LOAD {row.get('TableName')} attempt {attempt} failed: {error}")
            time.sleep(30)
    return {"SchemaName": row.get("SchemaName"), "TableName": row.get("TableName"), "error": error}


with ThreadPoolExecutor(max_parallel) as pool:
    results = list(pool.map(run_with_retry, data_rows))

loaded = [r for r in results if not r["error"]]
done = {(r["SchemaName"], (r["TableName"] or "").lower()) for r in loaded}  # a delete log counts as loaded when its target loaded
loaded += [{"SchemaName": r.get("SchemaName"), "TableName": r.get("TableName"), "mode": "delete log applied"}
           for r in rows if truthy(r.get("IsDeleteLog")) and (r.get("SchemaName"), (r.get("DeleteTarget") or "").lower()) in done]
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
