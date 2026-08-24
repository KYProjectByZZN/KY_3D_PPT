# Spec: PPT 模块化生成与编辑 MVP

> 状态：2026-08-23 用户已确认，0.4.0 MVP 已实现；等待实际操作和 PowerPoint/WPS 双端人工验收。

## Implementation Result

- 已实现 schema v2 项目模型、schema v1 自动迁移、模块/页面稳定 UUID 和独立数据副本。
- 已实现模块树、模块/页面增删复制排序、模块改名/类型/启用、页面标题/小标题和结构化 Slot 编辑。
- 已实现模块页面模板登记、默认新增页面模板、当前模块实际结构复制。
- 已实现 Excel 列到模块字段映射、一行一模块副本、重新应用替换旧副本和预计页数确认。
- 已实现统一 SlideContext：实际页数、内容页码、模块序号、模块内页码、标题和小标题均可写入系统 Slot。
- 已实现项目实例 Renderer，复制文字、图片、表格、普通图形、线条、Notes、超链接和 Tags 关系；旧 `render_template()` 入口不变。
- 自动测试、真实 NAT6704 24页模块复制、25页 Excel 重复生成和 Windows 原生界面截图均通过。
- 尚待人工验收：Microsoft PowerPoint/WPS 无修复提示、视觉一致性和另存编辑。

## Goal

把当前“固定模板模块勾选/排序”升级为真正的项目模块编辑器：模块和页面可增删、改名、排序、复制；模块内部按页面结构化管理标题、小标题、对应图片、正文、表格和数据字段；模块可绑定 Excel 行数据并按数据数量重复生成页面；导出文件保持原模板布局且可在 PowerPoint/WPS 中继续编辑。

## 现状与差距

当前已经具备：

- 模板配置中定义模块、模板页和文字/表格/图片 Slot。
- 项目保存、Excel 固定区域映射、图片素材和 PPTX 渲染。
- 固定模块启用/停用和顺序调整。

当前缺少：

- 项目级 `Module`、`Slide` 实例；现在只有模板模块 key 列表。
- 添加、删除、改名、复制模块和页面。
- 同一模板模块的多个独立副本及各自数据。
- Excel 表格行到模块变量的绑定，以及按行数动态扩页。
- 页面级变量编辑区和模块树。
- Renderer 对同一模板页的安全复制。

当前 NAT6704 模板共 23 页，主要包含文字、图片、表格、线条和普通图形，没有图表、宏或嵌入对象，适合先验证模块/页面复制。模板含 Notes、超链接和 Tags，复制时需要保留相关关系并做 PPTX ZIP 验证。

## Scope

In scope:

- 左侧模块树：展开模块查看内部页面和实时页数。
- 模块：从现有模板模块创建、删除、改名、复制、启用/停用、上下移动。
- 每个模块拥有独立的页面模板库、默认页面序列和默认新增页面模板。
- 页面：从模块页面模板库创建、删除、复制、改名、上下移动，并编辑页面标题和小标题。
- 页面增删、复制、重排后，统一重算总页数、内容页码、模块序号、模块内页码和模块小标题。
- 模块类型：`fixed`、`repeat`、`dataDriven`。
- 页面编辑：编辑该页面已配置的文字、表格、图片 Slot；显示变量名，例如 `{{station_name}}`。
- 模块/页面副本使用新的 UUID；数据互相独立；模板文件保持只读。
- Excel 重复绑定：选择工作表、表头、数据区域、目标模块和字段映射。
- Excel 每一行生成一个模块副本；每个副本包含该模板模块的全部页面。
- Excel 重新应用时只替换该绑定上次生成的模块副本，不影响手工模块。
- 保存/打开 schema v2 项目，并兼容读取当前 schema v1 项目。
- 导出可编辑 PPTX；保留原布局、图片位置、文字样式和表格结构。

Out of scope:

