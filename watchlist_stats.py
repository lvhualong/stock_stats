# -*- coding: utf-8 -*-
"""脚本 1:自选股每日分析。

对 config.WATCHLIST 里的每只股票输出 5 个维度:
  1) 行情涨跌   2) 技术指标(含均线锚定买点)   3) 资金流向
  4) 估值/财务   5) 公司公告/新闻

结果存档到 info/<日期>/watchlist.{json,md},并推送到企业微信群。
运行:python watchlist_stats.py
"""
import pandas as pd

import config
from common import data, indicators, wecom
from common.archive import save, now_bj


def _num(x):
    try:
        return float(x)
    except Exception:
        return None


def analyze_one(code, name):
    out = {"code": code, "name": name}

    # 1) 行情
    spot = data.get_spot_one(code)
    out["quote"] = {
        "最新价": _num(spot.get("最新价")),
        "涨跌幅": _num(spot.get("涨跌幅")),
        "成交额": _num(spot.get("成交额")),
        "换手率": _num(spot.get("换手率")),
    }

    # 2) 技术指标(均线锚定买点)
    hist = data.get_hist(code)
    out["tech"] = indicators.analyze(hist)

    # 3) 资金流向(取最新一日主力净流入)
    ff = data.get_fund_flow_individual(code)
    if ff is not None and not ff.empty:
        last = ff.iloc[-1].to_dict()
        main = None
        for key in ["主力净流入-净额", "主力净流入", "今日主力净流入-净额"]:
            if key in last:
                main = _num(last[key])
                break
        out["fund_flow"] = {"日期": str(last.get("日期", "")), "主力净流入": main}
    else:
        out["fund_flow"] = {}

    # 4) 估值(PE_TTM / PB / 总市值)
    out["valuation"] = data.get_valuation(code) or {}

    # 5) 公告 / 新闻
    news = data.get_news(code, limit=3)
    items = []
    if news is not None and not news.empty:
        for _, r in news.iterrows():
            items.append({
                "title": str(r.get("新闻标题", "")).strip(),
                "time": str(r.get("发布时间", "")).strip(),
            })
    out["news"] = items
    return out


def to_markdown(results):
    d = now_bj().strftime("%Y-%m-%d")
    lines = ["# 📊 自选股日报 %s" % d, ""]
    for r in results:
        q = r.get("quote", {})
        chg = q.get("涨跌幅")
        emoji = "🔴" if (chg or 0) > 0 else ("🟢" if (chg or 0) < 0 else "⚪")
        price = q.get("最新价")
        lines.append("## %s %s(%s)" % (emoji, r["name"], r["code"]))
        if price is not None:
            amt = q.get("成交额")
            amt_str = "%.1f亿" % (amt / 1e8) if amt else "—"
            lines.append("> 现价 **%.2f**  涨跌 **%+.2f%%**  成交 %s  换手 %s%%" % (
                price, chg or 0, amt_str, q.get("换手率") if q.get("换手率") is not None else "—"))

        t = r.get("tech", {})
        if t.get("ok"):
            lines.append("- **技术**:%s" % " / ".join(t.get("signals", []) or ["—"]))
            ma = "MA5 %.2f · MA20 %.2f · MA60 %.2f" % (t["ma5"] or 0, t["ma20"] or 0, t["ma60"] or 0)
            lines.append("  - 均线:%s;RSI %.0f" % (ma, t.get("rsi14") or 0))
            if t.get("buy_hint"):
                lines.append("  - 🎯 买点:%s" % t["buy_hint"])
        else:
            lines.append("- **技术**:%s" % t.get("note", "—"))

        ff = r.get("fund_flow", {})
        if ff.get("主力净流入") is not None:
            v = ff["主力净流入"] / 1e8
            lines.append("- **资金**:主力净流入 %+.2f 亿(%s)" % (v, ff.get("日期", "")))

        val = r.get("valuation", {})
        if val.get("PE_TTM") is not None or val.get("PB") is not None:
            mv = val.get("总市值")  # 百度返回单位:亿元
            mv_str = ("  · 市值 %.0f亿" % mv) if mv else ""
            lines.append("- **估值**:PE(TTM) %s · PB %s%s" % (
                _fmt(val.get("PE_TTM")), _fmt(val.get("PB")), mv_str))

        if r.get("news"):
            lines.append("- **新闻**:")
            for n in r["news"]:
                lines.append("  - %s" % n["title"])
        lines.append("")
    lines.append("> 数据来源 akshare,仅供研究,不构成投资建议。")
    return "\n".join(lines)


def _fmt(x):
    return "%.2f" % x if isinstance(x, (int, float)) else "—"


def main():
    results = [analyze_one(code, name) for code, name in config.WATCHLIST]
    md = to_markdown(results)
    save(config.INFO_ROOT, "watchlist", json_obj=results, markdown=md)
    wecom.send_markdown(md, config.WECOM_WEBHOOK)
    print(md)


if __name__ == "__main__":
    main()
