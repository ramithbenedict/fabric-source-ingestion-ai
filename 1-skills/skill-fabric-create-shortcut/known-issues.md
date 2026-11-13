---
title: Fabric Create Shortcut - Known Issues
description: Execution-derived issues and workarounds for the WF1 Stage 2a shortcut-only skill.
---

## Known Issues And Workarounds

| # | Date | Issue | Severity | Status | Workaround |
| --- | --- | --- | --- | --- | --- |
| 1 | 2026-05-05 | Invalid shortcut name characters can cause Fabric sync failures. | high | Open | Sanitize the shortcut `name` by lowercasing and replacing every forbidden character with `_`. |
| 2 | 2026-05-05 | ADLS subpath case mismatch causes target-path-not-found errors. | high | Open | Preserve the discovered folder name exactly in the final `subpath` segment and validate before writing. |
| 3 | 2026-05-05 | Missing or wrong Variable Library variables can produce broken shortcuts after sync. | high | Open | Resolve and validate `shortcut_connection_var` and `shortcut_location_var` from the selected Variable Library before writing the file. |
| 4 | 2026-05-05 | Duplicate ADLS questions create operator confusion and inconsistent values. | medium | Open | Treat the selected Variable Library as the primary source of truth and ask only for unresolved inputs. |
