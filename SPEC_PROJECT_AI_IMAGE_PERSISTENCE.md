# Spec: 项目级AI候选图绑定与持久化

## Goal

AI生成的候选图必须归属于当前KY PPT项目。保存项目后，重新打开项目能够恢复无CAD方案、已采用效果图以及每个目标的候选批次历史；不同项目即使结构和目标哈希相同，也不能共用或串入彼此的候选记录。

## Scope

In scope:

- 为 `PptProject` 增加稳定项目ID。
- 在项目JSON中保存无CAD `EquipmentScene` 和项目候选批次索引。
- AI候选文件按项目ID、目标哈希和批次ID分目录保存。
- AI效果图窗口按当前目标读取本项目的历史批次并允许重新预览、人工采用。
- 新建、保存和打开项目时同步无CAD工作区状态。
- schema 1～4项目自动迁移到新schema并生成项目ID。

Out of scope:

- 不把PNG二进制嵌入项目JSON。
- 不自动把旧版未绑定的 `output/ai_candidates/<hash>/...` 猜测归入当前项目。
- 不上传云端、不建立多人共享数据库。
- 不删除任何已有候选目录。

## Inputs And Outputs

Inputs:

- 当前 `PptProject.project_id`。
- 当前 `EquipmentScene`。
- Provider生成的 `OpenAIImageBatch`、目标ID/类型/哈希及候选图片路径。

Outputs:

- `output/ai_candidates/<projectId>/<targetHash>/<batchId>/` 候选文件目录。
- 项目JSON中的 `project_id`、`no_cad_scene` 和 `ai_image_batches`。
- AI窗口当前目标对应的项目历史批次列表。

## Behavior

- 新项目：创建一次稳定的32位项目ID；后续另存和重复打开不改变ID。
- 生成候选：Provider输出根目录必须包含当前项目ID；成功批次立即进入当前工作区批次索引，即使尚未采用也保留。
- 采用候选：采用信息继续写入Scene目标及批次 `accepted.json`；项目保存后两者一起恢复。
- 保存项目：从无CAD编辑器收集最新Scene和批次记录，项目JSON在同目录临时文件写完后原子替换。已经有项目文件的工作区在候选批次变化后立即自动保存；尚未首次保存的新项目在界面中提示用户保存。
- 打开项目：恢复Scene、已采用图和候选批次；AI窗口只显示当前项目且目标ID/目标哈希匹配的历史批次。
- 结构变化：旧目标哈希的历史批次仍保留在项目记录中用于追踪，但不能作为当前结构的可采用候选。
- 项目隔离：批次记录的 `projectId` 必须与项目ID一致；不一致的schema-v5项目拒绝加载。
- 旧项目：schema 1～4缺少这些字段时生成新项目ID，Scene和候选历史为空；保存后写为schema 5。

## Risk

- 用户手工移动或删除候选PNG后，历史记录仍在但界面必须标明文件不可用，不能采用。
- 项目JSON保存的是文件路径而非图片二进制；整个 `output` 目录被删除后无法仅凭JSON恢复图片。
- 旧版无项目ID候选无法可靠判断归属，因此不自动迁移。

## Acceptance Tests

- 新建两个项目，即使目标哈希相同，其候选输出根目录也包含不同项目ID。
- 保存并重开项目后，无CAD节点、已采用图片和候选批次记录一致。
- AI窗口选择目标后能列出该项目中目标ID和目标哈希均匹配的历史批次，并预览候选图。
- 结构变化后的旧哈希批次不进入当前可采用历史列表，但仍保留在项目JSON。
- schema 1～4项目能加载并在保存后升级为schema 5。
- 批次 `projectId` 与项目ID不一致时拒绝加载。
- 全量单元/界面测试与Python编译检查通过。

## Implementation Notes

- `PptProject`是项目持久化权威；`NoCadSchemeEditor`在运行时拥有Scene编辑状态，通过一个工作区数据事件与主窗口同步。
- 项目JSON只保存批次摘要和候选路径；Provider原始 `generation.json` 与 `accepted.json` 继续作为详细追踪凭据。
- 历史候选恢复使用现有 `OpenAIImageBatch` 数据结构，不建立第二套候选模型。
