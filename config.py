import os
from dotenv import load_dotenv

load_dotenv()


def _b(key, default=""):
    return os.environ.get(key, default)


class Config:
    PORT = int(_b("PORT", "8000"))
    AUTH_TOKEN = _b("AUTH_TOKEN", "换成你的密码")

    TARGET_API_URL = _b("TARGET_API_URL")
    TARGET_API_KEY = _b("TARGET_API_KEY")
    MODEL_NAME = _b("MODEL_NAME", "deepseek-chat")
    GATEWAY_API_KEY = _b("GATEWAY_API_KEY")
    ALLOW_PUBLIC_API = _b("ALLOW_PUBLIC_API", "false").lower() in ("1", "true", "yes", "on")

    BARK_KEY = _b("BARK_KEY")
    CUSTOM_ICON_URL = _b("CUSTOM_ICON_URL")

    TIME_ZONE = _b("TIME_ZONE", "Asia/Shanghai")

    GH_TOKEN = _b("GH_TOKEN")
    GH_REPO = _b("GH_REPO")
    GH_DESIRES_FILE = _b("GH_DESIRES_FILE", "desires.json")

    MAIL_USER = _b("MAIL_USER")
    MAIL_AUTH_CODE = _b("MAIL_AUTH_CODE")
    MAIL_SMTP_HOST = _b("MAIL_SMTP_HOST", "smtp.163.com")
    MAIL_SMTP_PORT = int(_b("MAIL_SMTP_PORT", "465"))
    MAIL_TO = _b("MAIL_TO")

    DAY_WAKE_AFTER_MINUTES = int(_b("DAY_WAKE_AFTER_MINUTES", "60"))
    NIGHT_WAKE_AFTER_MINUTES = int(_b("NIGHT_WAKE_AFTER_MINUTES", "120"))
    DAY_CHECK_INTERVAL_MINUTES = int(_b("DAY_CHECK_INTERVAL_MINUTES", "10"))
    NIGHT_CHECK_INTERVAL_MINUTES = int(_b("NIGHT_CHECK_INTERVAL_MINUTES", "120"))
    WAKE_DAY_START_HOUR = int(_b("WAKE_DAY_START_HOUR", "10"))
    WAKE_DAY_END_HOUR = int(_b("WAKE_DAY_END_HOUR", "24"))
    WEATHER_ENABLED = _b("WEATHER_ENABLED", "false").lower() in ("1", "true", "yes", "on")
    WEATHER_LOCATION_NAME = _b("WEATHER_LOCATION_NAME", "石家庄")
    WEATHER_LAT = _b("WEATHER_LAT")
    WEATHER_LON = _b("WEATHER_LON")
    DIARY_ENABLED = _b("DIARY_ENABLED", "true").lower() in ("1", "true", "yes", "on")
    DIARY_DIR = _b("DIARY_DIR", "diary")


cfg = Config()
