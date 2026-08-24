# Spec: NAT6704 模板与渲染技术验证

> 状态：M2 最小闭环已实现；等待 PowerPoint/WPS 人工视觉验收。  
> 输入模板：`templates/冲压筒形壳体检测方案NAT6704_v2.pptx`

## Goal

验证该 PPTX 能否通过人工配置模块和可替换位置，稳定生成新的可编辑技术方案，并同时兼容 Microsoft PowerPoint 与 WPS。

## Scope

In scope:

- 保持原模板只读并记录文件哈希。
- 建立人工模块与 Slot 配置草案。
- 选择代表页面验证文字、图片、流程图和表格替换。
- 比较 `python-pptx` 与必要时的本地 Node Renderer。
- 检查输出 PPTX 包结构，并在 PowerPoint/WPS 中人工验收。

Out of scope:

- PySide6 正式界面。
- Excel/Word 解析、图片素材库和 AI 接入。
- 承诺任意 PPT 模板自动识别。
- 修改或覆盖原始模板。

## Inputs And Outputs

Inputs:

- 原始 PPTX 模板。
- 可由后续软件调整的默认页面模块配置。
- 6 页代表页面的明确测试文字和表格数据。

Outputs:

- `templates/NAT6704_v2.template.json`。
- `output/NAT6704_v2_M2配置渲染测试.pptx`。
- 自动结构检查结果，以及待完成的 PowerPoint/WPS 人工视觉检查。
- 当前 Renderer 选择结论及已知限制。

## Behavior

- 原模板只读；所有操作基于工作副本。
- 只替换清单中明确配置的 Slot，不按模糊文本全局替换。
- 第一批代表页建议为：
  - 第 1 页：封面文字。
  - 第 3 页：需求文字与样品图片。
  - 第 4 页：复杂流程节点文字。
  - 第 5 页：设备说明与设备图片。
  - 第 10 页：设备参数表。
  - 第 16 页：检测项表格。
- 缺少必填内容时停止生成并报告页码和 Slot。
- 输出文件已存在时拒绝覆盖，除非明确允许。
- 不依赖 PowerPoint/WPS COM 完成核心生成。

## Risk

- 模板中大量对象名是通用名称，必须用页码、Shape ID 和人工语义键组合绑定。
- 第 4 页有 33 个对象，连接线和节点关系容易在复制时受损。
- 模板同时使用 Arial 和微软雅黑，PowerPoint/WPS 的换行可能不同。
- 文件约 35 MB，图片复制和关系处理需关注体积及性能。
- 模板含一个公司网站外部超链接，生成后应保持或由用户决定移除。
- 两端视觉一致不能仅靠结构测试，必须人工检查截图或导出结果。

## Acceptance Tests

- [x] 原模板 SHA-256 仍为 `795ACCABC0BB6B6EFC619E585A17A2BCA8E03C8B418CE5F8223DF1962A058CDF`。
- [x] 输出以 ZIP 签名开头，包含必要文件和 23 个 Slide XML。
- [ ] 输出在 Microsoft PowerPoint 和 WPS 中打开均无修复提示并完成视觉检查。
- [x] 语义对比未发现非目标 Shape 内容、位置、图片或表格发生变化。
- [x] 文字、图片和表格替换均有自动化可编辑性验证。
- [x] 第 4 页保留 33 个对象和 3 条连接线，未改动非目标对象。
- [x] 第 10、16 页表格仍分别为 7×4 和 9×5。
- [x] 外部超链接、14 页备注、1 个母版、11 个 Layout 和 25 个媒体文件保留。
- [x] 同一配置连续生成 20 次通过，原文件哈希不变。

## Implementation Notes

- 当前使用 `python-pptx`，已经满足本阶段原位文字、表格和图片替换。
- 页面复制、动态增删页或复杂媒体关系后续失败时，再验证 `pptx-automizer + PptxGenJS`。
- 不先直接编辑 ZIP/XML；仅在库无法保留必要结构时评估精确修补。
- 默认模块和 Slot 在 JSON 中配置，后续 UI 只编辑配置，不改变 Renderer 代码。
- Microsoft PowerPoint 已检测到安装，但无窗口自动打开受到本机 Office 启动提示阻塞；WPS 未检测到安装，因此双端验收不能标记完成。
