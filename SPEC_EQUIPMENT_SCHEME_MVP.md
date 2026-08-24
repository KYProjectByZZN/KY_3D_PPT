# Spec: 设备流程与设备功能模块 MVP

> 状态：2026-08-23 用户确认，0.7.0 MVP 已实现并完成自动化与 Microsoft PowerPoint 验收。

## Goal

把工程师或 AI 已设计并经人工确认的设备方案，结构化保存为“流程节点”和“设备功能模块”，再稳定写入现有 NAT6704 技术方案模板：检测流程页可按容量扩页，设备总览页显示整机方案，设备模块页按实体模块数量动态生成。

## Scope

In scope:

- 项目文件保存设备方案概览、流程节点、设备功能模块及二者关联。
- 流程节点支持新增、删除、排序和编辑名称、类型、工位、动作、节拍、输出及关联模块。
- 设备功能模块支持新增、删除、排序和编辑名称、类型、功能、动作、图片、说明及页面版式。
- 删除仍被流程引用的设备模块时必须先提示，确认后清空关联。
- 结构化流程同步到 `inspection_flow` PPT 章节；页面容量来自模板配置，NAT6704 主流程当前为 8 个节点一页，其余文本位置属于辅助和结果分支。
- 整机说明和整机图同步到 `equipment_overview` PPT 章节。
- 每个启用的设备功能模块生成 1 张 `equipment_module` 页面；可选择模板第 6、7、8、9 页版式。
- 导出的 PPTX 保持可编辑，不修改原始模板，并通过 Office ZIP 结构检查。
- 旧 schema v1/v2 项目可读取；保存后升级到 schema v3。

Out of scope:

- Visio/Office 级自由拖拽流程画布。
- 自动识别任意 CAD、截图或文字并直接形成最终方案。
- 自动生成新的 PPT 版式或自动修改母版。
- 多层任意拓扑、并行泳道和复杂回路；第一版保留主序列及 OK/NG/返工等输出语义。
- AI Provider/API 接入；本轮先完成无 AI 也可工作的确定性链路。

## Inputs And Outputs

Inputs:

- UI 人工录入的设备方案概览、流程节点和设备功能模块。
- 整机图和各设备模块方案图。
- 当前 PPT 模板及人工配置 manifest。

Outputs:

- schema v3 `*.kyppt.json` / `*.pptproj.json` 项目文件。
- 更新后的项目模块/页面实例。
- 可由 Microsoft PowerPoint/WPS 继续编辑的 `.pptx`。

## Behavior

- 第一次打开旧项目时，从已有 `flow_step_01`～`flow_step_13` 非空值初始化流程节点一次；用户以后删除全部节点时不自动重建。
- 流程顺序等于节点列表顺序；步骤编号为派生数据，不写死。
- 每个流程页清空未使用的流程 Slot，避免继承模板或项目公共旧文字。
- 当前模板每页最多 8 个主流程节点；超过容量时复制检测流程页继续生成。
- 流程节点可关联一个设备功能模块；设备功能模块可被多个节点引用。
- 没有设备功能模块时，同步流程不会擅自删除原设备模块页面。
- 有设备功能模块时，`equipment_module` 章节按启用模块重建，一模块一页。
- 启用的设备功能模块必须提供存在的图片文件；缺图时阻止同步，避免模板样图被误认为正式方案图。
- 整机图可为空；为空时不覆盖当前设备总览图，界面明确提示仍需人工审核。
- 模板没有所需模块、页面模板或 Slot 时，给出可理解错误，不生成半成品。

## Risk

- Data loss：同步只重建 `inspection_flow` 和有结构化设备模块时的 `equipment_module` 页面；执行前项目仍可另存，原 PPT 模板不修改。
- Compatibility：页面复制继续走现有 relationship-safe Renderer；新增 Slot 只绑定已核对的 Shape ID。
- Layout：文字长度受 manifest `max_chars` 限制；复杂流程超过一页自动分块。
- Content：软件只保证结构化生成，不对机构可行性、节拍和检测性能作自动承诺，必须由工程师确认。

## Acceptance Tests

- Given 15 个流程节点，when 同步方案，then 生成 2 张检测流程页，前 8 个和后 7 个顺序正确且剩余 Slot 为空。
- Given 2 个设备功能模块及有效图片，when 同步方案，then 设备模块章节生成 2 页，并写入各自标题、说明、图片和关联流程。
- Given 设备模块仍被流程引用，when 删除，then 默认拒绝；人工确认清除关联后可删除。
- Given schema v2 项目，when 打开并保存，then 可读取且保存为 schema v3。
- UI 可看到“设备方案”编辑区，默认项目能从现有流程字段初始化节点。
- 完整单元测试和 Python 编译通过；生成 PPTX 有 ZIP 签名、必要包成员和正确页数。

## Implementation Notes

- 数据模型放在 `ppt_generator/project.py`，业务操作放在新的 `ppt_generator/scheme_service.py`，不依赖 PySide6。
- UI 放在新的 `ppt_generator/ui/scheme_editor.py`，嵌入现有“方案模块”页签。
- `templates/NAT6704_v2.template.json` 增加流程容量、设备模块页面蓝图和第 6～9 页 Slot。
- 继续使用现有 `ProjectModule` / `ProjectSlide` / `render_project()`，不新建第二套 PPT 渲染器。
