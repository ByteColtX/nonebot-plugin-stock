<div align="center">
    <a href="https://v2.nonebot.dev/store">
    <img src="https://raw.githubusercontent.com/fllesser/nonebot-plugin-template/refs/heads/resource/.docs/NoneBotPlugin.svg" width="310" alt="logo"></a>

## ✨ nonebot-plugin-stock ✨
[![LICENSE](https://img.shields.io/github/license/ByteColtX/nonebot-plugin-stock.svg)](./LICENSE)
[![pypi](https://img.shields.io/pypi/v/nonebot-plugin-stock.svg)](https://pypi.python.org/pypi/nonebot-plugin-stock)
[![python](https://img.shields.io/badge/python-3.10|3.11|3.12|3.13-blue.svg)](https://www.python.org)
[![uv](https://img.shields.io/badge/package%20manager-uv-black?style=flat-square&logo=uv)](https://github.com/astral-sh/uv)
<br/>
[![ruff](https://img.shields.io/badge/code%20style-ruff-black?style=flat-square&logo=ruff)](https://github.com/astral-sh/ruff)
[![pre-commit](https://results.pre-commit.ci/badge/github/ByteColtX/nonebot-plugin-stock/master.svg)](https://results.pre-commit.ci/latest/github/ByteColtX/nonebot-plugin-stock/master)

</div>

## 📖 介绍

nonebot-plugin-stock 是一个 NoneBot2 股票行情插件，在 QQ 群聊与私聊里提供实时行情查询、
快捷标的和市场榜单。

行情数据源是可插拔的：内置腾讯行情与新浪行情两个免费数据源，主源不可用时自动降级到备用源，
每条消息都会标注实际数据源；Longbridge OpenAPI 作为可选数据源接入，同时也是市场榜单的唯一
来源。

行情路径不依赖任何凭证，榜单需要 Longbridge 凭证与 SDK。

## 💿 安装

<details open>
<summary>使用 nb-cli 安装</summary>
在 nonebot2 项目的根目录下打开命令行, 输入以下指令即可安装

    nb plugin install nonebot-plugin-stock --upgrade
使用 **pypi** 源安装

    nb plugin install nonebot-plugin-stock --upgrade -i "https://pypi.org/simple"
使用**清华源**安装

    nb plugin install nonebot-plugin-stock --upgrade -i "https://pypi.tuna.tsinghua.edu.cn/simple"


</details>

<details>
<summary>使用包管理器安装</summary>
在 nonebot2 项目的插件目录下, 打开命令行, 根据你使用的包管理器, 输入相应的安装命令

<details open>
<summary>uv</summary>

    uv add nonebot-plugin-stock
安装仓库 master 分支

    uv add git+https://github.com/ByteColtX/nonebot-plugin-stock@master
</details>

<details>
<summary>pdm</summary>

    pdm add nonebot-plugin-stock
安装仓库 master 分支

    pdm add git+https://github.com/ByteColtX/nonebot-plugin-stock@master
</details>
<details>
<summary>poetry</summary>

    poetry add nonebot-plugin-stock
安装仓库 master 分支

    poetry add git+https://github.com/ByteColtX/nonebot-plugin-stock@master
</details>

打开 nonebot2 项目根目录下的 `pyproject.toml` 文件, 在 `[tool.nonebot]` 部分追加写入

    plugins = ["nonebot_plugin_stock"]

</details>

<details>
<summary>使用 nbr 安装(使用 uv 管理依赖可用)</summary>

[nbr](https://github.com/fllesser/nbr) 是一个基于 uv 的 nb-cli，可以方便地管理 nonebot2

    nbr plugin install nonebot-plugin-stock
使用 **pypi** 源安装

    nbr plugin install nonebot-plugin-stock -i "https://pypi.org/simple"
使用**清华源**安装

    nbr plugin install nonebot-plugin-stock -i "https://pypi.tuna.tsinghua.edu.cn/simple"

</details>


## ⚙️ 配置

在 nonebot2 项目的`.env`文件中添加下表中的配置。Longbridge 凭证由 Longbridge 控制台提供，
只在需要榜单或把 Longbridge 用作行情数据源时才必填。

> ⚠️ **安全提示：** 本插件仅建议使用 Longbridge 模拟账户进行开发和测试。
> 不要使用真实股票账户的 API Key、App Secret 或 Access Token，也不要将任何凭证提交到代码仓库。

| 配置项 | 必填 | 默认值 | 说明 |
| :--- | :---: | :---: | :--- |
| `STOCK_QUOTE_SOURCES` | 否 | `tencent,sina` | 行情数据源优先级，逗号分隔，第一个为主源 |
| `STOCK_SOURCE_TIMEOUT` | 否 | `5` | 单个数据源的超时秒数，取值范围 0.5-30 |
| `LONGBRIDGE_APP_KEY` | 否 | 无 | Longbridge App Key |
| `LONGBRIDGE_APP_SECRET` | 否 | 无 | Longbridge App Secret |
| `LONGBRIDGE_ACCESS_TOKEN` | 否 | 无 | Longbridge Access Token |

示例：

```dotenv
# 默认：腾讯为主源，新浪为备用源，无需任何凭证
STOCK_QUOTE_SOURCES=tencent,sina
STOCK_SOURCE_TIMEOUT=5

# 想用 Longbridge 作为行情主源（需要下面的凭证）
# STOCK_QUOTE_SOURCES=longbridge,tencent,sina

LONGBRIDGE_APP_KEY=你的AppKey
LONGBRIDGE_APP_SECRET=你的AppSecret
LONGBRIDGE_ACCESS_TOKEN=你的AccessToken
```

### 数据源

| 数据源 | 键名 | 凭证 | 市场 | 成交额 | 备注 |
| :--- | :--- | :---: | :--- | :---: | :--- |
| 腾讯行情 | `tencent` | 不需要 | 美、港、A 股 | 有 | 默认主源 |
| 新浪行情 | `sina` | 不需要 | 美、港、A 股 | 有 | 不支持 `BRK.B` 这类类股票 |
| Longbridge OpenAPI | `longbridge` | 需要 | 美、港、A 股、新加坡 | 有 | 榜单的唯一来源，需装 `[longbridge]` 额外依赖 |

- 数据源按 `STOCK_QUOTE_SOURCES` 的顺序尝试，第一个成功的源提供整条消息的数据，消息末尾会
  标注**实际**数据源。
- 列了 `longbridge` 但凭证不全时会自动跳过并继续用后面的源，不会让插件整体不可用。
- 免费源的数据可能有延迟，且不提供交易状态（显示为 `-`）；`.SG` 市场只有 Longbridge 支持。
- 榜单（`/stock rank`、`/stock rank turnover`）仍然只走 Longbridge：未安装 SDK 时提示安装
  `nonebot-plugin-stock[longbridge]`，装了 SDK 但没配凭证时提示配置凭证。

## 🎉 使用

### 指令表

| 指令 | 权限 | 需要@ | 范围 | 说明 |
| :--- | :--- | :--- | :--- | :--- |
| `/stock quote <SYMBOL>...` | 群员 | 否 | 群聊、私聊 | 查询一个或多个标的的实时行情（多数据源） |
| `/stock quick <COMMAND>` | 群员 | 否 | 群聊、私聊 | 管理快捷标的 |
| `/stock rank [TYPE MARKET COUNT]` | 群员 | 否 | 群聊、私聊 | 查询 Longbridge 市场榜单（需要凭证） |
| 直接发送快捷代码 | 群员 | 否 | 群聊、私聊 | 查询内置或自定义快捷标的 |

`/longbridge` 与 `/stock` 等价。输入 `/stock --help` 可以查看完整帮助信息。

### 实时行情

```text
/stock quote AAPL.US
/stock quote TSLA.US NVDA.US
/longbridge quote 700.HK
```

### 快捷标的

内置快捷代码包括：`qqq`、`spy`、`aapl`、`tsla`、`msft`、`nvda`、`amzn`、`googl`、
`meta`、`amd` 和 `baba`。代码不区分大小写。

```text
/stock quick add COIN.US
/stock quick del COIN.US
/stock quick remove COIN.US
/stock quick list
/stock quick quote
```

添加 `COIN.US` 后，直接发送 `coin` 或 `COIN.US` 都可以查询。快捷标的由
`nonebot-plugin-localstore` 持久化。

### 市场榜单

```text
/stock rank
/stock rank hot US
/stock rank rising HK 20
/stock rank trade US 10
/stock rank discuss CN
/stock rank watch SG 10
/stock rank turnover US 10
```

普通榜单支持 `hot`、`rising`、`trade`、`discuss`、`watch` 类型，市场支持 `US`、
`HK`、`CN`、`SG`，数量范围为 1-50，默认 10。成交额榜支持 `US`、`HK`、`CN` 三个市场。
榜单由 Longbridge 服务端综合排序，插件不提供按单一字段重新排序的选项。

### 🎨 效果图

暂无示例图。