- Office 级自由画布、拖动图形、动画编辑、母版编辑。
- 凭空设计新页面；新增模块/页面必须选择当前模板中的蓝图。
- AI 自动设计、AI 排版、多人协作、云端权限。
- 第一版自动识别任意未配置模板变量。
- Word、数据库和 API 重复数据源；数据结构预留接口，暂不接入。
- 图表、SmartArt、视频、OLE、宏页面的通用复制承诺；遇到不支持对象应阻止导出并明确提示。

## 关键实现决定

1. **模板与项目分离**：模板配置只描述可用模块、模板页和 Slot；项目文件保存模块实例、页面实例、数据和绑定，不修改模板 PPTX。
2. **实例引用蓝图**：复制模块/页面时只创建新的项目实例和 UUID，记录 `template_module_key`、`page_template_key`；页面模板再指向实际来源页，导出时复制模板页。
3. **三级取值**：页面有效数据按“项目全局值 → 模块行数据 → 页面人工覆盖”合并，越靠后优先级越高。
4. **变量绑定仍以 Slot 配置为准**：界面用 `{{key}}` 展示变量，但 Renderer 继续通过模板页码和 Shape ID 精确定位，避免全文替换误伤格式。
5. **数据驱动采用显式应用**：Excel 变化后用户点击“重新生成模块”，软件显示将生成的记录数，再替换该绑定的旧副本，避免文件一变化就静默覆盖人工内容。
6. **保留旧 Renderer**：现有 `render_template()` 和命令行行为不变，新增项目实例渲染入口，降低回归风险。
7. **增加页面不等于盲目复制当前页**：模块保存页面模板库、默认页面序列和默认新增模板；新增时可直接使用默认模板，也可从模板库选择其他版式。
8. **页码和小标题是派生数据**：不把页码硬编码到项目页面中，每次结构变化后由统一的 SlidePlan 重新计算，再写入模板配置指定的系统 Slot。

## Data Structure

项目文件升级为 schema v2，核心关系如下：

```text
PptProject
├─ global_values
├─ modules: ProjectModule[]
│  ├─ id
│  ├─ template_module_key
│  ├─ name
│  ├─ module_type: fixed | repeat | dataDriven
│  ├─ enabled
│  ├─ module_values
│  ├─ page_templates: PageTemplateRef[]
│  ├─ default_sequence: page_template_key[]
│  ├─ default_add_template
│  ├─ generated_by_binding_id (可空)
│  └─ slides: ProjectSlide[]
│     ├─ id
│     ├─ page_template_key
│     ├─ title / subtitle
│     └─ overrides
└─ module_bindings: ExcelModuleBinding[]
   ├─ id
   ├─ source_path / sheet / header_row / data_range
   ├─ template_module_key
   ├─ field_map: Excel列名 → Slot key
   └─ module_name_field (可空)
```

模板配置继续兼容 schema v1，只增加可选字段，不要求立即重做 NAT6704 配置。模板模块蓝图提供初始页面模板库、默认页面序列和默认新增模板；创建项目模块时复制这些定义，项目内可以再自定义：

```json
{
  "key": "optical_station",
  "name": "光学工位",
  "type": "dataDriven",
  "slides": [6, 7],
  "page_templates": [
    {
      "key": "station_plan",
      "name": "光学工位方案",
      "source_slide": 6,
      "role": "content"
    },
    {
      "key": "station_parameters",
      "name": "光学配置参数",
      "source_slide": 7,
      "role": "parameters"
    }
  ],
  "default_sequence": ["station_plan", "station_parameters"],
  "default_add_template": "station_plan"
}
```

未填写 `type` 时默认 `fixed`。旧配置没有 `page_templates` 时，每一个 `slides` 页码自动成为一个页面模板，原页序列自动成为 `default_sequence`。如果没有明确配置 `default_add_template`，新增页面时必须让用户选择，避免误把封面页、目录页等特殊页面作为普通内容页重复。

## 页面模板、页数与标题方案

### 1. 模块页面模板库

每个模块有自己的 `PageTemplate` 列表。页面模板保存：

- 稳定的模板 key 和显示名称。
- 来源 PPTX 和来源页；第一版来源限制为当前项目模板中的页面。
- 页面角色：`cover`、`section`、`content`、`parameters`、`gallery`、`ending`。
- 默认页面标题、小标题。
- 该版式可编辑的普通 Slot 和系统 Slot。

