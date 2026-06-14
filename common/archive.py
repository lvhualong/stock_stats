# -*- coding: utf-8 -*-
"""结果存档:仿 arXiv-stats 的 info/<日期>/ 结构。"""
import os
import json
from datetime import datetime

try:
    from zoneinfo import ZoneInfo  # py3.9+
    _TZ = ZoneInfo("Asia/Shanghai")
except Exception:  # pragma: no cover
    _TZ = None


def now_bj():
    """北京时间 now(GitHub runner 是 UTC,这里统一成北京时间)。"""
    return datetime.now(_TZ) if _TZ else datetime.now()


def date_str():
    """形如 20240614,用于 akshare 日期参数。"""
    return now_bj().strftime("%Y%m%d")


def info_dir(root="info"):
    """info/YYYY-MM/DD 目录,自动创建。"""
    d = now_bj()
    path = os.path.join(root, d.strftime("%Y-%m"), d.strftime("%d"))
    os.makedirs(path, exist_ok=True)
    return path


def save(root, name, *, json_obj=None, markdown=None):
    """把结构化结果与 markdown 都落盘到 info 目录。"""
    d = info_dir(root)
    if json_obj is not None:
        with open(os.path.join(d, name + ".json"), "w", encoding="utf-8") as fp:
            json.dump(json_obj, fp, ensure_ascii=False, indent=2)
    if markdown is not None:
        with open(os.path.join(d, name + ".md"), "w", encoding="utf-8") as fp:
            fp.write(markdown)
    return d
