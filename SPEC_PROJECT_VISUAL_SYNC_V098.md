# Spec: v0.9.8 项目级设备图片与 PPT 一键同步

## Goal

在当前 KY PPT 项目内，把无 CAD 方案中的整机结构、设备模块、人工确认图片和自定义信息可靠绑定；图片齐全时一次点击同步到正式设备方案和 PPT 模块。未使用 AI 时，用户可以为整机或任一模块直接导入人工确认图。

## Scope

In scope:

- `project_id` 是项目技术绑定键；项目名称作为可见核对信息并由 `PptProject.project_name` 统一维护。
- 无 CAD 工作区的方案名称只读显示当前项目名称，不允许形成第二个独立名称。
- 整机和每个模块视觉目标都支持导入人工确认图片；人工图与 AI 采用图使用同一目标 ID、目标哈希和 Scene 字段。
- 同步事件携带项目 ID、项目名称和 Scene；与当前项目不一致时不写入任何正式状态。
- 所有整机/启用模块图片存在时，一次完成 `EquipmentScene → EquipmentScheme → PPT模块`。
- 图片不齐时只同步到正式设备方案，不改写 PPT 页面；界面自动进入设备方案，继续补图和编辑名称、类型、工位、功能、动作、说明与页面版式。
- 正式设备方案手工导入图片时记录“人工导入”来源和项目信息。

Out of scope:

- 不按项目名称单独查找或合并其它项目；同名项目仍由不同 `project_id` 隔离。
- 不自动把“模块参考图”当作正式采用图。
- 不在缺图时使用模板样图或生成部分设备模块页面。
- 不自动判断人工图片的机械可行性，图片仍需工程师确认。

## Inputs And Outputs

Inputs:

- 当前 `PptProject.project_id`、`project_name` 和模板 manifest。
- 当前 `EquipmentScene`、整机目标和模块目标。
- AI 人工采用图或用户手工导入的人工确认图。

Outputs:

- 项目绑定的 `EquipmentScheme` 整机图、模块图、结构、提示词和可编辑信息。
- 图片齐全时更新 `equipment_overview` 和 `equipment_module` PPT 页面实例。
- 图片缺失时返回明确的缺失目标名称，保留原 PPT 页面不变。

## Behavior

- 加载/新建项目时，无 CAD Scene 的 `projectName` 自动设为当前项目名称。
- 用户修改主界面项目名称并结束编辑时，同步更新 Scene；由现有目标哈希规则处理旧图失效。
- 人工导图必须是存在的图片文件，并记录 `source=manual-import`、项目 ID、项目名称、目标 ID/类型/哈希和人工确认标记。
- 点击“同步结构与图片到PPT”时先验证项目 ID 和名称，再校验 Scene 逻辑与图片目标。
- 整机图也属于完整一键同步条件；任一图片缺失或路径失效时，不调用 PPT materialize。
- 正式设备方案中人工创建的启用模块也必须有有效图片，否则同样不生成 PPT 半成品。
- 自动导入模块按 Scene 节点稳定 ID 更新；手工模块保留。

## Risk

- Data loss：项目身份校验和完整图片校验必须发生在 PPT 页面改写前；模板仍由现有原子渲染保护。
- Stale image：项目名称、结构或顺序变化可能改变目标哈希，旧图按既有规则失效。
- Duplicate names：名称不作为唯一键，避免同名项目串图。
- Compatibility：不增加项目 schema 字段，旧 schema-v5 项目继续读取。

## Acceptance Tests

- 新项目加载后，Scene 名称等于 `PptProject.project_name` 且界面只读显示。
- 项目 ID 或名称不匹配时，同步拒绝且正式设备方案不变。
- 整机和每个模块人工导图后，Scene 保存正确目标哈希和人工来源。
- 所有目标图片齐全时，一次同步后设备总览和每个设备模块 PPT 图片 Slot 均为对应确认图。
- 缺少任一目标图时，正式设备方案获得结构和已有图片，但 PPT 模块页面保持同步前状态。
- 正式设备方案可手工导入/替换整机及模块图，并继续编辑模块信息。
- 相关测试、全量质量门和真实 PPTX ZIP/页数/模板哈希验证通过。

## Implementation Notes

- 组合应用服务放在 `scheme_application.py`，UI 只提交项目绑定载荷并展示结果。
- 人工图片继续调用 `NoCadSchemeService.bind_accepted_image`，不建立第二套图片字段。
- PPT 页面仍由 `materialize_equipment_scheme` 和既有 Renderer 生成。
