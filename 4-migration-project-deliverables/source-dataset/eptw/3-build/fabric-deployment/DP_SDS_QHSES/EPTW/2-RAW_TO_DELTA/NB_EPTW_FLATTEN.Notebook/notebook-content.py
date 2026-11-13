# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   }
# META }

# MARKDOWN ********************

# # NB_EPTW_FLATTEN
# Turns the EPTW files of this run, as delivered in `Files/landing/eptw/<run>/`, into parquet in `Files/raw/eptw/<run>/<table>/`: the record array is exploded and nested fields are flattened (`a.b` => `a_b`). Only the tables that copied are processed.
# 
# **Replaces (DPV1):** the first half of `NTBK_COMMON_CHILD_META_RAW_TO_CLEAN, NTBK_COMMON_MASTER_RAW_TO_CLEAN, NTBK_EPTW_CHILD_FULL_RAW_TO_CLEAN, NTBK_EPTW_CHILD_META_RAW_TO_CLEAN, NTBK_EPTW_CHILD_RAW_TO_CLEANSED, NTBK_EPTW_MASTER_RAW_TO_CLEANSED` (read LANDING, explode, `flatten_json_df`). No cleaning and no table here: `NB_EPTW_RAW_TO_DELTA` loads the parquet.
# 
# The functions come from `0-shared/templates/raw-to-delta-snippets.py` of the migration repository.

# CELL ********************

# Parameters: PL_EPTW_RAW_TO_DELTA overrides them; the values below let the notebook run on its own.
lakehouse_name = globals().get("lakehouse_name", "LH_SDS_EPTW")   # looked up in the workspace this notebook runs in: no default lakehouse needed
tables_json = globals().get("tables_json", "[]")        # catalog rows of the tables that copied in this run
run_partition = globals().get("run_partition", "")      # yyyy/MM/dd/HHhmm of this run; empty = newest folder
landing_root = globals().get("landing_root", "landing/eptw").strip("/")
raw_root = globals().get("raw_root", "raw/eptw").strip("/")
max_parallel = int(globals().get("max_parallel", "8"))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Settings, rows of the tables that copied
import fnmatch, json, time
from concurrent.futures import ThreadPoolExecutor
import notebookutils
from pyspark.sql import functions as F

# Source lakehouse: found by name in the workspace this notebook runs in (same name in DEV, UAT and PRD), so nothing has to be attached
_lh = notebookutils.lakehouse.get(lakehouse_name, notebookutils.runtime.context["currentWorkspaceId"])
LH_ROOT = _lh["properties"]["abfsPath"].rstrip("/")   # OneLake root of this lakehouse

IS_REST = True   # REST: one <table>.json per table in the run folder; files: the SourcePath wildcard
SOURCE_FORMAT = "json"
JSON_ROOT = None   # DPV1 explode(col("…")): the array holding the records
READ_OPTIONS = {"json": {"multiLine": "false"}}

rows = [json.loads(r) if isinstance(r, str) else r for r in json.loads(tables_json or "[]")]

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


def landing_files(row):
    """(run folder in landing, [(file name, bytes)]) of this table: REST <table>.json, files the SourcePath wildcard."""
    land = f"{LH_ROOT}/Files/{landing_root}/{run_partition or latest_run(f'{LH_ROOT}/Files/{landing_root}')}"
    pattern = (f"{row['EntityName']}.json" if IS_REST else (row.get("SourcePath") or "*")).lower()
    if not has_files(land):
        return land, []
    return land, [(e.name, e.size) for e in notebookutils.fs.ls(land) if not e.isDir and (fnmatch.fnmatch(e.name.lower(), pattern) or fnmatch.fnmatch(e.name.lower(), pattern.replace(".json", "~*.json")))]


def flatten_to_raw(row):
    """NB_EPTW_FLATTEN: the files of this table in Files/landing/<src>/<run>/ (REST: <table>.json; files: the SourcePath wildcard)
    => record array exploded => nested fields flattened => parquet in Files/raw/<src>/<run>/<table>/. Returns the raw folder, or None.
    DPV1 NTBK_EPTW_CHILD_JSON_TO_CLEANSED (first half: read LANDING, explode, flatten_json_df) and NTBK_*_EXCEL_TO_PARQUET."""
    land, files = landing_files(row)
    if not files:
        return None
    files = [n for n, _ in files]
    fmt = (row.get("SourceFormat") or SOURCE_FORMAT).lower()
    options = dict(READ_OPTIONS.get(fmt, {}), **json.loads(row.get("FileOptions") or "{}"))
    df = spark.read.options(**options).format(fmt).load([f"{land}/{n}" for n in files])
    root = row.get("RootPath") or JSON_ROOT
    if root and root in df.columns:
        df = df.select(F.explode_outer(F.col(root)).alias("_r")).select("_r.*")
    raw = land.replace(f"{LH_ROOT}/Files/{landing_root}", f"{LH_ROOT}/Files/{raw_root}", 1) + f"/{row['EntityName']}"
    flatten(df).write.mode("overwrite").parquet(raw)
    return raw

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Run the tables in parallel in this one session, 3 attempts each. A table that fails is reported, not raised.


def flatten_with_retry(row):
    for attempt in range(1, 4):
        try:
            return row, flatten_to_raw(row), None
        except Exception as exc:
            error = str(exc)[:600]
            print(f"FLATTEN {row.get('TableName')} attempt {attempt} failed: {error}")
            time.sleep(30)
    return row, None, error


with ThreadPoolExecutor(max_parallel) as pool:
    results = list(pool.map(flatten_with_retry, rows))

flattened = [json.dumps(row) for row, raw, error in results if not error]   # no file in landing = nothing new: still passed on
failed = [f"{row.get('SchemaName')}.{row.get('TableName')} (flatten): {error}" for row, raw, error in results if error]
print(json.dumps({"flattened": len(flattened), "failed": failed}, indent=2))
notebookutils.notebook.exit(json.dumps({"flattened": flattened, "failed": failed}))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
