# -*- coding: utf-8 -*-
"""企业微信群机器人推送。

群机器人 webhook:在企业微信群 -> 右上角 -> 添加群机器人 -> 复制 webhook 地址,
取出 key,设为环境变量 WECOM_WEBHOOK(完整地址)。

注意限制(企业微信官方):
- markdown 内容最长 4096 字节,超出会被截断/报错,这里自动分片发送。
- 每个机器人每分钟最多 20 条,分片之间 sleep 一下。
"""
import time
import json
import requests


MAX_BYTES = 4000  # 留点余量,4096 是硬上限


def _split_by_bytes(text, limit=MAX_BYTES):
    """按行切分,保证每片 utf-8 字节数不超过 limit。"""
    chunks, cur = [], ""
    for line in text.split("\n"):
        candidate = (cur + "\n" + line) if cur else line
        if len(candidate.encode("utf-8")) > limit and cur:
            chunks.append(cur)
            cur = line
        else:
            cur = candidate
    if cur:
        chunks.append(cur)
    return chunks


def send_markdown(content, webhook=None):
    """发送 markdown 消息到企业微信群。webhook 为空则只打印(本地调试)。"""
    if not webhook:
        print("[wecom] 未配置 WECOM_WEBHOOK,仅打印内容:\n" + content)
        return False

    ok = True
    chunks = _split_by_bytes(content)
    for i, chunk in enumerate(chunks):
        payload = {"msgtype": "markdown", "markdown": {"content": chunk}}
        try:
            r = requests.post(webhook, json=payload, timeout=15)
            data = r.json()
            if data.get("errcode") != 0:
                ok = False
                print("[wecom] 第%d片发送失败: %s" % (i + 1, data))
            else:
                print("[wecom] 第%d/%d片发送成功" % (i + 1, len(chunks)))
        except Exception as e:  # noqa: BLE001
            ok = False
            print("[wecom] 第%d片发送异常: %s" % (i + 1, e))
        if len(chunks) > 1:
            time.sleep(3.5)  # 避免触发频率限制
    return ok
