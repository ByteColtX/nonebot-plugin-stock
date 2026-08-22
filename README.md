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

基于 Longbridge OpenAPI 的 NoneBot 股票行情插件，支持实时行情、快捷标的和市场榜单查询。
插件使用 `/stock` 和 `/longbridge` 作为命令别名，行情标的使用 `CODE.MARKET` 格式。

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

在 nonebot2 项目的`.env`文件中添加下表中的必填配置。凭证由 Longbridge 控制台提供。

> ⚠️ **安全提示：** 本插件仅建议使用 Longbridge 模拟账户进行开发和测试。
> 不要使用真实股票账户的 API Key、App Secret 或 Access Token，也不要将任何凭证提交到代码仓库。

| 配置项 | 必填 | 默认值 | 说明 |
| :--- | :---: | :---: | :--- |
| `LONGBRIDGE_APP_KEY` | 是 | 无 | Longbridge App Key |
| `LONGBRIDGE_APP_SECRET` | 是 | 无 | Longbridge App Secret |
| `LONGBRIDGE_ACCESS_TOKEN` | 是 | 无 | Longbridge Access Token |

示例：

```dotenv
LONGBRIDGE_APP_KEY=你的AppKey
LONGBRIDGE_APP_SECRET=你的AppSecret
LONGBRIDGE_ACCESS_TOKEN=你的AccessToken
```

## 🎉 使用

### 指令表

| 指令 | 权限 | 需要@ | 范围 | 说明 |
| :--- | :--- | :--- | :--- | :--- |
| `/stock quote <SYMBOL>...` | 群员 | 否 | 群聊、私聊 | 查询一个或多个标的的实时行情 |
| `/stock quick <COMMAND>` | 群员 | 否 | 群聊、私聊 | 管理快捷标的 |
| `/stock rank [TYPE MARKET COUNT]` | 群员 | 否 | 群聊、私聊 | 查询 Longbridge 市场榜单 |
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
