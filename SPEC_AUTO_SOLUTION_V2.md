# Spec：自动方案 v2——需求管理与候选技术方案

> 状态：2026-08-24 已确认开发。需求来源：`templates/自动方案-v2.txt`。本规格在原六阶段试验入口内增量实现，不改动现有 `PptProject`、模板渲染和一键检测效果链路。

## 1. 本轮目标

建立一条可保存、可追踪、可人工确认的首版闭环：

```text
客户原始需求
→ 固定分类配置
→ 需求记录与版本快照
→ 历史方案检索
→ 候选工艺与工位
→ DrawingSpecification
→ 稳定的二维方案图 Prompt
```

本轮不把候选方案写入正式 PPT，不宣称完成机械设计、CAD 或工程审核。

## 2. 模块所有者与低耦合边界

| 模块 | 权威状态 | 输入 | 输出 | 不负责 |
|---|---|---|---|---|
| `requirement_management` | `RequirementRecord` | 原始描述、人工配置、解析建议 | 结构化需求、版本元数据 | 历史检索、方案生成、UI |
| `auto_solution_repository` | 持久化记录 | 需求、快照、历史记录、候选方案 | CRUD 查询结果 | 业务推断、Qt 控件 |
| `solution_generation` | `CandidateSolution` | 已保存需求、历史候选 | 工艺、工位、DrawingSpecification、Prompt | 文件保存、Qt 控件、PPT |
| `auto_solution_application` | 跨模块用例 | 稳定记录 ID、业务命令 | 用例结果 | 直接操作控件 |
| `ui/requirement_management_widget` | 临时表单状态 | Application 服务 | 用户命令、需求 ID 事件 | 直接调用候选方案控件 |
| `ui/candidate_solution_widget` | 临时编辑状态 | Application 服务、需求 ID | 候选方案确认结果 | 修改需求记录 |

跨模块联动只通过 `AutoSolutionApplication` 和稳定 ID；业务模块不导入 PySide6，界面之间不读取彼此内部控件。

## 3. 数据契约

### 3.1 RequirementRecord

正式需求记录包含：

- `id`、`requirementNo`、`version`
- `customerName`、`projectName`、`productName`
- `originalRequirement`：永久保留用户原文，解析过程不得修改
- `structuredRequirement`：固定分类配置
- `status`：`draft | confirmed | archived`
- `createdBy`、`createdTime`、`updatedTime`

固定分类配置包含：

- 产品基本信息：类型、型号、尺寸、材料；客户/项目/产品名称由记录顶层字段统一拥有，避免双向维护
- 产能与节拍：目标节拍、每批数量、日产能、是否连续生产
- 上料方式与说明
- 下料方式与说明
- 多项检测要求：检测项、精度、范围、备注
- 九项产品状态：有油、有水、有粉尘、反光、透明、易划伤、易变形、有毛刺、尖锐边缘；值为 `yes | no | unknown`
- 特殊要求

### 3.2 解析建议

解析器只返回 `RequirementSuggestion`，包含字段路径、当前值、建议值、依据、置信度和来源。规则如下：

1. 解析器同时读取原始描述和当前配置。
2. 不直接写入正式字段。
3. 界面先显示建议，由用户勾选确认。
4. 已有人工值默认禁止覆盖；需要修改时由用户直接编辑正式字段。
5. 无法可靠识别的字段保持 `unknown`，不补造参数。

首版默认使用本地规则解析器，另提供稳定的解析 Provider 接口。在线 AI API 尚未配置，因此本轮不把本地规则结果伪装为大模型结论。

### 3.3 版本快照

已保存记录再次发生有效修改时：

- 记录版本由 `Vn` 增至 `Vn+1`
- 保存修改前和修改后的完整 JSON
- 保存修改时间、操作人和动作

复制需求生成新 ID、新需求编号和 V1，不继承原记录版本号。

### 3.4 历史方案

历史记录只保存检索所需的结构化摘要，不向生成器发送整份 PPT：

- 产品类型/尺寸、检测项、节拍、上下料
- 工艺流程、工位、模块、布局摘要
- 参考图片路径、关键参数、已知问题
- `sourceKind` 明确区分 `user` 与 `demo`

检索为可解释加权匹配，返回相似度及命中原因。没有真实历史数据时允许返回空；内置示例必须标明“演示”，不得冒充公司实际案例。

### 3.5 CandidateSolution

候选方案包含：

- `id`、`requirementId`、`version`
- `historicalReferences`
- `processFlow`
- `stations`：`stationId/name/description/referenceModule/referenceProject`
- `drawingSpecification`
- `drawingPrompt`
- `createdTime`、`createdBy`、`status`

候选页固定展示三部分：历史参考、结构化工艺/工位、DrawingSpecification 与 Prompt；没有历史参考时隐藏第一部分。

## 4. DrawingSpecification 与 Prompt Builder

DrawingSpecification 至少包含：

- `drawingType`、`product`、`overallLayout`、`processFlow`
- `stations`、`motionRelations`、`keyStructures`
- `annotations`、`prohibitedElements`、`referenceImages`

Prompt Builder 必须显式表达：产品位置、上/下料方向、工位相对位置及数量、固定/移动/旋转关系、相机/光源/夹具位置、禁止出现的部件。不得只输出抽象名词列表。

## 5. 界面与操作

### 客户需求页

- 左侧需求记录列表：编号、客户、项目、产品、节拍、创建人、更新时间、状态、方案数
- 右侧详情：原始描述、固定分类配置、检测项表、九项产品状态
- 操作：新建、保存、复制、归档、删除、版本历史、解析需求、应用勾选建议、生成候选方案

### 历史检索页

- 显示当前需求编号
- 支持按当前结构化需求检索
- 表格展示相似度、命中理由、来源类型和已知问题

### 候选方案页

- 显示三个固定区块
- 支持重新生成、人工编辑并保存、确认候选方案
- “生成方案图”保留按钮和接口边界；未配置图像 Provider 时禁用并说明原因

原工程审核、局部纠正和输出准备继续保留为后续阶段，不在本轮伪实现。

## 6. 持久化

- 开发版默认保存到 `output/auto_solution_v2_store.json`
- JSON 使用 UTF-8 和原子替换，避免中途写入留下半文件
- 存储层只持久化，不做解析与方案生成
- 测试使用临时目录，不污染用户记录

## 7. 验收标准

1. 原始需求保存、解析、确认建议后内容保持原样。
2. 需求可新建、编辑、复制、归档、删除、重开读取。
3. 第二次修改生成 V2 快照，可查看修改前后。
4. 历史检索结果可解释；无匹配时不伪造历史引用。
5. 候选方案严格包含三部分，工位带来源字段。
6. DrawingSpecification JSON 可往返，Prompt 包含明确空间和运动关系。
7. 三组 Mock 需求走完保存→检索→候选→Prompt，并导出最终数据结果。
8. 新界面可在 PySide6 offscreen 模式创建和操作；旧 PPT 功能测试不回归。

## 8. 明确不做

- 多 Agent 编排、复杂工作流引擎、知识图谱或向量数据库
- 自动 CAD、自动机械设计或把概念图作为工程真值
- 未经人工确认直接覆盖正式需求
- 自动写入正式 PPT 模块
- 在没有配置 Provider 时假装已经调用在线 AI 或图像生成 API
