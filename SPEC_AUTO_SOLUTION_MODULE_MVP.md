# Spec：可靠技术方案自动生成独立模块 MVP

> 状态：2026-08-24 原型阶段已完成，后续实现由 `SPEC_AUTO_SOLUTION_V2.md` 接管。需求来源为 `templates/自动方案模块提示词.txt`。本文件保留用于追踪最初的六阶段边界。

## 1. Goal

在现有 PySide6 软件中增加顶层“自动方案（试验）”入口，展示并验证以下闭环应如何被工程师操作：

```text
客户需求 → 历史/标准模块检索 → 候选方案 → 工程审核
→ 局部纠正 → 输出准备 → 确认后再合并正式PPT链路
```

首版重点不是自动生成，而是先确认字段、页面分组、审核边界和操作顺序。

## 2. 现状与差距

### 2.1 可直接复用

- Excel/Word通用解析和光学FAR结构化解析。
- schema v3项目、PPT模块/页面实例、设备流程节点和实体设备模块。
- 模板配置、关系安全的PPT复制渲染、当前页预览和图片素材记录。
- 人工确认后再生成PPT的既有产品原则。

### 2.2 当前缺失

- 跨输入来源统一的 Requirement JSON 和缺失参数状态。
- 历史项目库、标准模块库和可解释的相似度检索。
- 每个工位/模块/参数的来源、置信度和人工锁定。
- 确定性工程规则、ValidationResult和局部纠正版本链。
- CAD/STEP/SolidWorks正式方案图生成和可验证的模块接口。

### 2.3 不应直接复用

- 不能把现有设备方案中的自由文字直接当成已验证工程结论。
- 不能把FAR检测效果图片当成机械方案图。
- 不能让AI输出直接进入Renderer；AI只输出结构化候选数据。

## 3. Scope

### In scope

- 顶层“自动方案（试验）”页签。
- 六阶段可点击导航：客户需求、历史/模块检索、候选方案、工程审核、局部纠正、输出准备。
- `RequirementModel`、`SolutionModel`、`ModuleModel`、`ValidationResult` 四类UI无关草稿模型。
- 界面显示需求字段状态、来源类型、工位候选、模块候选、验证规则、问题列表、锁定/版本边界和输出检查项。
- 明确显示“独立试验、尚未接入正式项目/PPT”。

### Out of scope

- 不调用AI API，不实现Solution/Validation/Correction Agent。
- 不建立SQLite、向量库、历史项目导入或相似度算法。
- 不执行真实节拍、干涉、视觉工艺或机械安全计算。
- 不修改 `PptProject` schema，不保存到 `.kyppt.json`。
- 不修改模板、Renderer、现有设备方案或一键检测效果流程。
- 不提供“合并到正式PPT”的可用按钮。

## 4. 核心数据模型

### 4.1 RequirementModel

固定字段至少包含：产品、尺寸、材料、检测项目、精度、节拍、产能、上下料、工艺、特殊要求和限制条件。每个字段使用：

```json
{
  "value": "",
  "state": "unknown | need_confirm | confirmed",
  "source_type": "customer | excel | word | pdf | manual | ai_inference",
  "source_ref": ""
}
```

缺失值不得自动补写；AI推测不能标为 `confirmed`。

### 4.2 SolutionModel

```json
{
  "version": 1,
  "process": [],
  "stations": [],
  "module_ids": [],
  "cycle_time": {},
  "inspection": [],
  "risks": [],
  "references": []
}
```

工位对象预留功能、模块、原理、产品运动、执行机构、定位、检测、节拍、来源、置信度和人工锁定。

### 4.3 ModuleModel

保存模块ID、名称、使用条件、输入/输出、产品范围、节拍能力、尺寸/负载/精度范围、结构接口、工程图片/CAD路径、历史项目、风险和验证状态。

### 4.4 ValidationResult

保存审核是否通过、规则版本和问题列表。每个问题包含严重度、对象、规则、说明、建议、状态和是否阻止输出。验证引擎只能输出问题和证据，不能静默改写人工锁定内容。

## 5. 模块关系与目录边界

本轮实际新增：

```text
ppt_generator/
├─ auto_solution.py                 四类UI无关草稿模型和校验
└─ ui/
   └─ auto_solution_editor.py       六阶段独立工作台
```

当前关系：

```text
AutoSolutionEditor
├─ RequirementModel
├─ SolutionModel
├─ ModuleModel[]
└─ ValidationResult

──────── 用户确认前的隔离边界 ────────

现有 PptProject / EquipmentScheme / Renderer / Preview
```

确认后再按阶段增加，不提前创建空目录：

```text
ppt_generator/auto_solution/
├─ requirement_engine.py
├─ retrieval_engine.py
├─ solution_engine.py
├─ validation_engine.py
├─ correction_service.py
└─ repository.py
```

与正式PPT连接时只允许通过已审核的结构化适配器进入现有`PptProject`，不得让Agent直接调用Renderer坐标或改写模板。

## 6. 界面结构

```text
自动方案（试验）
├─ 1 客户需求        固定需求字段、状态、来源
├─ 2 历史/模块检索   历史项目候选、标准模块候选
├─ 3 候选方案        流程、工位、模块、来源、置信度、锁定
├─ 4 工程审核        规则分类、问题清单、阻断状态
├─ 5 局部纠正        版本、局部变更、人工锁定
└─ 6 输出准备        完整性检查；正式合并按钮禁用
```

页面顶部持续显示：`独立试验模块｜尚未接入正式项目和PPT生成`。

## 7. 风险控制

- UI中不得出现“已通过”“可正式输出”等虚假默认状态。
- 示例页不预填具体机械参数，避免样例被误认成工程结论。
- 所有自动化按钮在引擎未实现前保持禁用并标注阶段。
- 本模块不得改变现有项目数据、PPT页数、预览指纹或生成文件。

## 8. Acceptance Tests

- Given 软件启动，when 查看顶层工作区，then 存在第5个“自动方案（试验）”页签。
- Given 点击自动方案页签，when 依次点击左侧六阶段，then 右侧显示对应界面且阶段标题一致。
- Given 新建模块模型，when 序列化并重建，then Requirement、Solution、Module、Validation数据不丢失。
- Given Requirement字段为空，when 序列化，then 状态保持`unknown/need_confirm`，不生成猜测值。
- Given来源为`ai_inference`且字段标为`confirmed`，when校验，then明确拒绝。
- Given自动方案界面存在，when运行现有PPT测试，then项目页数、Renderer和预览测试保持通过。
- “合并到正式PPT”按钮默认禁用，界面明确说明需用户确认后才能接入。

## 9. 实施顺序

1. 独立核心草稿模型和序列化测试。
2. 独立PySide6编辑器和六阶段界面。
3. 在主窗口新增顶层入口，但不连接项目保存/生成。
4. 用户审核字段、分组和工作流。
5. 确认后再单独制定Requirement导入、检索库、规则引擎和正式合并Spec。
