# -*- coding: utf-8 -*-
"""脚本 2:大盘 + 板块每日概览。

输出:
  - 主要指数涨跌(上证/深证/创业板/沪深300/科创50/中证500)
  - 全市场涨跌家数、涨停/跌停数
  - 行业板块资金流向 Top/Bottom
  - 概念板块资金流向 Top

结果存档 info/<日期>/market.{json,md},推送企业微信群。
运行:python market_stats.py
"""
import pandas as pd

import config
from common import data, wecom
from common.archive import save, now_bj


def _num(x):
    try:
        return float(x)
    except Exception:
        return None


def collect():
    out = {}

    # 指数:用 sina 指数快照统一取
    try:
        import akshare as ak
        idx = ak.stock_zh_index_spot_sina()
    except Exception as e:  # noqa: BLE001
        print("[market] 指数快照失败: %s" % e)
        idx = pd.DataFrame()

    indices = []
    if idx is not None and not idx.empty:
        for code, name in config.INDEX_LIST:
            row = idx[idx["代码"].astype(str).str.endswith(code)]
            if not row.empty:
                r = row.iloc[0]
                indices.append({
                    "name": name,
                    "最新价": _num(r.get("最新价")),
                    "涨跌幅": _num(r.get("涨跌幅")),
                })
    out["indices"] = indices

    # 涨跌家数
    out["breadth"] = data.get_market_breadth()

    # 行业板块资金流
    ind = data.get_sector_fund_flow_rank(indicator="今日", sector_type="行业资金流")
    out["industry"] = _top_bottom(ind)

    # 概念板块资金流
    con = data.get_sector_fund_flow_rank(indicator="今日", sector_type="概念资金流")
    out["concept"] = _top_bottom(con, only_top=True)
    return out


def _top_bottom(df, n=5, only_top=False):
    """从板块资金流排名表里取净流入前 n / 后 n。"""
    if df is None or df.empty:
        return {"top": [], "bottom": []}
    col = None
    for c in df.columns:
        if "主力净流入-净额" in c or c == "今日主力净流入-净额":
            col = c
            break
    if col is None:
        # 退而求其次:找含"净额"的列
        cand = [c for c in df.columns if "净额" in c]
        col = cand[0] if cand else None
    if col is None:
        return {"top": [], "bottom": []}
    namecol = "名称" if "名称" in df.columns else df.columns[1]
    chgcol = next((c for c in df.columns if "涨跌幅" in c), None)
    df = df.copy()
    df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=[col]).sort_values(col, ascending=False)

    def pack(sub):
        rows = []
        for _, r in sub.iterrows():
            rows.append({
                "名称": str(r[namecol]),
                "主力净流入": float(r[col]),
                "涨跌幅": _num(r[chgcol]) if chgcol else None,
            })
        return rows

    top = pack(df.head(n))
    bottom = [] if only_top else pack(df.tail(n).iloc[::-1])
    return {"top": top, "bottom": bottom}


def to_markdown(o):
    d = now_bj().strftime("%Y-%m-%d")
    lines = ["# 🏛️ 大盘板块概览 %s" % d, ""]

    if o.get("indices"):
        lines.append("## 主要指数")
        for i in o["indices"]:
            chg = i.get("涨跌幅") or 0
            e = "🔴" if chg > 0 else ("🟢" if chg < 0 else "⚪")
            lines.append("- %s %s:**%.2f**(%+.2f%%)" % (e, i["name"], i.get("最新价") or 0, chg))
        lines.append("")

    b = o.get("breadth") or {}
    if b:
        lines.append("## 涨跌家数")
        lines.append("> 上涨 **%s** / 下跌 **%s** / 平盘 %s  ·  涨停 🔴%s / 跌停 🟢%s" % (
            b.get("上涨", "—"), b.get("下跌", "—"), b.get("平盘", "—"),
            b.get("涨停", "—"), b.get("跌停", "—")))
        lines.append("")

    ind = o.get("industry") or {}
    if ind.get("top"):
        lines.append("## 行业资金流(净流入前5)")
        for r in ind["top"]:
            lines.append("- %s:主力 %+.2f 亿(%+.2f%%)" % (
                r["名称"], r["主力净流入"] / 1e8, r.get("涨跌幅") or 0))
        if ind.get("bottom"):
            lines.append("\n净流出前5:")
            for r in ind["bottom"]:
                lines.append("- %s:主力 %+.2f 亿(%+.2f%%)" % (
                    r["名称"], r["主力净流入"] / 1e8, r.get("涨跌幅") or 0))
        lines.append("")

    con = o.get("concept") or {}
    if con.get("top"):
        lines.append("## 概念资金流(净流入前5)")
        for r in con["top"]:
            lines.append("- %s:主力 %+.2f 亿(%+.2f%%)" % (
                r["名称"], r["主力净流入"] / 1e8, r.get("涨跌幅") or 0))
        lines.append("")

    lines.append("> 数据来源 akshare,仅供研究,不构成投资建议。")
    return "\n".join(lines)


def main():
    o = collect()
    md = to_markdown(o)
    save(config.INFO_ROOT, "market", json_obj=o, markdown=md)
    wecom.send_markdown(md, config.WECOM_WEBHOOK)
    print(md)


if __name__ == "__main__":
    main()
