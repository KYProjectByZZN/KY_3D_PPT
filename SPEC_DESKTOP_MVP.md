# Spec: 技术方案 PPT 桌面 MVP

> 状态：2026-08-23 已实现，等待用户界面审核。界面参考 `D:\test\KY_Project\ky_dce_projetct` 的顶部操作栏、左右分屏和统一数据模型。

## Goal

提供一个可直接操作的 PySide6 Windows 桌面界面，把现有 NAT6704 模板渲染能力变成可视化工作流，而不是要求用户手写命令或 JSON。

## Scope

In scope:

- 选择 PPTX 模板及其人工配置 JSON。
- 在界面中编辑文字、表格和图片 Slot。
- 查看、启用/停用和调整方案模块顺序，并让选择实际影响输出页。
- 导入 Excel/Word，解析成可复制、可应用到文字 Slot 的内容预览。
- 批量导入图片，人工分类，并分配到图片 Slot。
- 保存和打开本地项目 JSON。
- 选择输出位置并在后台生成可编辑 PPTX。
- 默认加载 NAT6704 模板和明确标记的测试数据，便于立即体验。

Out of scope:

- AI API、自动理解客户资料和自动字段映射。
- PowerPoint 画布级在线编辑和真实幻灯片缩略图渲染。
- 任意模板自动识别、动态新增复杂版式和安装包发布。
- 完整 Excel/Word 业务模板规则；本阶段先提供通用解析预览和人工应用。

## Inputs And Outputs

Inputs:

- PPTX 模板及 `*.template.json` 配置。
- Excel `.xlsx/.xlsm`、Word `.docx`、图片文件和手工输入内容。
- 可选的项目 JSON 或渲染数据 JSON。

Outputs:

- 可恢复编辑状态的 `*.kyppt.json` 项目文件。
- 新生成且可继续编辑的 `.pptx`。
- 界面运行日志和明确的错误提示。

## Behavior

- 启动后显示顶部操作栏、左侧四个工作页签和右侧方案结构预览。
- 模板配置变化后，字段、模块和图片 Slot 自动刷新。
- 文字可直接编辑；表格通过二维编辑器修改；图片通过文件选择或素材分配修改。
- 模块列表支持勾选和上下移动；生成结果只保留已启用模块并按列表顺序排列。
- Excel/Word 解析失败时显示文件和原因，不影响已有项目数据。
- 输出已存在时必须再次确认，默认不覆盖。
- 生成任务在后台线程运行，期间界面保持响应。
- 核心项目模型、资料解析和 PPT 渲染不依赖 PySide6。

## Risk

- 删除或重排模板页依赖 `python-pptx` 的内部 Slide ID 列表，必须用结构测试验证页数、顺序和 ZIP 完整性。
- 35 MB 模板生成需要约 1～2 秒，必须避免阻塞界面。
- 通用 Excel/Word 解析只能提取内容，不能代替后续按真实业务模板建立的字段规则。
- PowerPoint/WPS 的视觉一致性仍需人工打开检查。

## Acceptance Tests

- [x] PySide6 离屏启动成功，主窗口、四个页签、模块列表和默认模板信息可见。
- [x] 默认配置显示 16 个模块和 40 个文字/表格/图片 Slot。
- [x] 修改内容后保存项目，再打开能恢复字段、资料和图片记录。
- [x] 测试 Excel 和 Word 能提取文字供界面预览。
- [x] 图片可以人工分类并分配到图片 Slot。
- [x] 只启用封面、设备参数和结束页后，输出为 3 页且顺序正确。
- [x] 生成输出通过 ZIP、Slide XML 数量和 `python-pptx` 重开检查；原模板哈希不变。
- [x] 13 项单元测试、Python 编译检查和 Windows 原生 UI 截图检查通过。
- [ ] 用户审核真实界面操作、字段命名和布局后确认第一版交互。

## Implementation Notes

- UI 使用 PySide6，不引入 Qt WebEngine；第一版右侧展示方案结构和生成检查信息。
- 参考 DCE 的 Steel Blue 浅色工业风格，但样式和代码保留在本项目中。
- 项目模型放在 `ppt_generator/project.py`，资料解析放在 `ppt_generator/source_parser.py`，UI 放在 `ppt_generator/ui/`。
- 现有 `render_template()` 增加可选模块过滤和排序参数，命令行默认行为保持不变。
