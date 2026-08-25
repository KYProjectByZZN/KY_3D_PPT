# Project Index

这是 AI 和工程师进入项目的默认索引。先按任务定位，再读取对应 Spec 与实现；`PROJECT_LOG.md` 仅在追溯历史决策时读取。

## 当前基线

- 版本：0.9.8
- 产品：Windows 本地 PySide6 工业技术方案 PPT 工作台
- 正式状态：`PptProject`；无 CAD 编辑状态：`EquipmentScene`
- 输出：可编辑 `.pptx`；模板必须保持不变
- 用户数据：`%LOCALAPPDATA%\KY_Project\PPT_Generator`
- 全量质量门：`powershell -ExecutionPolicy Bypass -File .\tools\quality_gate.ps1`

## 任务路由

| 任务 | 先读 Spec | 核心实现 | 重点测试 |
|---|---|---|---|
| 项目保存/路径/恢复 | `SPEC_STABILITY_BASELINE_V097.md` | `app_paths.py`, `project.py`, `project_session.py` | `test_app_paths.py`, `test_project_and_sources.py`, `test_ui.py` |
| 模板 Slot 渲染 | `SPEC_TEMPLATE_SPIKE.md` | `template_renderer.py`, `io_utils.py` | `test_template_renderer.py`, `test_project_renderer.py` |
| 模块/页面编辑 | `SPEC_MODULAR_EDITOR_MVP.md` | `module_service.py`, `ui/module_editor.py` | `test_module_service.py`, `test_ui.py` |
| 当前页预览 | `SPEC_CURRENT_PAGE_PREVIEW_MVP.md` | `preview.py`, `office_preview.py`, `ui/slide_preview.py` | `test_preview.py`, `test_ui.py` |
| 顶部导航 | `SPEC_NAVIGATION_EDITOR_MVP.md` | `navigation_style.py`, `ui/dialogs.py` | `test_navigation_style.py`, `test_ui.py` |
| Excel/FAR | `SPEC_EXCEL_MAPPING_WORKBENCH.md`, `SPEC_OPTICAL_FAR_TO_PPT.md` | `excel_mapper.py`, `optical_far.py` | `test_excel_mapper.py`, `test_optical_far.py` |
| 正式设备方案/一键图片同步 | `SPEC_EQUIPMENT_SCHEME_MVP.md`, `SPEC_PROJECT_VISUAL_SYNC_V098.md` | `scheme_service.py`, `scheme_application.py`, `ui/scheme_editor.py` | `test_scheme_service.py`, `test_scheme_application.py`, `test_ui.py` |
| 无 CAD 逻辑 | `SPEC_NO_CAD_LOGIC_SCHEME_MVP.md` | `no_cad_scheme.py`, `ui/no_cad_scheme_editor.py` | `test_no_cad_scheme.py`, `test_no_cad_scheme_ui.py` |
| AI 候选图 | `SPEC_MODULE_VISUAL_BINDING.md`, `SPEC_PROJECT_AI_IMAGE_PERSISTENCE.md` | `codex_image.py`, `openai_image.py`, `ui/openai_image_dialog.py` | `test_codex_image.py`, `test_openai_image.py`, `test_ai_image_persistence.py` |
| 自动方案 v2 | `SPEC_AUTO_SOLUTION_V2.md` | `auto_solution_application.py`, `solution_generation.py` | `test_auto_solution_v2.py` |

## 状态与联动

```text
Excel / Word / 图片 / FAR
        ↓ 显式解析或应用
PptProject（正式项目唯一状态）
        ↓ render_project
暂存 PPTX → ZIP/页数/重开校验 → 原子替换正式输出

EquipmentScene（无CAD实验室唯一状态）
        ↓ scheme_application.import_no_cad_scene（人工触发）
PptProject.equipment_scheme
```

- UI 控件不得直接成为第二份业务状态。
- 模块间联动只通过稳定 ID、数据对象或 Application 服务。
- AI 图片只提供候选外观，不决定设备逻辑、模块顺序或连接关系。
- 生成失败必须保留旧项目和旧 PPT。

## 文件边界

| 类别 | 位置 | Git |
|---|---|---|
| 源码/测试/文档 | 项目根目录 | 跟踪 |
| PPTX/XLSX 模板与示例 | `templates/`, `examples/` | Git LFS |
| 用户项目与素材 | `%LOCALAPPDATA%\KY_Project\PPT_Generator\data` | 不跟踪 |
| 预览缓存 | 同上 `cache` | 不跟踪 |
| 运行日志 | 同上 `logs` | 不跟踪 |
| 人工导出 | `output/` 或用户选择目录 | 不跟踪 |
| 外部研究仓库 | `research_repos/` | 不跟踪 |
| 代码索引 | `.codegraph/` | 不跟踪 |

## 修改检查

1. 先写或选择任务 Spec，明确非目标和验收标准。
2. 只读任务相关实现与测试；需要历史原因时再检索 `PROJECT_LOG.md`。
3. 修改业务代码时同时补对应测试。
4. PPTX 路径必须暂存、验证、原子替换，不直接覆盖源模板。
5. 运行全量质量门；更新 `PROJECT_LOG.md`；检查 `git status` 后提交。
