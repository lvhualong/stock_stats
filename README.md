# stock_stats

A 股每日自动分析 + 企业微信群推送。仿 [arXiv-stats](https://github.com/lvhualong/arXiv-stats) 用 GitHub Actions 定时维护。

每个交易日收盘后(默认北京时间 15:35)自动运行三个脚本,把结果存档到 `info/<日期>/`,并推送 markdown 到企业微信群机器人。

## 三个脚本

| 脚本 | 内容 |
|------|------|
| `watchlist_stats.py` | **自选股**(`config.WATCHLIST`):行情涨跌 / 技术指标(均线锚定买点)/ 资金流向 / 估值 / 公告新闻 |
| `market_stats.py` | **大盘+板块**:主要指数、涨跌家数、行业与概念板块资金流向 |
| `hotlist_stats.py` | **热门榜单**:涨幅榜/跌幅榜/成交额榜、涨停板梯队、龙虎榜 |

数据源:[akshare](https://akshare.akfamily.xyz)(免费、无需 key)。技术指标(MA/MACD/RSI/BOLL)纯 pandas 实现。

## 本地运行

```bash
pip install -r requirements.txt

# 不配 webhook 时只在终端打印结果
python watchlist_stats.py
python market_stats.py
python hotlist_stats.py

# 配置企业微信群机器人后推送
export WECOM_WEBHOOK="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=你的key"
python watchlist_stats.py
```

## 配置

- **自选股**:编辑 `config.py` 的 `WATCHLIST`。
- **指数/榜单条数**:`config.py` 的 `INDEX_LIST` / `TOP_N`。

## 部署到 GitHub Actions

1. 把本目录推到一个 GitHub 仓库。
2. 在企业微信目标群:右上角 → 添加群机器人 → 复制 Webhook 地址。
3. 仓库 Settings → Secrets and variables → Actions → New repository secret:
   - `WECOM_WEBHOOK` = 上面复制的完整 webhook 地址(必填)。
   - `ACTION_TOKEN` =(可选)个人 PAT,仅当需要 push 触发其它 workflow 时。不设则用默认 `github.token`。
4. workflow 默认每个交易日 **07:35 UTC(北京 15:35)** 运行;也可在 Actions 页面手动 `Run workflow`。

> 注:GitHub schedule 在节假日不会判断 A 股是否休市,非交易日脚本会因无新数据而推送空/旧榜单,可按需在脚本里加交易日历过滤。

## 免责声明

仅用于学习研究,不构成任何投资建议。
