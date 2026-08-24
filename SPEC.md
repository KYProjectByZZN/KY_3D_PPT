# Spec: PPT Generator 0.1.0 Foundation

## Goal

Create a small standalone project under `D:\test\KY_Project\PPT_Generator` that can generate an editable PowerPoint file and serve as the base for later template-driven work.

## Scope

In scope:

- A documented Python project structure.
- A reusable PPT builder function.
- A command-line generation entry point.
- A 16:9 title slide and optional bullet slide.
- Structural tests for the generated PPTX package.

Out of scope:

- GUI, web service, database, AI-generated content, PDF conversion, complex charts, and company-specific templates.
- Editing existing PPTX files.
- Automatic overwrite of existing output files.

## Inputs And Outputs

Inputs:

- Title, subtitle, zero or more bullet points, and output path.

Outputs:

- One editable `.pptx` presentation.

## Behavior

- Create the output parent directory when it does not exist.
- Reject a non-`.pptx` output path.
- Reject an existing output file unless overwrite is explicitly enabled.
- Always create a title slide.
- Create a content slide only when bullet points are supplied.
- Use a standard 16:9 slide size and Chinese-capable default font.

## Risk

- Generated Office files may be corrupt despite a successful save; tests must inspect the ZIP structure and reopen the file.
- Font rendering can vary between computers; text remains editable and does not embed fonts.

## Acceptance Tests

- Given a title and two bullets, generation creates a two-slide PPTX.
- The output starts with the ZIP signature and contains `[Content_Types].xml`, `ppt/presentation.xml`, and slide XML.
- Reopening with `python-pptx` returns the expected title and slide count.
- Existing output is protected unless overwrite is enabled.

## Implementation Notes

- Use `python-pptx` for the initial implementation.
- Keep source in `ppt_generator/` and generated files in `output/`.
