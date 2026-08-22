# AGENTS.md

本文件为在本仓库中工作的 coding agent 提供最少且必要的项目约定。以
`pyproject.toml`、源码和测试的实际行为为准；不要把通用模板内容带入本项目。

## 项目概况

- 本项目是 Python 3.10+ 的 NoneBot 插件，使用 `uv` 管理环境和依赖。
- 包源码位于 `src/nonebot_plugin_stock/`，测试位于 `tests/`；`pyproject.toml` 是
  插件、pytest 和 Ruff 配置的来源。
- `src/nonebot_plugin_stock/` 实现基于 Longbridge OpenAPI 的行情功能，其中
  `plugin.py` 是 NoneBot 入口。修改行情逻辑时，应保持现有命令行为：
  `/longbridge` 与 `/stock` 别名、`quote`、`quick`、`rank` 子命令，以及
  `CODE.MARKET` 标的格式。
- Longbridge 凭证从 NoneBot 配置读取：`LONGBRIDGE_APP_KEY`、
  `LONGBRIDGE_APP_SECRET`、`LONGBRIDGE_ACCESS_TOKEN`。不得将凭证写入代码、测试
  或提交记录。快捷标的由 `nonebot-plugin-localstore` 持久化，不要改为仓库内固定
  文件。

## 开发与验证

所有 Python 命令均使用 `uv` 执行，不直接使用 `python`、`pip` 或 `pipx`。

```bash
uv sync
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run pre-commit run --all-files
```

修改代码后至少运行相关测试和 `uv run ruff check .`；涉及格式时再运行
`uv run ruff format .`。完整覆盖率测试使用项目已配置的任务：

```bash
uv run poe test
```

新增测试放在 `tests/`，命名为 `test_<module>.py`。Longbridge 网络请求应使用 mock，
测试不得依赖真实凭证或外部服务。

## 代码约定

- 遵循 PEP 8，行宽以 Ruff 配置的 88 个字符为准。
- 新增或修改的公共函数、方法和类必须有 Google 风格 docstring；函数参数和返回值
  必须有类型注解。私有函数可使用单行 docstring。
- 异步处理、异常边界、消息格式和缓存/锁的设计应在拆分后的模块之间保持一致；
  优先复用现有辅助函数，不重复实现行情格式化和配置读取。
- 变更功能时同步更新测试；不要为了让测试通过而放宽生产代码的校验或错误处理。

## Git 提交

提交信息使用 Conventional Commits，标题和 body 均使用中文，例如：
`fix(stock): 修复榜单数量校验`。常用类型为 `feat`、`fix`、`docs`、`test`、
`refactor`、`perf` 和 `chore`。提交前确保测试、Ruff 和 pre-commit 检查通过；除非
用户明确要求，不自动创建提交。
