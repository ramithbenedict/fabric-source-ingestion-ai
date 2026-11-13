# 4-migration-project-deliverables

One folder per service offering, then one folder per project. Every stage writes only into its own folder, so a project folder reads as the complete record of its migration. Pages stay short: reference detail is parked in the `analysis/` folder of its stage.

```
4-migration-project-deliverables/
├── migration-portfolio.md                 every project of both services: progress, stages, gates, risks, change-log index (track.py)
├── source-dataset/                        Source Dataset Migration (wf-1 + wf-2)
│   └── <source>/                          e.g. geos (lowercase folder)
│       ├── 0_progress_tracking/           <source>_tracking.md (status + change log) · progress.json (state, framing inputs)
│       ├── 1-framing/                     01-scope-analysis.md · 02-object-mapping.md · 03-target-design-and-plan.md
│       │   └── analysis/                  dpv1-inventory.md: full DPV1 inventory, name check, DPV1 environment values (reference)
│       ├── 2-legacy-code/                 copy of the DPV1 code, rebuilt by extract_scope_code.py (not in Git)
│       ├── 3-build/
│       │   ├── fabric-deployment/         same layout as REPO-FABRIC-DEPLOYMENT, copied there by deploy_publish.py
│       │   │   └── <WORKSPACE>/           workspace folder, no environment suffix
│       │   │       ├── VL_MAIN.VariableLibrary/
│       │   │       ├── WH_CATALOG_<SOURCE>.Warehouse/   view [CATALOG].[<source>_catalog]
│       │   │       └── <SOURCE>/  0-ORCHESTRATION/ · 1-SOURCE_TO_RAW/ · 2-RAW_TO_DELTA/ · LH_SDS_<SOURCE>.Lakehouse/
│       │   ├── build-notes/               build-notes.md (one section per stage, hand-over) · connections.md (connections to create)
│       │   │                              · catalog-profile.json (read by the scripts)
│       │   └── analysis/                  build-details.md: catalog columns, contract tables with DPV1 access paths (reference)
│       ├── review/                        gap-review.md + .json (latest review) · fix-log.md (newest run first)
│       └── source-dataset-contract.json   hand-over to data products (read by scripts)
└── data-product/                          Data Product Migration (wf-1 + wf-3 + wf-4)
    └── <project>/                         same layout, plus 3-build/equivalence-tests/ and 4-dacpac/ (retarget, lint, build reports)

Both services: `<project>/data-validation/` (wf-5, m-data-validator): validation-config.json · validation-report.md · validation-results.json · run-history.md · analysis/validation-details.md
```

A project that needs both services (e.g. GAIA) has one folder in each. Every Fabric item is in `3-build/fabric-deployment/`, in the Fabric Git format and exactly the REPO-FABRIC-DEPLOYMENT layout defined in `2-config/conventions/01-general/fabric-git-repo-structure.md` (workspace folders without environment suffix, `database-projects/DPG-<GROUP>/`), so it can be copied to the deployment repository unchanged. Writing directly to the deployment repository will use `deployment_repo` in `2-config/migration/paths.json` (not used yet).
