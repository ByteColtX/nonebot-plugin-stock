---
id: stock-plugin
type: module-design
title: nonebot-plugin-stock 插件模块
status: active
---

# nonebot-plugin-stock 插件模块

## 职责

一个 NoneBot2 插件：在 QQ 群/私聊里按 `CODE.MARKET` 格式查询股票行情、管理快捷标的、
查看市场榜单。命令入口是 `plugin.py`，`/longbridge` 与 `/stock` 等价。

## 能力与归属

| 能力 | 归属 | 数据来源 |
| --- | --- | --- |
| 实时行情（`quote`、`quick quote`、快捷词直查） | `plugin.py` + `providers/` | 可配置的多个行情数据源 |
| 快捷标的持久化与匹配 | `symbols.py` | `nonebot-plugin-localstore` |
| 市场榜单（`rank`、`rank turnover`、榜单分类） | `plugin.py` + `rank.py` + `formatters.py` | 仅 Longbridge OpenAPI |
| 行情与榜单的消息格式化 | `formatters.py` | 无（纯函数） |
| Longbridge 配置与客户端缓存 | `client.py` | Longbridge 凭证 |

## 边界

- **行情查询不依赖具体数据源**：`plugin.py` 只消费 `providers.Quote`，不接触
  `longbridge.openapi` 的行情类型。新增数据源只需实现 `providers` 的协议并注册，见
  [行情数据源抽象层](providers/SPEC.md)。
- **榜单是 Longbridge 专属能力**：榜单走 Longbridge 内部 HTTP 接口，没有免费等价物，
  因此榜单路径允许直接依赖 `longbridge.openapi`，未配置凭证时提示配置错误。
- **凭证只从 NoneBot 配置读取**，不落盘、不进代码或测试。快捷标的由 localstore 持久化，
  不使用仓库内固定文件。
- 消息层只做展示：一条行情消息里的所有标的来自同一个数据源，末尾标注实际数据源；
  取不到的标的以 `❌ 代码：原因` 追加，而不是让整条消息失败。

## 配置

`STOCK_QUOTE_SOURCES`（行情数据源优先级）与 `STOCK_SOURCE_TIMEOUT`（单源超时）决定行情
路径的行为；`LONGBRIDGE_APP_KEY` / `LONGBRIDGE_APP_SECRET` / `LONGBRIDGE_ACCESS_TOKEN`
只在榜单或把 Longbridge 列为行情数据源时必需。

## 已知限制

- 免费数据源的数据可能有延迟，且不提供交易状态；`.SG` 市场只有 Longbridge 支持。
- 仓库尚无根级 `goal-and-requirements` 与 `architecture-design` 文档，本 spec 是当前
  唯一的上层记录。
