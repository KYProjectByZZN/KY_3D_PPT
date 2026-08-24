# NAT6704 v2 模板人工配置草案

> 状态：用户已同意先采用默认模块；可执行配置见 `NAT6704_v2.template.json`。模块归属和内容后续可在软件中调整。

## 模板信息

| 项目 | 值 |
|---|---|
| 文件 | `冲压筒形壳体检测方案NAT6704_v2.pptx` |
| SHA-256 | `795ACCABC0BB6B6EFC619E585A17A2BCA8E03C8B418CE5F8223DF1962A058CDF` |
| 页面 | 23 |
| Master / Layout | 1 / 11 |
| 对象 | 189 |
| 图片 / 表格 / 图表 | 22 / 4 / 0 |
| 媒体 | 22 PNG、3 JPEG |
| 备注页 | 14 |
| 字体 | Arial、微软雅黑 |
| 外部关系 | 第 1 页公司网站超链接 |
| 宏 / 嵌入对象 | 无 / 无 |

## 页面与模块草案

| 页码 | 当前标题 | 建议模块 | 初步处理 |
|---:|---|---|---|
| 1 | 封面 | `cover` | 动态：项目名、编号、日期、联系人 |
| 2 | 开异介绍 | `company_intro` | 固定/可选 |
| 3 | 需求概览 | `customer_requirement` | 动态：产品、要求、说明、样品图 |
| 4 | 检测流程 | `inspection_flow` | 动态：流程节点；高风险页 |
| 5 | 设备示意图 | `equipment_overview` | 动态：说明和设备图 |
| 6 | 带隔板装箱 | `equipment_module` | 动态/可选 |
| 7 | 移动上料机构 | `equipment_module` | 动态/可选 |
| 8 | 搬运机构 | `equipment_module` | 动态/可选 |
| 9 | 移动下料机构 | `equipment_module` | 动态/可选 |
| 10 | 设备参数 | `equipment_parameters` | 动态表格 |
| 11–15 | 检测效果 | `inspection_result` | 动态/可选：说明和效果图 |
| 16 | 产品检测项说明 | `inspection_items` | 动态表格 |
| 17 | 机器视觉系统 | `vision_system` | 固定或半动态 |
| 18 | 工控机 | `control_system` | 固定或半动态 |
| 19 | AI 深度学习 | `ai_algorithm` | 固定或半动态 |
| 20 | 主要部件品牌 | `core_components` | 动态表格 |
| 21 | 公司资质 | `company_qualification` | 固定/可选 |
| 22 | 文件版本变更记录 | `revision_record` | 自动生成或固定 |
| 23 | 谢谢 | `ending` | 固定 |

## 首批建议配置的 Slot

| 页码 | Slot 建议 |
|---:|---|
| 1 | `company_name`、`project_title`、`project_code`、`date`、`contact` |
| 3 | `product_name`、`inspection_requirement`、`feeding_mode`、`inspection_summary`、`special_notes`、`product_image` |
| 4 | `flow_title`、`flow_steps[]`、`flow_caption` |
| 5 | `equipment_title`、`equipment_description`、`equipment_image`、`caption` |
| 10 | `equipment_parameters[]`、`parameter_note`、`table_caption` |
| 16 | `inspection_items[]`、`accuracy_note`、`table_caption` |

最终配置必须记录页码、Shape ID、对象类型、业务 Slot、是否必填、文字容量和图片比例；不依赖“文本框 1”这类可能重复的名称。

## 后续可调整项

1. 第 2、17、18、19、21、23 页是否作为公司固定页，默认直接复用？
2. 第 6～9 页是固定设备模块，还是根据项目增删并替换图片/文字？
3. 第 11～15 页是五个必须保留的检测视角，还是候选页面按实际图片数量选择？
4. 第 20 页主要部件品牌是否从 Excel 自动填充？
5. 第 22 页版本记录是否由软件自动生成？
6. 第 1 页公司网站超链接需要保留还是移除？
7. 请为首批代表页提供要替换成什么内容，或允许先使用明确标注为“测试”的虚拟数据。

这些内容不再阻塞 M2 技术验证。当前按默认值生成测试文件，等进入桌面 MVP 和真实项目资料阶段后在软件中调整。
