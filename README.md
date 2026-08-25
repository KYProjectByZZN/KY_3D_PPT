# KY PPT Generator

一个本地、轻量、可扩展的 PowerPoint 生成项目。

当前版本：0.9.7。已经提供 PySide6 桌面工作台、结构化模块/页面编辑、设备流程与实体设备模块设计、Excel 动态扩页、光学 FAR 一键生成检测效果、当前页只读预览、项目级可编辑顶部导航、独立的自动方案 v2，以及“无CAD方案实验室”。实验室把一个方案拆成“整机 + 各功能模块”视觉目标，每个目标独立绑定人工结构、确定性提示词、控制图、采用图片和来源记录；模块增删或排序时，这套绑定与PPT页面按同一模块ID联动，过期采用图会自动失效。“模块效果总览”使用大尺寸工业分区卡片一次审核整机和各模块；“AI设备方案效果图”窗口内可直接选择整机或模块、预览已有采用图和候选图并打开大图查看。候选图按项目ID隔离保存，Scene、批次历史和采用来源随项目恢复；已保存项目的新批次会自动写入项目文件。默认通过本机 Codex 的 ChatGPT 登录生成候选图，OpenAI图片API仅作为单独计费备用路径。

## 目录

```text
PPT_Generator/
├─ ppt_generator/       PPT构建、项目模型、资料解析和UI源码
├─ templates/           PPTX模板及人工Slot配置
├─ examples/            示例渲染数据
├─ assets/              图片、Logo等素材
├─ output/              人工导出结果，不纳入Git
├─ projects/            可选项目导出目录，不纳入Git
├─ tests/               自动化测试
├─ generate_ppt.py      基础命令行入口
├─ render_template.py   模板渲染命令行入口
├─ run_desktop.py       PySide6桌面入口
├─ 启动PPT软件.bat       Windows双击启动入口
└─ SPEC.md              当前规格与边界
```

## 安装

当前电脑已经安装 `python-pptx 1.0.2`。新环境可执行：

```powershell
python -m pip install -r requirements.txt
```

需要复现本次 Windows 验证环境时，使用 `python -m pip install -r requirements-tested.txt`；它固定 v0.9.7 质量门实际使用的直接依赖版本。

## 生成示例

```powershell
python generate_ppt.py `
  --title "项目汇报" `
  --subtitle "KY Project" `
  --bullet "项目背景" `
  --bullet "核心方案" `
  --bullet "下一步计划" `
  --output ".\output\项目汇报.pptx"
```

如果目标文件已经存在，命令会拒绝覆盖；明确需要替换时增加 `--overwrite`。

## 启动桌面软件

双击 `启动PPT软件.bat`，或执行：

```powershell
python run_desktop.py
```

启动后默认加载 NAT6704 模板和测试数据。界面包含：

- 项目内容：编辑模板中的文字、表格和图片字段。
- 方案模块：包含“PPT模块”和“设备方案”两个工作区；PPT模块管理章节和页面，设备方案管理流程节点与实体设备模块。
- 设备流程：新增、删除、排序并编辑节点名称、类型、工位、动作、节拍、输出和关联设备模块；NAT6704 主流程每页8个节点，超过后自动扩页。
- 设备功能模块：录入模块名称、功能、动作、方案图、备注和页面版式，一模块生成一页；模板旧机械标注在生成时自动清除。
- 页面模板：模块可以登记当前 PPT 模板中的其他页面，设置默认新增页面模板。
- 结构化页面：选择页面后，按文字、图片、表格和数据来源编辑模板 Slot。
- Excel 动态模块：把 Excel 列映射到模块字段，一行生成一份当前模块结构；重新应用只替换该绑定生成的旧副本。
- Excel映射：预览工作表、识别表头、框选单元格/区域并映射到PPT文字或表格字段，规则可保存复用。
- 光学 FAR：读取统一格式 FAR 的检测项标准、工位、节拍、相机、镜头、光源和内嵌检测图，一键更新检测效果、产品检测项和设备参数模块。
- Word / 通用解析：提取资料文字，将选中内容填入PPT字段。
- 图片素材：批量导入、人工分类并分配到图片 Slot。
- 项目文件：保存为 `*.kyppt.json`，后续继续编辑。
- 当前页展示：在“方案模块”选择具体页面后，最右侧自动显示按当前数据生成的实际页面；优先调用 Microsoft PowerPoint，不可用时尝试 WPS 演示。
- 自动方案 v2：保存客户原始需求和固定分类配置，提供需求 CRUD/复制/归档/版本快照、本地保守解析建议、可解释历史方案检索、候选工艺与工位、DrawingSpecification 和二维方案图 Prompt；所有解析建议和候选方案均需人工确认。
- 无CAD方案实验室：默认进入逻辑方案编辑器，使用16种内置上料、输送、定位、检测、分选和下料模块组成单条主线；支持模块添加/替换/删除/拖动排序/锁定、参考图登记、自动排布和逻辑门禁。整机与每个模块都是独立视觉目标，可分别编辑结构JSON与补充要求、查看最终提示词、生成并采用图片；完成后通过Application服务单向同步到正式设备方案。内部第二页保留DrawingSpecification提示词/SVG实验。
- 模块效果总览：在无CAD方案顶部打开大尺寸审核窗口，按当前模块顺序显示整机和全部模块；缺图保持独立占位，已采用图可点击打开原始分辨率并进行适应窗口、100%、放大和缩小查看。

