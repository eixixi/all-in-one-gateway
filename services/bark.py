import requests
from config import cfg


def bark_alert(title="", content=""):
    if not content:
        return "内容不能为空"
    if not cfg.BARK_KEY:
        return "Bark Key 未配置"
    payload = {
        "title": title or "祁宴",
        "body": content,
        "device_key": cfg.BARK_KEY,
        "icon": cfg.CUSTOM_ICON_URL or None,
    }
    try:
        r = requests.post("https://api.day.app/push", json=payload, timeout=10)
        return "推送成功" if r.status_code == 200 else "推送失败"
    except Exception as e:
        return f"推送异常：{e}"