“自定义页面模板”第一版指：用户从当前 PPT 模板的任意已有页面中选择一页，登记到当前模块的页面模板库并命名。直接从另一个外部 PPTX 导入页面暂不放在第一版，因为跨文件母版、主题、字体和关系复制风险明显更高；需要时先在 PowerPoint 中把页面加入正式模板，再在软件中登记。

### 2. 默认页面序列与默认新增模板

- `default_sequence`：新建模块时自动创建的初始页面组合。例如光学工位默认是“工位方案页 + 配置参数页”。
- `default_add_template`：人工点击“增加一页”时默认选中的单页版式，适合连续添加相同内容页。
- 修改默认模板只影响以后新增的页面，不改变已经存在的页面。
- 页面模板从库中删除前必须检查引用；仍被项目页面使用时禁止删除，先要求重新指定模板。
- 手工复制模块和 Excel 动态扩展都复制“当前源模块的实际页面序列”，因此用户后来增加的自定义页也会一起生成；默认页面序列只负责新建模块的初始状态。

### 3. 增加、复制和删除页面

增加页面：

1. 选择所属模块和插入位置。
2. 弹窗默认选中 `default_add_template`；也可以选择该模块的其他页面模板。
3. 输入页面标题/小标题，或接受页面模板默认值。
4. 生成新的页面 UUID，插入后立即重算结构。

复制页面：

- 保留原页面模板、数据、标题和小标题，但生成新的 UUID。
- 插入到原页面后方；同名时界面建议增加“2、3……”后缀，用户可改名。

删除页面：

- 只删除项目页面实例和该页人工覆盖数据，不删除页面模板。
- 删除模块最后一页时，提示“删除整个模块”或取消，禁止保留空模块。
- 删除后统一重算后续所有页面编号和模块统计。

### 4. 统一结构变量

`build_slide_instances()` 在界面预览和最终导出前生成同一份结构上下文：

| 系统变量 | 含义 |
|---|---|
| `{{page_number}}` | 当前参与编号的内容页页码 |
| `{{total_pages}}` | 参与编号的内容页总数 |
| `{{physical_page_number}}` | PPTX 中的实际页序号，包含封面等 |
| `{{physical_total_pages}}` | PPTX 实际总页数 |
| `{{module_number}}` | 当前启用模块的顺序号 |
| `{{module_count}}` | 当前启用模块总数 |
| `{{module_page_number}}` | 当前页在模块内的顺序号 |
| `{{module_page_count}}` | 当前模块实际页数 |
| `{{module_title}}` | 模块名称 |
| `{{slide_title}}` | 当前页面标题 |
| `{{slide_subtitle}}` | 当前页面小标题 |

默认编号策略：

- 封面和结束页保留在 PPTX 实际页数中，但默认不显示内容页码，也不计入 `total_pages`。
- 其余启用页面从 1 连续编号；删除、增加或移动页面后自动更新。
- 模块序号和模块内页码同样只按当前启用结构计算。
- 页码显示格式（如 `3 / 20`、`03`）由模板配置决定，不在业务代码里写死。

页面模板可以配置如下系统 Slot：

```json
{
  "system_slots": {
    "module_title": 23553,
    "slide_title": 4,
    "slide_subtitle": 7,
    "page_number": 8
  },
  "number_format": "{page_number} / {total_pages}"
}
```

这里的数字是模板 Shape ID。模板没有对应文本框时，软件不会强行在固定坐标新增页码或标题，避免破坏设计；用户可以在模板配置中指定或后续补充。

### 5. 小标题取值优先级

页面小标题按以下优先级取值：

1. 当前页面人工填写的 `subtitle`。
2. Excel 字段映射到 `slide_subtitle` 的值。
3. 页面模板的默认小标题。
4. 都没有时保持模板原文字或留空。

模块名称、页面标题和小标题绑定稳定 UUID/变量，不绑定“第几页”，因此前面插入或删除页面不会导致数据串页。

## 模块内部结构化内容方案

