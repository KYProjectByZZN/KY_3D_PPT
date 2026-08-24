# Spec: Codex Pro 设备方案图片 Provider MVP

## Goal

把无 CAD 设备方案的默认图片生成路径从按量计费的 OpenAI API Key 改为本机 Codex 的 ChatGPT 登录，使用用户已有的 Codex Pro 套餐额度；保留原 API Provider 作为显式备用选项。

## Scope

In scope:

- 新增独立的 Codex 本地运行时 Provider，复用现有 `EquipmentScene` 门禁、请求快照、候选图、追踪记录和人工采用流程。
- 默认选择“Codex Pro（ChatGPT 登录）”，支持检查登录和浏览器登录。
- 使用官方可脚本化 `codex exec` 运行时；Provider 接口保持可替换，后续可无感切换到 `openai-codex` Python SDK。
- Codex 任务在单个批次目录内以 `workspace-write` 沙箱运行，不授予项目源码写权限。
- API Key Provider 继续可选，API Key 仍只保存在本次界面会话。
- 所有网络和生成任务继续在 Qt 后台线程执行。

Out of scope:

- 不绕过 ChatGPT 登录、不读取或复制 Codex 登录令牌。
- 不把 Codex Pro 额度转换成通用 OpenAI API 额度。
- 不保证套餐无限使用；达到 Codex 使用限制时提示等待额度恢复。
- 不自动把采用图写入正式候选方案或 PPT。
- 不改变 `EquipmentScene` 的模块、顺序和逻辑权威性。

## Inputs And Outputs

Inputs:

- 已通过逻辑门禁的 `EquipmentScene` 只读快照和 `sceneHash`。
- 当前 SVG 渲染得到的 PNG 控制图。
- Codex ChatGPT 登录状态，或备用 OpenAI API Key。
- 图片尺寸、质量和 1～4 张候选数量。

Outputs:

- `output/ai_candidates/<sceneHash>/<batchId>/candidate_XX.png`。
- 不含凭据的 `generation.json`。
- 人工采用后生成 `accepted.json`。
- 界面中的登录、生成、限额和错误状态。

## Behavior

- 正常路径：默认 Codex Pro → 检查/登录 → 冻结 Scene → 生成控制图 → 后台调用 Codex → 校验 PNG → 保存 manifest → 人工核验。
- 未登录：不发起生成，显示“请登录 ChatGPT/Codex”，允许点击登录按钮打开官方浏览器流程。
- 缺少运行时：显示安装或更新 Codex 的中文提示，不回退到 API Key 付费路径。
- 达到套餐限制：显示 Codex 使用额度限制提示，不误导用户充值 API。
- API 备用路径：用户主动切换后才显示 API Key，并继续使用原固定图片模型。
- 兼容：已有注入式 Fake Provider 测试和 API Provider 行为继续有效。

## Risk

- Data loss: Codex 只写新批次目录，不覆盖 Scene、项目文件、模板或已有候选图。
- Security/permission: 登录由官方 Codex 完成；软件不接触密码或 OAuth token。Codex 任务工作目录限制为新批次目录。
- Performance: 登录和图片生成都可能较慢，必须在后台线程执行并阻止任务运行中关闭弹窗。
- Availability: Codex 图片能力和套餐限制由账号/地区决定；缺少图片输出时保留失败目录但不写成功 manifest。
- Release/update: 本版依赖系统可发现 `codex.cmd`/`codex`；后续打包需增加运行时检测或随安装器声明前置条件。

## Acceptance Tests

- Given 未登录状态，when 检查连接或生成，then 显示中文登录提示且不创建成功 manifest。
- Given Fake Codex 已登录并生成 PNG，when 请求 2 张候选，then 保存 2 张 PNG 和完整 manifest，provider 为 `codex-pro`。
- Given Codex 返回内嵌 PNG 数据而未直接写文件，when Provider 处理结果，then 仍可保存候选图。
- Given Codex 返回套餐额度错误，when 生成失败，then 提示 Codex 使用限制且不建议充值 API。
- Given 默认生产界面，then Codex Pro 是第一选项、API Key 隐藏、登录按钮可见。
- Given 用户切换 OpenAI API，then API Key 和固定图片模型可见，原 API Provider 测试继续通过。
- 完整单元测试和 Python 编译检查通过，界面离屏实例化不冻结。

## Implementation Notes

- 新模块：`ppt_generator/codex_image.py`，只负责 Codex 运行时、登录状态和候选文件适配。
- 现有数据契约：继续使用 `OpenAIImageRequest` / `OpenAIImageBatch`，避免本次为命名做无关重构；manifest 的 `provider` 区分来源。
- UI 适配：`ppt_generator/ui/openai_image_dialog.py` 管理 Provider 选择和后台 Worker，不读取 Provider 内部状态。
- 运行时调用：固定 `workspace-write`、`--ephemeral`、独立批次工作目录；控制图复制到该目录后作为唯一图片输入。
- 默认模型：Codex 代理使用 `gpt-5.6-sol`，图片由其可用的 ImageGen 能力生成；API 备用仍使用原固定图片模型。

