# -*- coding: utf-8 -*-
"""脚本 3:每日热门榜单。

输出:
  - 涨幅榜 / 跌幅榜 Top N(全市场快照)
  - 成交额榜 Top N
  - 当日涨停板池(数量 + 连板梯队)
  - 龙虎榜上榜股(机构/游资动向)

结果存档 info/<日期>/hotlist.{json,md},推送企业微信群。
运行:python hotlist_stats.py
"""
import pandas as pd

import config
from common import data, wecom
from common.archive import save, now_bj, date_str


def _num(x):
    try:
        return float(x)
    except Exception:
        return None


def _rank(df, col, ascending=False, n=10):
    if df is None or df.empty or col not in df.columns:
        return []
    df = df.copy()
    df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=[col]).sort_values(col, ascending=ascending).head(n)
    rows = []
    for _, r in df.iterrows():
        rows.append({
            "代码": str(r.get("代码", "")),
            "名称": str(r.get("名称", "")),
            "最新价": _num(r.get("最新价")),
            "涨跌幅": _num(r.get("涨跌幅")),
            "成交额": _num(r.get("成交额")),
        })
    return rows


def collect():
    n = config.TOP_N
    out = {}

    spot = data.get_spot_all()
    out["gainers"] = _rank(spot, "涨跌幅", ascending=False, n=n)
    out["losers"] = _rank(spot, "涨跌幅", ascending=True, n=n)
    out["turnover"] = _rank(spot, "成交额", ascending=False, n=n)

    # 涨停池
    ds = date_str()
    zt = data.get_limit_up_pool(ds)
    zt_rows = []
    if zt is not None and not zt.empty:
        # 连板数列名常见为 "连板数"
        lb_col = next((c for c in zt.columns if "连板" in c), None)
        for _, r in zt.iterrows():
            zt_rows.append({
                "代码": str(r.get("代码", "")),
                "名称": str(r.get("名称", "")),
                "连板": int(_num(r.get(lb_col)) or 1) if lb_col else None,
            })
    out["limit_up"] = {"count": len(zt_rows), "list": zt_rows}

    # 龙虎榜(当日)
    lhb = data.get_dragon_tiger(ds, ds)
    lhb_rows = []
    if lhb is not None and not lhb.empty:
        name_col = next((c for c in lhb.columns if c in ("名称", "股票名称")), None)
        code_col = next((c for c in lhb.columns if c in ("代码", "股票代码")), None)
        reason_col = next((c for c in lhb.columns if "解读" in c or "原因" in c or "上榜" in c), None)
        seen = set()
        for _, r in lhb.iterrows():
            code = str(r.get(code_col, "")) if code_col else ""
            if code in seen:
                continue
            seen.add(code)
            lhb_rows.append({
                "代码": code,
                "名称": str(r.get(name_col, "")) if name_col else "",
                "原因": str(r.get(reason_col, "")) if reason_col else "",
            })
            if len(lhb_rows) >= config.TOP_N:
                break
    out["dragon_tiger"] = lhb_rows
    return out


def to_markdown(o):
    d = now_bj().strftime("%Y-%m-%d")
    lines = ["# 🔥 热门榜单 %s" % d, ""]

    def block(title, rows, with_amt=False):
        if not rows:
            return
        lines.append("## %s" % title)
        for r in rows:
            amt = ("  成交 %.1f亿" % (r["成交额"] / 1e8)) if (with_amt and r.get("成交额")) else ""
            lines.append("- %s(%s)  %.2f  **%+.2f%%**%s" % (
                r["名称"], r["代码"], r.get("最新价") or 0, r.get("涨跌幅") or 0, amt))
        lines.append("")

    block("📈 涨幅榜", o.get("gainers"))
    block("📉 跌幅榜", o.get("losers"))
    block("💰 成交额榜", o.get("turnover"), with_amt=True)

    lu = o.get("limit_up") or {}
    if lu.get("count"):
        lines.append("## 🚀 涨停板(%d 只)" % lu["count"])
        # 连板梯队:按连板数降序展示前几只
        lst = [x for x in lu.get("list", []) if x.get("连板")]
        lst = sorted(lst, key=lambda x: x["连板"], reverse=True)[:8]
        for x in lst:
            lines.append("- %s(%s)  %d 连板" % (x["名称"], x["代码"], x["连板"]))
        lines.append("")

    dt = o.get("dragon_tiger") or []
    if dt:
        lines.append("## 🐉 龙虎榜")
        for r in dt:
            reason = ("  · %s" % r["原因"]) if r.get("原因") else ""
            lines.append("- %s(%s)%s" % (r["名称"], r["代码"], reason))
        lines.append("")

    lines.append("> 数据来源 akshare,仅供研究,不构成投资建议。")
    return "\n".join(lines)


def main():
    o = collect()
    md = to_markdown(o)
    save(config.INFO_ROOT, "hotlist", json_obj=o, markdown=md)
    wecom.send_markdown(md, config.WECOM_WEBHOOK)
    print(md)


if __name__ == "__main__":
    main()