页数只作为模块结构的统计结果。实际编辑对象按以下层级管理：

```text
项目
└─ 模块（光学方案）
   ├─ 页面（整体光学方案）
   │  ├─ 标题
   │  ├─ 小标题
   │  ├─ 技术方案图
   │  ├─ 图片说明
   │  └─ 方案正文
   └─ 页面（相机配置）
      ├─ 工位名称
      ├─ 相机图片
      ├─ 相机型号
      ├─ 相机数量
      └─ 参数表
```

不能把所有页面统一写死成“标题 + 小标题 + 一张图片”。每一个 `PageTemplate` 通过 Slot Schema 声明自己的内容结构：

```json
{
  "key": "station_plan",
  "name": "光学工位方案",
  "source_slide": 6,
  "slots": [
    {
      "key": "station_name",
      "label": "工位名称",
      "kind": "text",
      "role": "title",
      "group": "基本信息",
      "required": true
    },
    {
      "key": "station_image",
      "label": "技术方案图",
      "kind": "image",
      "role": "main_image",
      "group": "图片",
      "asset_category": "技术方案图"
    },
    {
      "key": "inspection_content",
      "label": "检测内容",
      "kind": "text",
      "role": "body",
      "group": "方案内容"
    }
  ]
}
```

Slot 最少支持：

- `text`：标题、小标题、正文、说明、型号等。
- `image`：公司图、产品图、设备图、技术方案图、检测效果图等单张图片。
- `table`：设备参数、检测项目、配置清单。
- `system`：页码、模块标题、模块内页码等由结构计算得到的值。

每个 Slot 还可配置：显示名称、所属分组、内容角色、是否必填、字符限制、图片分类、Excel 字段别名。模板保存结构定义，项目页面只保存实际值和人工覆盖，继续保证模板与内容分离。

界面呈现规则：

- 左侧模块树只显示“模块 → 页面”，避免把几十个字段全部展开造成混乱。
- 选中模块时，右侧显示模块名称、类型、页数、默认页面模板和数据源。
- 选中页面时，右侧按“基本信息 / 文字内容 / 图片 / 表格 / 数据绑定”分组显示该页 Slot。
- 图片 Slot 直接从项目图片库选择，并按配置的图片分类优先筛选。
- 每个字段显示数据来源：手工、Excel、项目公共数据或模板默认值。
- 必填字段未完成时在页面节点显示提示，但不改变模板文件。

数据作用域：

1. 项目公共数据，例如公司名称、项目名称，可供多个模块使用。
2. 模块数据，例如工位名称、相机型号，可供该模块所有页面使用。
3. 页面数据，例如本页小标题、技术方案图，只作用于当前页面。

同名字段按“项目公共数据 → 模块数据 → 页面人工覆盖”取值。模块和页面复制时深拷贝实际数据，随后修改互不影响；数据始终绑定稳定 ID 和 Slot key，不绑定页码或树中的显示顺序。

## UI Structure

“方案模块”页改成三栏：

```text
左侧模块树                    中间当前页面                  右侧属性/数据
├─ 光学方案 · 4页             页面名称与模板来源            模块名称/类型/页数
│  ├─ 整体光学方案            页面结构摘要                  标题/小标题/正文
│  ├─ 相机配置                当前图片和表格信息            对应图片/图片分类
│  ├─ 镜头配置                非Office级结构预览             模板变量/Excel映射
│  └─ 光源配置
└─ AI算法 · 2页
```

按钮按选择对象切换：

- 选择模块：添加模块、删除、改名、复制、上移、下移、管理页面模板、设置默认模板、连接 Excel。
- 选择页面：增加页面、删除、改名、复制、上移、下移；按结构分组编辑标题、小标题、对应图片、正文、表格和变量。
- 所有删除只影响当前项目；原模板不变。

第一版中间区域不是 Office 自由画布。它显示页面名称、模板来源、字段/图片/表格的结构化编辑和可选静态缩略图；任意图形拖动留到后续阶段。

## Core Interfaces

