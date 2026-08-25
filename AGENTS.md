# Project Rules

This project builds a local Windows application for generating editable technical-proposal PowerPoint files from structured inputs.

Before changing code, read `README-AI.md` and `PROJECT_INDEX.md`, then read only the Spec routed for the current task. Read `PROJECT_LOG.md` only for targeted history lookup.

## Engineering

- Follow the `engineering-standard` skill for scope, verification, and change discipline.
- Follow the `dce-generation` skill for PPTX and Office Open XML safety.
- Keep delivery phased: deterministic template generation before AI, preview, and advanced editing.
- Treat files in `templates/` and `assets/` as source inputs. Treat `output/`, `projects/`, `exports/`, `research_repos/`, `.codegraph/`, caches and logs as untracked runtime data.
- Store application-owned data under `%LOCALAPPDATA%\KY_Project\PPT_Generator` unless `KY_PPT_APP_DATA_ROOT` explicitly overrides it.
- Do not overwrite an existing PPTX unless the caller explicitly requests it.
- Do not edit PPTX ZIP/XML directly unless `python-pptx` cannot preserve the required structure.
- Keep business logic independent from PySide6 so the UI can be replaced without rewriting the core.
- Develop each feature as a bounded module that owns its model, service, UI adapter, and focused tests.
- Route cross-module workflows through explicit application services, typed data objects/events, and stable IDs; UI widgets and module internals must not call each other directly.
- Keep one authoritative owner for shared state and prefer one-way synchronization over duplicated state or bidirectional callback chains.
- Introduce shared abstractions only after a real second consumer exists; modularity must reduce coupling without creating speculative framework layers.
- Update `PROJECT_LOG.md` after each implementation task with scope, result, verification, and next step.

## Quality Gate

Run before handing off code changes:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\quality_gate.ps1
```

For generated PPTX files, also verify the ZIP signature and required package entries.
