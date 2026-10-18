---
id: stock-providers
type: submodule-design
title: 行情数据源抽象层
status: active
parent: stock-plugin
---

# 行情数据源抽象层

## 职责

把「查一批标的的行情」从具体供应商解耦：定义统一的行情数据类与数据源协议，按优先级
尝试多个数据源，并在某个源不可用时自动降级。存在的理由是单点故障——Longbridge 曾是
唯一数据源，一次故障就让行情命令全部失效。

## 契约

- `Quote` 是行情路径唯一的领域对象：标的、数据源键与展示名、货币、最新价/昨收/开高低、
  成交量（统一为**股**）、成交额（统一为计价货币金额）、交易状态、带时区的行情时间。
- `QuoteProvider` 协议只有 `key`、`label` 和 `fetch(symbols)`。`fetch` 返回
  `(quotes, symbol_errors)`：
  - **单个标的**取不到（市场不支持、无数据）→ 放进 `symbol_errors`，不抛异常；
  - **整个源**不可用（网络、HTTP、整包解析、超时）→ 抛 `ProviderError`；
  - **源未配置**（如缺 Longbridge 凭证）→ 抛 `ProviderUnavailableError`，由链路跳过。
- 所有异常都携带可读原因，最终汇总进用户可见的消息或日志。

## 链路语义（`registry.py`）

- 按配置顺序尝试，`ProviderUnavailableError`、`ProviderError`、超时、空结果、任何未预期
  异常都只记 warning 并继续下一个源——单个源的缺陷不应让整条查询失败。
- 第一个返回非空行情的源胜出，**一条消息只来自一个源**，`QuoteResult` 带上实际源，
  供消息末尾标注。
- 全部失败抛 `StockSourceError`，携带已尝试的源名和累计的逐标的失败原因，用户能看到
  「已尝试：…」而不是笼统的失败。
- 每个源的超时由 `STOCK_SOURCE_TIMEOUT` 统一控制，默认 5 秒。

## 已接入的数据源

| 键名 | 实现 | 凭证 | 市场 | 交易状态 |
| --- | --- | --- | --- | --- |
| `tencent` | `tencent.py`（`qt.gtimg.cn`，GBK 文本） | 无 | 美、港、A 股 | 无 |
| `sina` | `sina.py`（`hq.sinajs.cn`，GBK 文本，需 `Referer`） | 无 | 美、港、A 股 | 无 |
| `longbridge` | `longbridge.py`（`AsyncQuoteContext`） | 需要 | 美、港、A 股、新加坡 | 有 |

默认优先级是 `tencent → sina`：开箱即用且不依赖任何凭证。Longbridge 需要显式写进
`STOCK_QUOTE_SOURCES` 才参与行情查询；凭证不全时自动跳过而不是报错。

## 口径归一化（改解析前必读）

各源的字段口径不同，实现里已按市场处理，回归测试固定了这些换算：

- 腾讯 A 股成交量单位是「手」（×100 得股），成交额单位是「万元」（×10000 得元）；
  港股成交量已是股。
- 腾讯港股代码必须补零到 5 位；新浪港股是 `rt_hk` 前缀同样补零。
- 新浪不支持 `BRK.B` 这类带分隔符的美股代码，映射阶段直接判为不支持。
- `.SG` 两家免费源都不支持，只有 Longbridge 能查。
- 时间戳格式三家都不同（腾讯 A 股 `20261016161447`、腾讯港股 `2026/10/16 16:08:22`、
  新浪为日期与时间两段），统一解析成东八区带时区时间。

## 扩展一个新数据源

1. 在包内新增模块，实现 `fetch` 与标的映射，把口径差异收在解析函数里；
2. 在 `constants.QUOTE_SOURCE_LABELS` 与 `registry.build_providers` 中注册键名；
3. 用 `httpx.MockTransport` 覆盖解析与失败路径的测试，不依赖真实网络。

## 已知限制

- 免费源没有公开的限流阈值，实测稳定但未做压力测试；触发限流时表现为该源抛
  `ProviderError` 后降级，不影响结果正确性。
- 不做行情缓存：重复查询会重复打免费源。若线上触发限流，再加短 TTL 缓存。