自动方案 v2、项目候选图、FAR 素材、预览缓存和日志默认保存在 `%LOCALAPPDATA%\KY_Project\PPT_Generator`，不与源码或导出文件混放。旧版 `output/auto_solution_v2_store.json` 首次迁移时只复制、不删除。内置三条历史摘要明确标记为“演示数据”，只用于验证首版检索链路，不代表公司真实项目；未配置在线 AI 和图像 Provider 时，软件不会伪装成已经调用 API。

无CAD方案实验室与自动方案 v2 的需求/候选仓库暂不联动，也不回写 `CandidateSolution`。无CAD Scene 通过门禁后可以由用户显式同步到 `PptProject.equipment_scheme`，同步内容包括整机/模块结构、提示词、图片和来源记录；同步结构本身不生成PPT。内置模块只是功能核验目录，后续需用公司真实模块和规则逐项替换。

Codex Pro 生图操作顺序：进入“无CAD方案实验室” → 完成主线逻辑 → 在“结构 / 提示词绑定”中依次核对整机和各模块结构 → 点击“打开 Codex Pro AI效果图生成” → 在AI窗口的“本次生成目标”选择整机或模块 → 预览已有采用图或生成候选图 → 人工核验和采用 → 可继续切换其他目标 → 关闭窗口统一回写 → 点击“同步结构到正式设备方案” → 在“方案模块 / 设备方案”检查后同步到PPT。软件不读取账号密码，也不把Codex登录令牌写入项目；若主动切换到“OpenAI API（单独计费）”，才需要API Key和API余额。

当前页展示是只读预览，不是自由编辑画布。0.5.2会先显示正确的模板页并用遮罩标明“实时内容加载中”，再替换为当前数据的最终画面。模板页首次访问时按需生成并持久缓存；实时页只生成当前一页、复用后台Office进程，同时预加载前后相邻页。同一内容再次打开直接走内存缓存。Office 首次启动或不可用时，右侧会显示原因，不影响正式 PPTX 生成。

没有真实业务样例时，可使用：

- `examples/excel_mapping_demo.xlsx`：通用演示工作簿。
- `examples/excel_mapping_demo.json`：对应映射规则。
- `output/NAT6704_v2_Excel映射验证.pptx`：映射后的验证结果。

界面操作顺序：选择Excel → 选择工作表 → 框选区域 → 添加选区映射 → 选择PPT目标 → 应用到项目 → 生成PPT。

光学 FAR 操作顺序：进入“Excel / Word”→“Excel 映射” → 选择 `NAT6801FAR(8.5).xlsx` → 点击“一键生成检测效果” → 在“方案模块”审核6张检测效果页、检测项和设备参数 → 生成 PPT。

NAT6801 实际规则：有对应缺陷图的检测项各生成1页；同一工位没有对应缺陷图的检测项合并为1张OK页。工位1只放1张OK样件图，括号列出关联的指纹、镀层不良、生锈、磨伤，不把OK图表述为缺陷图；工位2四个缺陷各1页，工位3翘曲1页。检测效果共6页，完整方案24页。

