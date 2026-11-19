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

Longbridge 支持两种认证方式：OAuth 2.0 和传统的 API Key。插件会自动选择：配置了
`LONGBRIDGE_OAUTH_CLIENT_ID` 时优先使用 OAuth 2.0，否则使用 API Key；两种方式都配置时也优先
OAuth。`LONGBRIDGE_AUTH_METHOD` 只在需要强制指定时使用。
OAuth 2.0 不需要 App Secret 和长期 Access Token，令牌由 SDK 自动缓存与刷新。

> ⚠️ **安全提示：** 本插件仅建议使用 Longbridge 模拟账户进行开发和测试。
> 不要使用真实股票账户的 API Key、App Secret 或 Access Token，也不要将任何凭证提交到代码仓库。

| 配置项 | 必填 | 默认值 | 说明 |
| :--- | :---: | :---: | :--- |
| `STOCK_QUOTE_SOURCES` | 否 | `tencent,sina` | 行情数据源优先级，逗号分隔，第一个为主源 |
| `STOCK_SOURCE_TIMEOUT` | 否 | `5` | 单个数据源的超时秒数，取值范围 0.5-30 |
| `LONGBRIDGE_AUTH_METHOD` | 否 | 自动 | 可强制指定 `apikey` 或 `oauth`；通常无需设置 |
| `LONGBRIDGE_APP_KEY` | 否 | 无 | Longbridge App Key（`apikey` 方式） |
| `LONGBRIDGE_APP_SECRET` | 否 | 无 | Longbridge App Secret（`apikey` 方式） |
| `LONGBRIDGE_ACCESS_TOKEN` | 否 | 无 | Longbridge Access Token（`apikey` 方式） |
| `LONGBRIDGE_OAUTH_CLIENT_ID` | 否 | 无 | OAuth 2.0 客户端 ID，配置后自动启用 OAuth |
| `LONGBRIDGE_OAUTH_CALLBACK_PORT` | 否 | `60355` | OAuth 本地回调端口，需与注册的 `redirect_uri` 一致 |

示例：

```dotenv
# 默认：腾讯为主源，新浪为备用源，无需任何凭证
STOCK_QUOTE_SOURCES=tencent,sina
STOCK_SOURCE_TIMEOUT=5

# 想用 Longbridge 作为行情主源（需要下面的凭证）
# STOCK_QUOTE_SOURCES=longbridge,tencent,sina

# 方式一：API Key（未配置 OAuth Client ID 时自动使用）
LONGBRIDGE_APP_KEY=你的AppKey
LONGBRIDGE_APP_SECRET=你的AppSecret
LONGBRIDGE_ACCESS_TOKEN=你的AccessToken

# 方式二：OAuth 2.0（配置 Client ID 后自动优先使用）
# LONGBRIDGE_OAUTH_CLIENT_ID=你的client_id
# LONGBRIDGE_OAUTH_CALLBACK_PORT=60355
```

### OAuth 2.0 认证

OAuth 2.0 使用 Bearer Token 且无需 HMAC 签名，Longbridge 官方推荐使用这种方式。

1. 向 Longbridge 注册 OAuth 客户端，`redirect_uris` 需与回调端口一致：

   ```bash
   curl -X POST https://openapi.longbridge.com/oauth2/register \
     -H "Content-Type: application/json" \
     -d '{
       "redirect_uris": ["http://localhost:60355/callback"],
       "token_endpoint_auth_method": "none",
       "grant_types": ["authorization_code", "refresh_token"],
       "response_types": ["code"],
       "client_name": "nonebot-plugin-stock"
     }'
   ```

2. 在 `.env` 中设置 `LONGBRIDGE_OAUTH_CLIENT_ID` 即可自动启用 OAuth；如果同时配置了
   API Key 但仍想使用 OAuth，无需额外设置（OAuth 优先）。`redirect_uri` 使用其他端口时
   同时设置 `LONGBRIDGE_OAUTH_CALLBACK_PORT`。

3. 启动 NoneBot。首次启动且本地没有令牌时，日志会输出 **Longbridge OAuth 授权链接**，
   用浏览器打开并按提示完成授权。

首次授权需要浏览器能访问插件所在机器的回调端口，因此建议在运行机器人的电脑上完成；
授权完成后令牌会缓存到 `~/.longbridge/openapi/tokens/<client_id>`
（Windows 为 `%USERPROFILE%\.longbridge\openapi\tokens\<client_id>`），后续启动会自动复用、
自动刷新，不再需要浏览器操作。若机器人在远端服务器上，可在本地完成授权后把该令牌文件
复制到服务器相同路径。

OAuth 认证下 Longbridge 行情与榜单共用同一授权句柄，插件会在启动时后台预热授权，
避免首个行情请求因等待浏览器回调而超时降级到免费数据源。

### 数据源

| 数据源 | 键名 | 凭证 | 市场 | 成交额 | 备注 |
| :--- | :--- | :---: | :--- | :---: | :--- |
| 腾讯行情 | `tencent` | 不需要 | 美、港、A 股 | 有 | 默认主源 |
| 新浪行情 | `sina` | 不需要 | 美、港、A 股 | 有 | 不支持 `BRK.B` 这类类股票 |
| Longbridge OpenAPI | `longbridge` | 需要（API Key 或 OAuth） | 美、港、A 股、新加坡 | 有 | 榜单的唯一来源，需装 `[longbridge]` 额外依赖 |

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