```python
create_project_from_manifest(manifest) -> PptProject
add_module(project, template_module_key, name=None) -> ProjectModule
duplicate_module(project, module_id) -> ProjectModule
remove_module(project, module_id) -> None
move_module(project, module_id, offset) -> None

add_page_template(project, module_id, source_slide_number, name) -> PageTemplate
set_default_page_template(project, module_id, page_template_key) -> None
add_slide(project, module_id, page_template_key=None, position=None) -> ProjectSlide
duplicate_slide(project, module_id, slide_id) -> ProjectSlide
remove_slide(project, module_id, slide_id) -> None
move_slide(project, module_id, slide_id, offset) -> None

read_excel_records(binding) -> list[dict[str, str]]
materialize_excel_modules(project, binding) -> list[ProjectModule]

build_slide_instances(project, manifest) -> list[SlideInstance]
rebuild_structure_context(project, manifest) -> list[SlideContext]
render_project(project, output_path, overwrite=False) -> Path
```

所有模块操作、Excel 重复逻辑和渲染计划都放在 PySide6 之外，可独立单元测试。

## Files To Add Or Modify

新增：

- `ppt_generator/module_service.py`：模块/页面 CRUD、复制、顺序和 Excel 行物化。
- `ppt_generator/ui/module_editor.py`：模块树、页面结构编辑、模块属性和重复绑定界面。
- `tests/test_module_service.py`：模型、复制、排序、删除、Excel 重复测试。
- `tests/test_project_renderer.py`：真实页面复制、独立填值和 PPTX 结构测试。

修改：

- `ppt_generator/project.py`：schema v2 数据类和 v1 迁移。
- `ppt_generator/template_renderer.py`：增加项目实例渲染和安全复制页；保留旧入口。
- `ppt_generator/excel_mapper.py`：复用现有预览，增加表头记录读取和重复字段映射。
- `ppt_generator/ui/main_window.py`：接入新的模块编辑器和生成入口。
- `tests/test_project_and_sources.py`、`tests/test_ui.py`：持久化迁移和界面验收。
- `README.md`、`README-AI.md`、`PROJECT_LOG.md`：操作说明和跟踪记录。

暂不创建新的 `core/`、`adapters/` 等大目录，避免为第一版做空架构。

## Development Order

1. **模型与迁移**：实现 schema v2、从 manifest 初始化项目、v1 项目兼容读取。
   - 验证：模块/页面 UUID 唯一，保存再打开数据一致。
2. **页面模板与结构规则**：模块页面模板库、默认序列、默认新增模板、系统变量和统一编号计算。
   - 验证：模板变更只影响新页面；增删移动后物理页码、内容页码、模块内页码和小标题正确。
3. **模块/页面操作**：增删改排、模块复制、单页复制。
   - 验证：复制后修改数据互不影响，页数实时正确。
4. **实例 Renderer**：按项目树生成 SlideInstance，复制模板页并逐实例替换普通 Slot 和系统 Slot。
   - 验证：复制 2 页模块 6 次得到 12 页；源模板哈希不变；PPTX ZIP 和重开通过。
5. **模块树 UI**：替换当前 QListWidget，接入页面模板、模块/页面操作、标题/小标题和页面字段编辑。
   - 验证：离屏 UI 测试和 Windows 原生截图。
6. **Excel 重复绑定**：表头映射、预览记录数、应用和重新生成；每条数据重复所选源模块当前的实际页面序列。
   - 验证：6 行→12 页、8 行→16 页；重新应用只替换该绑定生成项。
7. **回归与记录**：运行全套测试、编译检查、Office ZIP 检查，更新项目日志。
   - 人工验收：PowerPoint/WPS 打开、编辑、另存，不出现修复提示。

## Behavior And Edge Cases

