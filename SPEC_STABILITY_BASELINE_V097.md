# v0.9.7 稳定性与仓库基线

## 目标

在不改变现有 PPT 业务逻辑的前提下，建立可持续开发所需的仓库、文件、保存和验证边界。任何失败都不得破坏原模板、已保存项目或已存在的输出 PPT。

## 范围

1. Git 仅跟踪源码、测试、文档、模板和小型示例；模板 Office 文件使用 Git LFS。
2. `research_repos/`、`.codegraph/`、缓存、日志、用户项目、生成物不进入 Git。
3. 默认用户数据写入 `%LOCALAPPDATA%\KY_Project\PPT_Generator`，可用 `KY_PPT_APP_DATA_ROOT` 覆盖。
4. 项目 JSON 使用同目录临时文件加原子替换，并保留最近 3 个备份。
5. 新建、打开、退出前检测未保存修改，允许保存、放弃或取消。
6. PPT 先写同目录暂存文件，完成 ZIP 结构、页数和重新打开验证后才替换目标文件。
7. 根目录执行 `python -m pytest` 时只收集本项目 `tests/`。
8. AI 默认入口只读取简短索引；按任务路由到对应 Spec 和实现，避免每次加载全部历史。

## 数据目录

```text
%LOCALAPPDATA%\KY_Project\PPT_Generator\
├─ data\
│  ├─ auto_solution\auto_solution_v2_store.json
│  └─ projects\<projectId>\
│     ├─ ai_candidates\...
│     └─ far_assets\...
├─ cache\previews\...
└─ logs\...
```

- `output/` 只作为人工选择的导出位置和旧版兼容位置，不再承载应用数据库。
- 旧版 `output/auto_solution_v2_store.json` 在新数据文件不存在时复制到新位置；原文件保留。
- 已有项目 JSON 中的绝对素材路径继续有效，本版本不做破坏性批量迁移。

## 验收

- 根目录 `python -m pytest -q` 与 `python -m unittest discover -s tests -q` 均通过。
- 项目连续保存后可读取，且 `.bak1` 至 `.bak3` 按新到旧保留。
- 模拟 PPT 校验失败时，已有目标 PPT 字节保持不变，暂存文件被清理。
- UI 修改项目后，新建、打开和关闭均出现未保存确认；取消操作不会丢失当前状态。
- `git status` 不包含用户运行数据、输出、日志、缓存、研究仓库或 CodeGraph 索引。

## 不在本版本处理

- 不拆分 `MainWindow` 的全部历史代码，只增加独立的路径、会话和原子 I/O 边界。
- 不删除旧 `output/`、旧候选图或 `research_repos/`。
- 不自动安装 PowerPoint/WPS，也不宣称完成尚未执行的 WPS 兼容验收。
- 不批量改写旧项目中的素材绝对路径。
