# -*- coding: utf-8 -*-
"""技术指标 —— 纯 pandas/numpy 实现,避免 TA-Lib 的 C 依赖(CI 友好)。

输入统一为 akshare 历史日线 DataFrame(含 中文列名:收盘/最高/最低)。
所有函数对数据不足的情况都返回 None / NaN,调用方需判空。
"""
import numpy as np
import pandas as pd


def _close(df):
    return pd.to_numeric(df["收盘"], errors="coerce")


def sma(series, n):
    return series.rolling(n).mean()


def ema(series, n):
    return series.ewm(span=n, adjust=False).mean()


def rsi(series, n=14):
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(n).mean()
    loss = (-delta.clip(upper=0)).rolling(n).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def macd(series, fast=12, slow=26, signal=9):
    dif = ema(series, fast) - ema(series, slow)
    dea = ema(dif, signal)
    hist = (dif - dea) * 2
    return dif, dea, hist


def boll(series, n=20, k=2):
    mid = sma(series, n)
    std = series.rolling(n).std()
    return mid + k * std, mid, mid - k * std


def _last(series):
    """最后一个非 NaN 值,取不到返回 None。"""
    s = series.dropna()
    return float(s.iloc[-1]) if len(s) else None


def analyze(df):
    """对历史日线做一揽子技术分析,返回结构化 dict + 文字提示 + 均线锚定的买点。

    买点遵循"必须用均线等可计算锚"的原则:给出回踩 MA20 / MA60 的支撑参考价,
    而不是凭手感画线。
    """
    if df is None or df.empty or len(df) < 30:
        return {"ok": False, "note": "历史数据不足,跳过技术分析"}

    close = _close(df).reset_index(drop=True)
    price = _last(close)

    ma5, ma20, ma60 = _last(sma(close, 5)), _last(sma(close, 20)), _last(sma(close, 60))
    rsi14 = _last(rsi(close, 14))
    dif, dea, hist = macd(close)
    dif_v, dea_v, hist_v = _last(dif), _last(dea), _last(hist)
    up, mid, low = boll(close)
    boll_up, boll_mid, boll_low = _last(up), _last(mid), _last(low)

    # ---- 多空研判 ----
    signals = []
    if ma5 and ma20 and ma60:
        if price > ma5 > ma20 > ma60:
            trend = "多头排列(强势)"
        elif price < ma5 < ma20 < ma60:
            trend = "空头排列(弱势)"
        else:
            trend = "均线纠缠(震荡)"
        signals.append(trend)

    if dif_v is not None and dea_v is not None:
        if dif_v > dea_v and hist_v and hist_v > 0:
            signals.append("MACD 金叉/红柱(偏多)")
        elif dif_v < dea_v and hist_v and hist_v < 0:
            signals.append("MACD 死叉/绿柱(偏空)")

    if rsi14 is not None:
        if rsi14 >= 70:
            signals.append("RSI 超买(>70,警惕回调)")
        elif rsi14 <= 30:
            signals.append("RSI 超卖(<30,关注反弹)")

    # ---- 均线锚定的买点 / 止损参考 ----
    buy_hint = None
    if price and ma20 and ma60:
        if price > ma20:
            # 强势:回踩 MA20 是第一支撑买点,跌破 MA60 止损
            buy_hint = "回踩 MA20≈%.2f 附近可关注;跌破 MA60≈%.2f 减仓/止损" % (ma20, ma60)
        else:
            # 走弱:站回 MA20 才转强
            buy_hint = "现价已破 MA20≈%.2f;站回 MA20 上方再考虑,下方支撑看 MA60≈%.2f" % (ma20, ma60)

    return {
        "ok": True,
        "price": price,
        "ma5": ma5, "ma20": ma20, "ma60": ma60,
        "rsi14": rsi14,
        "macd": {"dif": dif_v, "dea": dea_v, "hist": hist_v},
        "boll": {"up": boll_up, "mid": boll_mid, "low": boll_low},
        "signals": signals,
        "buy_hint": buy_hint,
    }
