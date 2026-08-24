# AI Onboarding

## Purpose

`PPT_Generator` is a local PySide6 desktop project for assembling editable industrial technical-proposal PowerPoint files from configured templates and structured project inputs.

## Read Order

1. `AGENTS.md`
2. `SPEC.md`
3. `PROJECT_FRAMEWORK.md`
4. `PROJECT_LOG.md`
5. `README.md`
6. `ppt_generator/builder.py`
7. `SPEC_TEMPLATE_SPIKE.md`
8. `ppt_generator/template_renderer.py`
9. `SPEC_DESKTOP_MVP.md`
10. `SPEC_MODULAR_EDITOR_MVP.md`
11. `SPEC_EXCEL_MAPPING_WORKBENCH.md`
12. `ppt_generator/project.py`
13. `ppt_generator/excel_mapper.py`
14. `ppt_generator/source_parser.py`
15. `ppt_generator/ui/main_window.py`
16. `SPEC_CURRENT_PAGE_PREVIEW_MVP.md`
17. `SPEC_NAVIGATION_EDITOR_MVP.md`
18. `SPEC_OPTICAL_FAR_TO_PPT.md`
19. `ppt_generator/optical_far.py`
20. `SPEC_EQUIPMENT_SCHEME_MVP.md`
21. `SPEC_EQUIPMENT_INTRO_PPT.md`
22. `SPEC_AUTO_SOLUTION_MODULE_MVP.md`
23. `SPEC_AUTO_SOLUTION_V2.md`
24. `ppt_generator/requirement_management.py`
25. `ppt_generator/solution_generation.py`
26. `ppt_generator/auto_solution_repository.py`
27. `ppt_generator/auto_solution_application.py`
28. `ppt_generator/scheme_service.py`
29. `ppt_generator/ui/scheme_editor.py`
30. `SPEC_SCHEME_VISUAL_LAB_MVP.md`
31. `ppt_generator/scheme_visual_lab.py`
32. `ppt_generator/ui/scheme_visual_lab.py`
33. `SPEC_NO_CAD_LOGIC_SCHEME_MVP.md`
34. `ppt_generator/no_cad_scheme.py`
35. `ppt_generator/ui/no_cad_scheme_editor.py`
36. `SPEC_OPENAI_IMAGE_PROVIDER_MVP.md`
37. `ppt_generator/openai_image.py`
38. `SPEC_CODEX_PRO_IMAGE_PROVIDER_MVP.md`
39. `ppt_generator/codex_image.py`
40. `ppt_generator/ui/openai_image_dialog.py`
41. `SPEC_MODULE_VISUAL_BINDING.md`
42. `ppt_generator/scheme_application.py`
43. `SPEC_MODULE_VISUAL_OVERVIEW.md`
44. `ppt_generator/ui/module_visual_overview.py`
45. `tests/`

## Current Implementation

