# Project Rules

This project builds a local Windows application for generating editable technical-proposal PowerPoint files from structured inputs.

Before changing code, read `README-AI.md`, `SPEC.md`, `PROJECT_FRAMEWORK.md`, and `PROJECT_LOG.md`.

## Engineering

- Follow the `engineering-standard` skill for scope, verification, and change discipline.
- Follow the `dce-generation` skill for PPTX and Office Open XML safety.
- Keep delivery phased: deterministic template generation before AI, preview, and advanced editing.
- Treat files in `templates/` and `assets/` as source inputs; treat `output/` as generated data.
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
$env:QT_QPA_PLATFORM='offscreen'
python -m unittest discover -s tests -v
python -m py_compile generate_ppt.py render_template.py run_desktop.py ppt_generator\auto_solution.py ppt_generator\auto_solution_application.py ppt_generator\auto_solution_repository.py ppt_generator\requirement_management.py ppt_generator\solution_generation.py ppt_generator\scheme_visual_lab.py ppt_generator\no_cad_scheme.py ppt_generator\scheme_application.py ppt_generator\codex_image.py ppt_generator\openai_image.py ppt_generator\builder.py ppt_generator\excel_mapper.py ppt_generator\module_service.py ppt_generator\navigation_style.py ppt_generator\office_preview.py ppt_generator\office_preview_server.py ppt_generator\optical_far.py ppt_generator\preview.py ppt_generator\project.py ppt_generator\scheme_service.py ppt_generator\source_parser.py ppt_generator\template_renderer.py ppt_generator\ui\app.py ppt_generator\ui\auto_solution_editor.py ppt_generator\ui\candidate_solution_widget.py ppt_generator\ui\historical_retrieval_widget.py ppt_generator\ui\requirement_management_widget.py ppt_generator\ui\scheme_visual_lab.py ppt_generator\ui\no_cad_scheme_editor.py ppt_generator\ui\module_visual_overview.py ppt_generator\ui\openai_image_dialog.py ppt_generator\ui\dialogs.py ppt_generator\ui\main_window.py ppt_generator\ui\module_editor.py ppt_generator\ui\scheme_editor.py ppt_generator\ui\slide_preview.py tools\build_auto_solution_v2_demo.py tools\build_scheme_visual_lab_sample.py tools\build_no_cad_scheme_sample.py
```

For generated PPTX files, also verify the ZIP signature and required package entries.
