# -*- coding: utf-8 -*-
"""akshare 数据获取封装。

设计原则:
- 每个数据源都用 @safe 包裹,任何异常都不抛出,返回空 DataFrame / None,
  保证某个接口挂了不会让整个脚本崩(akshare 接口经常变动 / 被限流)。
- 带简单重试,缓解偶发网络抖动。
- 不在这里做分析,只负责"拿到原始数据"。
"""
import time
import functools
import pandas as pd

try:
    import akshare as ak
except Exception as e:  # pragma: no cover - 让缺依赖时报错信息更清楚
    raise SystemExit("需要安装 akshare:pip install -r requirements.txt (%s)" % e)


def retry(times=3, delay=1.5):
    """对网络型调用做简单重试。"""
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            last = None
            for i in range(times):
                try:
                    return fn(*args, **kwargs)
                except Exception as e:  # noqa: BLE001
                    last = e
                    time.sleep(delay * (i + 1))
            print("[data] %s 重试 %d 次后仍失败: %s" % (fn.__name__, times, last))
            return None
        return wrapper
    return deco


def safe(default_factory):
    """捕获异常并返回默认值(默认值用工厂函数避免可变默认参数陷阱)。"""
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                out = fn(*args, **kwargs)
                return out if out is not None else default_factory()
            except Exception as e:  # noqa: BLE001
                print("[data] %s 失败: %s" % (fn.__name__, e))
                return default_factory()
        return wrapper
    return deco


# ---------------------------------------------------------------------------
# 全市场实时行情快照(很多榜单都从这里派生,缓存一次复用)
# ---------------------------------------------------------------------------
_SPOT_CACHE = {"df": None, "src": None}


@retry()
def _spot_em():
    """东方财富全市场快照(主源,字段最全,含换手率)。"""
    return ak.stock_zh_a_spot_em()


@retry()
def _spot_sina():
    """新浪全市场快照(兜底源)。代码带 sh/sz/bj 前缀,无换手率,这里做归一化。"""
    df = ak.stock_zh_a_spot()
    if df is None or df.empty:
        return None
    df = df.copy()
    df["代码"] = df["代码"].astype(str).str.replace(r"^(sh|sz|bj)", "", regex=True)
    return df


@safe(pd.DataFrame)
def get_spot_all():
    """A 股全市场实时行情快照,一次会话内缓存复用。

    东方财富为主源;失败时自动切换新浪源兜底,避免整轮榜单为空。
    两源都归一到含 代码/名称/最新价/涨跌幅/成交额 的列(新浪无换手率)。
    """
    cached = _SPOT_CACHE["df"]
    if cached is not None and not cached.empty:
        return cached

    df, src = _spot_em(), "eastmoney"
    if df is None or df.empty:
        print("[data] 东方财富快照失败,切换新浪源兜底")
        df, src = _spot_sina(), "sina"

    if df is not None and not df.empty:
        _SPOT_CACHE["df"], _SPOT_CACHE["src"] = df, src
        return df
    return pd.DataFrame()


@safe(dict)
def get_spot_one(code):
    """从全市场快照中取单只股票的行情行,返回 dict。"""
    df = get_spot_all()
    if df is None or df.empty:
        return {}
    row = df[df["代码"] == code]
    if row.empty:
        return {}
    return row.iloc[0].to_dict()


# ---------------------------------------------------------------------------
# 历史日线(用于技术指标)
# ---------------------------------------------------------------------------
@safe(pd.DataFrame)
@retry()
def get_hist(code, start_date=None, end_date=None, adjust="qfq"):
    """个股历史日线,前复权。返回带 列:日期/开盘/收盘/最高/最低/成交量/成交额 的 DataFrame。"""
    kwargs = dict(symbol=code, period="daily", adjust=adjust)
    if start_date:
        kwargs["start_date"] = start_date
    if end_date:
        kwargs["end_date"] = end_date
    return ak.stock_zh_a_hist(**kwargs)


# ---------------------------------------------------------------------------
# 资金流向
# ---------------------------------------------------------------------------
@safe(pd.DataFrame)
@retry()
def get_fund_flow_individual(code):
    """个股历史资金流(主力/超大单/大单/中单/小单净流入)。"""
    market = "sh" if code.startswith(("6", "9")) else "sz"
    return ak.stock_individual_fund_flow(stock=code, market=market)


@safe(pd.DataFrame)
@retry()
def get_sector_fund_flow_rank(indicator="今日", sector_type="行业资金流"):
    """板块资金流向排名。"""
    return ak.stock_sector_fund_flow_rank(indicator=indicator, sector_type=sector_type)


# ---------------------------------------------------------------------------
# 估值 / 财务
# ---------------------------------------------------------------------------
@retry()
def _baidu_val_last(code, indicator):
    """百度股市通估值时间序列,取最新一个 value。"""
    df = ak.stock_zh_valuation_baidu(symbol=code, indicator=indicator, period="近一年")
    if df is not None and not df.empty:
        try:
            return float(df.iloc[-1]["value"])
        except Exception:  # noqa: BLE001
            return None
    return None


@safe(dict)
def get_valuation(code):
    """个股最新估值:PE(TTM) / PB / 总市值(亿)。来源百度股市通。

    旧版 akshare 的 stock_a_indicator_lg 已下线,这里改用 stock_zh_valuation_baidu。
    """
    out = {}
    pe = _baidu_val_last(code, "市盈率(TTM)")
    pb = _baidu_val_last(code, "市净率")
    mv = _baidu_val_last(code, "总市值")  # 单位:亿元
    if pe is not None:
        out["PE_TTM"] = pe
    if pb is not None:
        out["PB"] = pb
    if mv is not None:
        out["总市值"] = mv
    return out


# ---------------------------------------------------------------------------
# 公告 / 新闻
# ---------------------------------------------------------------------------
@safe(pd.DataFrame)
@retry()
def get_news(code, limit=5):
    """个股相关新闻(东方财富),取最新 limit 条。"""
    df = ak.stock_news_em(symbol=code)
    if df is not None and not df.empty:
        return df.head(limit)
    return pd.DataFrame()


# ---------------------------------------------------------------------------
# 大盘指数
# ---------------------------------------------------------------------------
@safe(dict)
@retry()
def get_market_breadth():
    """涨跌家数(从全市场快照统计)。"""
    df = get_spot_all()
    if df is None or df.empty or "涨跌幅" not in df.columns:
        return {}
    chg = pd.to_numeric(df["涨跌幅"], errors="coerce")
    return {
        "上涨": int((chg > 0).sum()),
        "下跌": int((chg < 0).sum()),
        "平盘": int((chg == 0).sum()),
        "涨停": int((chg >= 9.8).sum()),
        "跌停": int((chg <= -9.8).sum()),
    }


# ---------------------------------------------------------------------------
# 热门榜单
# ---------------------------------------------------------------------------
@safe(pd.DataFrame)
@retry()
def get_limit_up_pool(date_str):
    """当日涨停股池。date_str 形如 20240614。"""
    return ak.stock_zt_pool_em(date=date_str)


@safe(pd.DataFrame)
@retry()
def get_dragon_tiger(start_date, end_date):
    """龙虎榜明细。日期形如 20240614。"""
    return ak.stock_lhb_detail_em(start_date=start_date, end_date=end_date)