- Inputs: basic command-line content, or a PPTX template plus manifest and render-data JSON.
- Outputs: editable 16:9 `.pptx` files; original templates are hash-checked and not modified.
- Runtime library: `python-pptx`.
- The NAT6704 template has a configuration-driven M2 renderer spike for text, exact-size tables, and pictures.
- PySide6 desktop MVP: template selection, schema-v2 module/page tree, structured Slot editing, source parsing, image classification, project persistence, and background rendering.
- Generic Excel workbench: worksheet preview, header suggestion, cell/range-to-Slot mapping, reusable rule JSON, and project application.
- Optical FAR workflow: DCE-compatible uniform-layout parsing for detection standards, stations, embedded images, detection speed, camera, lens, and light; matched defects get one page each, while unmatched items share one page explicitly labeled as an OK-sample reference rather than a defect image.
- Equipment-scheme workflow: schema-v5 overview, ordered flow nodes, physical device modules and node-to-module links; overview/modules can persist no-CAD structure definitions, deterministic image prompts, accepted images and provenance. Project JSON now also owns a stable project ID, the live no-CAD Scene and project-scoped AI candidate batch indexes. The structured editor materializes editable flow, equipment-overview and repeated device-module pages while clearing template-specific callouts from replaced engineering images.
- Module service: independent module/page CRUD, page-template registry, stable UUIDs, structure numbering, schema-v1 migration, and Excel row materialization.
- Project renderer: clones page relationship graphs per module instance, applies page/module/global values independently, drops non-visual single-owner slide tags when duplicating one source page, removes unreferenced Slide XML, and keeps the source template unchanged.
- Current-page preview: the upper-right review pane first shows an on-demand persistent source-template thumbnail with a loading overlay, then replaces it with the selected project's live page; it reuses one timeout-limited PowerPoint/WPS child process, caches live PNGs in memory, and preloads adjacent pages.
- Navigation styling: project files persist a `0.42～0.72 in` height, automatic or manual `9～16 pt` font size, active-item `#RRGGBB` background, and 1～7 editable navigation items with template-module ownership. Automatic mode scales from `10 pt @ 0.52 in` up to `14 pt @ 0.72 in`. The full-width navigation background has no Office shadow; there are no inactive white strips or per-item shadows. A solid gray baseline spans the full `0～13.333 in` slide width including the right-side logo area, while navigation cells remain within `0～11.55 in`; the active cell overlays one exact-width red segment at the same height. Instant preview removes the template's fixed old shadow and draws the same solid gray/red lines without a gradient shadow.
- Auto-solution v2: the separate six-stage workspace now has a formal `RequirementRecord`, original-text-preserving categorized configuration, JSON CRUD/copy/archive/version snapshots, a replaceable requirement-suggestion Provider with conservative offline fallback, explainable structured-history retrieval, `CandidateSolution`, `DrawingSpecification`, and deterministic Prompt Builder. The requirement, history, candidate, repository, application, and UI adapters are separate bounded modules. Demo history is explicitly labelled and candidate output still does not merge into `PptProject` or the renderer.
- Scheme Visual Lab: an isolated reviewer converts editable `DrawingSpecification` JSON into a deterministic single-line `LayoutPlan`, traceable SVG structure diagram, provider-neutral `PromptRecipe`, fixed seed pool, hashes, and an engineering checklist. It has no repository/Application dependency, does not write `PptProject`, and only shows vision parts or fixtures explicitly present in the input.
- No-CAD Logic Scheme Editor: the default page inside the lab owns an independent `EquipmentScene`, a 16-item standard module catalog, single-line operations, locked-node behavior, deterministic layout/SVG/brief, and conservative blocking/warning/info checks. Each scene produces one overview visual target plus one target per module; each target has an editable structured definition/additional requirement, deterministic final prompt, target hash, control SVG, accepted image and provenance. It refuses AI handoff when entry/exit, inspection, reject order, connections, dimensions, or left-to-right flow are invalid. The original DrawingSpecification lab remains available as the second page.
- Codex Pro Image Provider MVP: a logic-passed no-CAD visual target defaults to the local Codex runtime with ChatGPT sign-in and plan usage, so it does not require API recharge. Each ephemeral `codex exec` task receives only the target selected inside the AI-effect dialog, its control image and immutable prompt. The modal UI switches among overview/modules, previews current accepted images and new candidates, opens accepted images at full size, supports 1–4 asynchronous candidates, trace manifests and multiple explicit human acceptances before one validated outer write-back. The previous API-key provider remains an explicit pay-as-you-go fallback. Scene/target changes and logic blockers stop both paths.
- Project-owned AI candidate persistence: provider output is isolated under `output/ai_candidates/<projectId>/<targetHash>/<batchId>/`; the AI dialog restores only history whose project ID, target ID and target hash match. Existing project files auto-save a newly generated batch index, while a never-saved project asks the user to save once. Candidate PNGs stay as files rather than JSON blobs.
- No-CAD import Application: `scheme_application.import_no_cad_scene` is the only cross-module writer from `EquipmentScene` to `PptProject.equipment_scheme`. The user must explicitly commit the whole structure; the service upserts imported modules by stable Scene node ID, preserves manually-created modules, registers accepted images as project assets, and never materializes PPT pages automatically.
- Module visual overview: the no-CAD editor opens a large adaptive 1–3 column review mosaic with one card per visual target. It decodes display-sized thumbnails only; clicking an accepted image opens an on-demand original-resolution zoom viewer. The gallery is read-only and never owns a second scene/module state.
- No web service, production history database, editable PowerPoint canvas, external-PPT page import, or installer yet. Auto-solution v2 currently uses an atomic local JSON store and a rule parser; its separate DrawingSpecification lab AI button remains disabled.

## Approved Direction

- Windows 10/11 local desktop application using PySide6 as a replaceable UI shell.
- First presentation type: industrial equipment technical proposal.
- Manual first-time template configuration, followed by reusable one-click generation.
- Excel, Word, and image inputs normalized into structured project data before rendering.
- Online AI API is allowed, but deterministic generation must still work without AI.
- Generated PPTX files must be checked in both Microsoft PowerPoint and WPS.
- Features are developed as bounded modules. Cross-module workflows are coordinated by application services using stable IDs and explicit data contracts/events; UI widgets and module internals do not call each other directly, and shared state has one authoritative owner.
- The detailed plan is in `DEVELOPMENT_PLAN_DRAFT.md`; the concise baseline is in `PROJECT_FRAMEWORK.md`.

## Validation

Use the commands declared in `AGENTS.md`. A successful generation must produce a valid Office ZIP package containing presentation and slide XML.
