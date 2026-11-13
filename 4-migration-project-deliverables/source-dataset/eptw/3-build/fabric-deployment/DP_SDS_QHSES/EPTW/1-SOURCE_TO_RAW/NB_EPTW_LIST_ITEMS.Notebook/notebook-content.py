# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   }
# META }

# MARKDOWN ********************

# # NB_EPTW_LIST_ITEMS
# Reads `list_of_items.json` (the answer of `GetPTWProjects_V1/`, landed by `PL_EPTW_SOURCE_TO_RAW`) and returns the items that have a `cpInternalCode`.
# 
# **Replaces (DPV1):** the Web activities `Get APIM SubKey` and `Get ePTW Projects` and the Filter `@greater(length(item().cpInternalCode), 0)` of `PL_RAWDATA_EPTW`.

# CELL ********************

# Parameters: PL_EPTW_SOURCE_TO_RAW overrides them; the values below let the notebook run on its own.
lakehouse_name = globals().get("lakehouse_name", "LH_SDS_EPTW")   # looked up in the workspace this notebook runs in: no default lakehouse needed
landing_root = globals().get("landing_root", "landing/eptw").strip("/")
run_partition = globals().get("run_partition", "")      # yyyy/MM/dd/HHhmm of this run (the run folder of the landed list)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

import json
import notebookutils

# Source lakehouse: found by name in the workspace this notebook runs in (same name in DEV, UAT and PRD), so nothing has to be attached
_lh = notebookutils.lakehouse.get(lakehouse_name, notebookutils.runtime.context["currentWorkspaceId"])
LH_ROOT = _lh["properties"]["abfsPath"].rstrip("/")   # OneLake root of this lakehouse

ITEM_KEY = "cpInternalCode"      # DPV1 filter: the item has a cpInternalCode (length > 0)
LIST_FILE = "list_of_items.json"    # landed by the Copy 'Land list of items' of PL_EPTW_SOURCE_TO_RAW

path = f"{LH_ROOT}/Files/{landing_root}/{run_partition}/{LIST_FILE}"
text = notebookutils.fs.head(path, 100 * 1024 * 1024)
try:                                   # one JSON document (an array, or one object)
    data = json.loads(text)
except ValueError:                     # JSON lines: one item per line (what a Copy writes for a list)
    data = [json.loads(line) for line in text.splitlines() if line.strip()]
items = data if isinstance(data, list) else [data]
valid = [{ITEM_KEY: i[ITEM_KEY]} for i in items if isinstance(i, dict) and len(str(i.get(ITEM_KEY) or "")) > 0]
print(f"{len(items)} items in the list, {len(valid)} with a {ITEM_KEY}")
notebookutils.notebook.exit(json.dumps(valid))   # the pipeline loops over this array

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