模块化操作顺序：选择“方案模块” → 选择模块或页面 → 增删/复制/调整结构 → 编辑页面字段 → 可选“Excel生成” → 确认记录数和预计页数 → 生成PPT。

设备方案操作顺序：选择“方案模块” → “设备方案” → 填写整机方案 → 编辑流程节点 → 建立设备功能模块并选择各自方案图 → 关联流程与模块 → 点击“同步方案到PPT模块” → 在“PPT模块”审核页面 → 生成PPT。

模块功能演示文件：

- `examples/module_repeat_demo.xlsx`：3条设备模块数据。
- `output/NAT6704_v2_模块结构化验证.pptx`：复制设备总览模块后的24页验证文件。
- `output/NAT6704_v2_Excel模块重复验证.pptx`：Excel 3行动态替换1页源模块后生成的25页验证文件。
- `output/ui_module_editor_v040_windows.png`：Windows原生模块编辑界面截图。
- `output/current_page_preview_v050.png`：Microsoft PowerPoint 实际导出的单页 PNG。
- `output/ui_current_page_preview_v050_windows.png`：包含最右侧当前页展示区的 Windows 原生界面截图。
- `output/ui_current_page_preview_v051_windows.png`：优化后切页并命中内存缓存的界面截图。
- `output/ui_two_level_loading_v052_windows.png`：模板页即时画面和实时内容加载遮罩。
- `output/ui_two_level_preview_v052_windows.png`：实时页完成且相邻页预加载后的界面。
- `output/ui_optical_far_one_click_v060_windows.png`：光学 FAR 一键生成功能入口。
- `output/方案图实验室_结构示意图.svg`：三工位确定性结构示意审核样本。
- `output/方案图实验室_PromptRecipe.json`：对应固定参数、提示词和核验清单。
- `output/ui_方案图实验室.png`：独立实验功能界面审核图。
- `output/无CAD设备逻辑方案.svg`：七模块单主线、逻辑通过的无CAD结构示意。
- `output/无CAD设备逻辑方案.scene.json`：对应Scene、连接、逻辑结果和AI生成约束。
- `output/ui_无CAD设备逻辑方案_通过.png`：模块库、产品主线、属性和逻辑通过界面。
- `output/ui_无CAD设备逻辑方案_阻断.png`：删除检测模块后的阻断门禁界面。
- `output/ui_module_visual_overview_v094.png`：大尺寸三列模块效果总览布局审核图（重复使用一张旧候选图验证界面，不代表模块最终图片）。
- `output/ui_ai_effect_target_selector_v095.png`：AI效果图窗口内目标选择与已有采用图预览布局审核图（临时复用旧候选图，不代表模块最终图片）。
- `output/NAT6801_FAR_OneClick_v0.6.3_Final.pptx`：NAT6801 FAR 的24页真实生成结果。
- `output/NAT6801_FAR_OneClick_v0.6.3_Final.pptproj.json`：对应可继续编辑的项目文件。
- `output/设备方案流程模块_v0.7.0_验收版.pptx`：8步流程、4个关联设备模块的PowerPoint实际渲染验收文件。
- `output/设备方案流程模块_v0.7.0_验收版.pptproj.json`：对应schema v3结构化项目文件。
- `output/scheme_flow_v070_acceptance.png`：Microsoft PowerPoint实际导出的检测流程页。
- `output/scheme_device_module_v070_acceptance.png`：Microsoft PowerPoint实际导出的设备模块页。

## 按模板配置生成

```powershell
python render_template.py `
  --template ".\templates\冲压筒形壳体检测方案NAT6704_v2.pptx" `
  --manifest ".\templates\NAT6704_v2.template.json" `
  --data ".\examples\NAT6704_v2_test_data.json" `
  --output ".\output\NAT6704_v2_测试.pptx"
```

模块名称、页面归属和可替换位置都保存在 JSON 配置中，后续软件界面可以修改，不写死在渲染器里。相对图片路径以数据 JSON 所在目录为基准。

## 验证

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\quality_gate.ps1
```