- 模块至少包含 1 页；删除最后一页时提示删除整个模块或取消。
- 项目至少保留 1 个已启用且含页面的模块才能导出。
- 添加页面时默认使用模块配置的 `default_add_template`；未配置默认值时必须人工选择。
- 页面模板库第一版只能引用当前项目 PPT 模板中的实际页面。
- `default_sequence` 至少包含 1 个页面模板；新建模块先按它初始化，之后允许项目模块独立调整实际页面序列。
- Excel 绑定需要指定一个未由该绑定生成的源模块；重新应用时读取源模块当前页面序列，生成项不能反过来作为源模块，避免递归复制。
- Excel 空行忽略；重复/空表头要求人工处理；缺少映射字段显示警告但不崩溃。
- 重新应用 Excel 前显示“旧副本数量 → 新副本数量”；确认后替换。
- 生成文件已存在时继续要求用户确认；禁止输出覆盖源模板。
- 固定模块默认不允许通过 Excel 扩展；切换为 `dataDriven` 后才能创建重复绑定。
- 模板中没有配置 Slot 的对象仍完整复制，但软件不能编辑其内容。

## Risk

- `python-pptx` 没有公开的复制幻灯片 API，需要使用受控的底层关系复制；这是本功能最大技术风险。
- Notes、图片、超链接和 Tags 必须随页面关系保留；第一阶段用 NAT6704 实测并做 ZIP/关系检查。
- 图表、SmartArt、视频、OLE 和宏的关系图更复杂，第一版不承诺通用复制。
- PowerPoint 与 WPS 视觉兼容无法只靠 Python 判定，最终仍需要人工打开验收。
- 数据驱动重新生成会覆盖该绑定副本中的人工覆盖值；第一版在操作前明确警告，不做复杂的行级差异合并。

## Acceptance Tests

- Given NAT6704 模板，when 初始化项目，then 生成 16 个模块和 23 个页面实例。
- Given 一个 2 页模块，when 复制模块 6 次，then 新模块和页面 ID 均唯一，预计页数增加 12 页。
- Given 两个模块副本，when 修改其中一个页面变量，then 另一个副本数据不变化。
- Given 页面复制/删除/移动，when 查看模块树，then 页面顺序和页数立即更新。
- Given 模块默认序列为方案页和参数页，when 新建模块，then 自动产生这 2 页；人工增加页面时默认选中模块的默认新增模板。
- Given 源模块在默认 2 页基础上增加了自定义第 3 页，when 复制模块或按 Excel 6 行扩展，then 每个副本均为当前 3 页结构，最终生成 18 页。
- Given 页面增删或跨位置移动，when 重建结构，then `page_number`、`total_pages`、`module_page_number`、模块标题和页面小标题全部匹配新结构。
- Given 默认新增模板被更换，when 查看已有页面，then 已有页面保持原模板；之后新增页面使用新默认模板。
- Given 页面模板声明标题、小标题、技术方案图和正文 Slot，when 选中该页，then 编辑区按分组显示这些字段及其数据来源，未声明的字段不凭空出现。
- Given 模块或页面被复制，when 修改副本的标题、图片或表格，then 原对象的结构和值均不变化。
- Given Excel 6 条记录和 2 页模板模块，when 应用绑定，then 输出 12 页且每组变量不同。
- Given Excel 改为 8 条记录，when 重新应用，then 旧绑定副本被替换为 8 组/16 页，手工模块保持不变。
- Generated PPTX has valid ZIP signature, required Office entries and expected slide count; `python-pptx` can reopen it.
- 原模板 SHA-256 在所有操作前后保持不变。
- 当前 17 项回归测试继续通过，新增模块和渲染测试通过。
- 用户在 Microsoft PowerPoint 与 WPS 中打开、编辑和另存验证文件，无修复提示。

## Approval Defaults

若用户回复“可以，按方案做”，视为同时确认：

1. 新模块/新页面从模板蓝图创建，不做空白自由设计。
2. 第一版页面编辑是 Slot/变量编辑，不做 Office 级画布。
3. Excel 重新生成会替换该绑定生成的旧副本，并在操作前提示。
4. 先支持当前 NAT6704 已出现的普通图形、文字、图片、表格、线条、Notes、超链接和 Tags。
5. 自定义页面模板第一版从当前 PPT 模板已有页面登记，不直接导入外部 PPTX 页面。
6. 封面和结束页默认不参与内容页码；模板有配置的系统 Slot 才写入页码、模块标题和小标题。
