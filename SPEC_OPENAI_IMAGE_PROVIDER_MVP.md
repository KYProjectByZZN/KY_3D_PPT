# Spec：OpenAI 设备方案效果图 Provider MVP

## 1. 目标

把已经通过逻辑门禁的 `EquipmentScene` 以只读快照提交给 OpenAI 图片 API，生成可供人工审核的工业设备概念效果图，并确保生成记录能够追溯到唯一的 Scene、控制图、提示词和模型版本。

本功能解决的是“无 CAD 阶段的售前概念图”，不替代 CAD、机构设计、干涉检查、节拍计算或工程师审核。

## 2. 已确认选择

- 图片 Provider：OpenAI。
- API：Image Edit，输入当前确定性 SVG 转换出的 PNG 结构控制图。
- 模型：固定快照 `gpt-image-2-2026-04-21`，避免别名升级造成未审核的行为变化。
- 默认参数：`1536x1024`、`medium`、1 张候选图。
- API Key：优先读取 `OPENAI_API_KEY`，也允许在界面临时输入；只保留在本次软件会话，不写入项目 JSON、Scene、生成记录或日志。
- 结果仍需人工审核；当前版本不自动写入正式候选方案或 PPT。

## 3. 权威状态与边界

```text
EquipmentScene
  → NoCadSchemeService 重新计算逻辑门禁和 sceneHash
  → SVG 转 PNG 控制图
  → OpenAIImageRequest（只读快照）
  → OpenAI Image Edit
  → 候选 PNG + generation.json
  → 人工采用记录 accepted.json
```

- `EquipmentScene` 是设备逻辑唯一权威数据源。
- Provider 不接收编辑器对象，不能回写或修改 Scene。
- 提交前必须重新计算 Scene；计算出的哈希与界面检查结果不一致时视为过期并拒绝提交。
- 存在任一 blocking 逻辑问题时禁止提交。
- AI 图片不能作为模块数量、顺序和连接关系的权威来源。

## 4. 请求与输出

请求至少包含：

- Scene 快照与 `sceneHash`；
- 结构控制 PNG；
- 固定模型版本；
- 图片尺寸、质量、候选数量；
- 强约束提示词。

输出目录：

```text
output/ai_candidates/<sceneHash>/<batchId>/
  candidate_01.png
  candidate_02.png        # 用户要求多候选时
  generation.json
  accepted.json           # 人工点击采用后才存在
```

`generation.json` 保存：请求参数、Scene 快照、控制图 SHA-256、模型、OpenAI 请求 ID、候选图路径和 SHA-256。任何文件均不得包含 API Key。

## 5. 界面行为

- 逻辑通过时，“使用 OpenAI 生成效果图”按钮可用；逻辑阻断时禁用。
- 弹窗显示 API Key、固定模型、尺寸、质量和候选数量。
- 支持“测试连接”，不生成图片。
- 真实生成放在线程中执行，主界面不能被网络请求冻结。
- 候选图逐张预览，明确显示工程逻辑人工核验清单。
- 人工点击“采用当前候选”后只登记采用记录，不自动修改 Scene、正式方案或 PPT。

## 6. 失败处理

- 缺少 Key、SDK、控制图或模型权限时显示明确错误。
- API 请求失败时不得写成功 manifest。
- 返回数量不符、Base64 无效或不是 PNG 时拒绝结果。
- 错误信息中若意外包含 API Key，必须替换为 `***`。
- 弹窗中有运行任务时禁止关闭，避免后台线程被提前销毁。

## 7. 验收标准

1. 同一 Scene 的请求记录包含一致的 `sceneHash`。
2. Scene 在检查后被修改时拒绝提交。
3. 逻辑阻断 Scene 拒绝提交。
4. 通过 Fake Provider 可生成 1～4 张候选图并保存完整 manifest。
5. manifest 和界面输出不包含 API Key。
6. 非 PNG、无图片数据和返回数量不符均明确失败。
7. 界面离屏测试确认通过/阻断时按钮状态正确。
8. 原有完整测试继续通过。

## 8. 本期不做

- 不保证相同提示词得到像素一致的图片；固定模型只能减少模型版本变化，图片生成仍具有随机性。
- 不做局部蒙版重绘、多轮对话编辑或自动视觉验收。
- 不做 AI 图片与 Scene 的自动语义比对。
- 不自动合并正式候选方案、设备模块页或 PPT。
- 不保存 API Key 到项目文件或明文配置文件。
