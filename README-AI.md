# AI Onboarding

## 默认读取顺序

1. `AGENTS.md`：工程、安全和质量门规则。
2. `PROJECT_INDEX.md`：按任务定位 Spec、实现和测试。
3. 当前任务对应的一个或两个 `SPEC_*.md`。

不要默认通读 `PROJECT_LOG.md`、全部 Spec 或整个 `ui/main_window.py`。只有需要追溯历史决定时才在 `PROJECT_LOG.md` 中定向搜索关键词。

## 项目一句话

这是一个 Windows 本地 PySide6 工业技术方案 PPT 工作台：把模板、Excel/FAR、Word、图片、设备模块和人工确认的 AI 候选内容组装为可编辑 `.pptx`。

## 当前边界

- 正式项目唯一状态是 `PptProject`；无 CAD 实验室唯一状态是 `EquipmentScene`。
- 无 CAD Scene 必须通过逻辑门禁并由用户显式同步，才进入正式设备方案。
- 整机和模块图片可来自 AI 人工采用或手工导入；全部确认图齐全时，项目绑定同步会同时配置正式设备方案和 PPT 模块。
- Codex Pro 是默认候选图 Provider；OpenAI API 是单独计费备用路径。
- AI 只产生候选结构、文字或图片，不直接决定工艺逻辑，不直接写 OOXML。
- 模板和已有输出不可因生成失败而损坏；PPTX 通过暂存、验证和原子替换发布。
- 用户数据、候选图、FAR 素材、预览缓存和日志写入 `%LOCALAPPDATA%\KY_Project\PPT_Generator`，不进入 Git。
- 当前页是只读预览，不是自由编辑画布；PowerPoint 优先，WPS 为后备。
- PowerPoint/WPS 双端兼容仍需在有对应软件的机器上执行人工验收。

## 常用入口

- 桌面启动：`python run_desktop.py`
- 模板渲染：`python render_template.py ...`
- 基础生成：`python generate_ppt.py ...`
- 全量质量门：`powershell -ExecutionPolicy Bypass -File .\tools\quality_gate.ps1`

详细模块路由、状态流与文件边界见 `PROJECT_INDEX.md`。
