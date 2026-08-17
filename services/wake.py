import json
import asyncio
import re
import httpx
from datetime import datetime, timedelta, timezone
from config import cfg
from services import reporting, bark, timeline, xinchao_client

CN_TZ = timezone(timedelta(hours=8))


def _log(msg):
    print(f"[{_now_cn().strftime('%Y-%m-%d %H:%M:%S')}] [wake] {msg}", flush=True)


def _now_cn():
    return datetime.now(CN_TZ)


def _is_daytime():
    hour = _now_cn().hour
    start, end = cfg.WAKE_DAY_START_HOUR, cfg.WAKE_DAY_END_HOUR
    if start == end:
        return True
    if start < end:
        return start <= hour < end
    return hour >= start or hour < end


def _wake_after_minutes():
    return cfg.DAY_WAKE_AFTER_MINUTES if _is_daytime() else cfg.NIGHT_WAKE_AFTER_MINUTES


def _check_interval_minutes():
    return cfg.DAY_CHECK_INTERVAL_MINUTES if _is_daytime() else cfg.NIGHT_CHECK_INTERVAL_MINUTES


def _get_last_user_time():
    """从时间线找最后一条真实用户消息时间（中国时区）。"""
    timeline_msgs = timeline.load_timeline()
    for m in reversed(timeline_msgs):
        if m.get("role") == "user":
            content = str(m.get("content", ""))
            match = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})[ T]?(\d{1,2})[:：](\d{2})", content)
            if match:
                try:
                    y, mo, d, h, mi = map(int, match.groups())
                    return datetime(y, mo, d, h, mi, tzinfo=CN_TZ)
                except Exception:
                    pass
    return None


def _should_wake():
    last = _get_last_user_time()
    if not last:
        return False
    diff_min = (_now_cn() - last).total_seconds() / 60
    return diff_min >= _wake_after_minutes()


_WEATHER_CODE = {
    0: "晴朗", 1: "大致晴朗", 2: "局部多云", 3: "阴天", 45: "有雾", 48: "雾凇",
    51: "小毛毛雨", 53: "中等毛毛雨", 55: "较强毛毛雨", 61: "小雨", 63: "中雨", 65: "大雨",
    71: "小雪", 73: "中雪", 75: "大雪", 80: "阵雨", 81: "较强阵雨", 82: "强阵雨",
    95: "雷暴", 96: "雷暴伴小冰雹", 99: "雷暴伴大冰雹",
}


async def _fetch_weather():
    if not cfg.WEATHER_ENABLED:
        return ""
    try:
        lat, lon = float(cfg.WEATHER_LAT), float(cfg.WEATHER_LON)
    except (TypeError, ValueError):
        return ""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat, "longitude": lon,
        "current": "temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,weather_code,wind_speed_10m",
        "daily": "sunrise,sunset", "timezone": "auto", "forecast_days": "1",
        "temperature_unit": "celsius", "wind_speed_unit": "kmh",
    }
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
        cur = data.get("current", {})
        daily = data.get("daily", {})
        code = _WEATHER_CODE.get(cur.get("weather_code"), f"代码{cur.get('weather_code')}")
        lines = [
            "## 天气信息",
            f"- 位置：{cfg.WEATHER_LOCATION_NAME}",
            f"- 当前：{code}，{cur.get('temperature_2m')}°C，体感 {cur.get('apparent_temperature')}°C",
            f"- 湿度：{cur.get('relative_humidity_2m')}%",
            f"- 降雨：{cur.get('precipitation')}mm",
            f"- 风速：{cur.get('wind_speed_10m')}km/h",
        ]
        if daily.get("sunrise") and daily.get("sunset"):
            lines.append(f"- 日出/日落：{daily['sunrise'][0]} / {daily['sunset'][0]}")
        return "\n".join(lines)
    except Exception:
        return ""


def _build_wake_prompt(current_time, diff_min, check_result, mood_text, weather=""):
    return f"""
## 最高优先级规则
1. 这是一次后台自动唤醒，不是用户发起的对话。你没有收到任何新消息。
2. 你的唯一任务是决定是否主动联系用户。不能生成对话回复。
3. 输出格式必须严格遵守以下二选一。

## 唤醒信息
- 当前时间：{current_time}
- 距离用户最后一条消息：{diff_min:.0f} 分钟

## 查岗信息（她此刻的手机状态）
{check_result}

## 心潮动态状态（十二维驱动力+念头池+疲惫）
{mood_text}

{weather}

## 输出格式
- 如果想联系用户，直接写你想说的话。系统会自动打包成手机推送发送。可以是一句话，也可以第一行作为标题、第二行作为正文。
- 如果不想联系，只输出：[NO_ACTION]，可附带简短原因（10字以内）。
- 如果你想写日记，可以额外输出 [DIARY]...[/DIARY]。
"""


def _extract_diary(text):
    diary_blocks = re.findall(r"\[DIARY\]([\s\S]*?)\[/DIARY\]", text)
    remaining = re.sub(r"\[DIARY\][\s\S]*?\[/DIARY\]", "", text).strip()
    return diary_blocks, remaining


def _save_diary(content):
    if not cfg.DIARY_ENABLED or not content:
        return False
    from pathlib import Path
    diary_dir = Path(cfg.DIARY_DIR)
    diary_dir.mkdir(exist_ok=True)
    now = _now_cn()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%Y-%m-%d %H:%M")
    file = diary_dir / f"{date_str}.md"
    with open(file, "a", encoding="utf-8") as f:
        f.write(f"\n\n## {time_str}\n\n{content}\n")
    return True


def _parse_push_lines(text):
    """清洗推送内容：剥[BARK]标签、清标题/正文前缀、截断、标题保护。"""
    t = text.strip()
    bark_match = re.search(r"\[BARK\]([\s\S]*?)\[/BARK\]", t)
    if bark_match:
        t = bark_match[1].strip()
    else:
        t = re.sub(r"^\[BARK\]\s*", "", t)
        t = re.sub(r"\s*\[/BARK\]$", "", t)
    t = re.sub(r"^标题[：:]\s*", "", t, flags=re.M)
    t = re.sub(r"^正文[：:]\s*", "", t, flags=re.M)

    lines = [l.strip() for l in t.split("\n") if l.strip()]
    if not lines:
        return None, None
    if len(lines) == 1:
        title, body = "来自AI", lines[0]
    elif len(lines) == 2:
        title, body = lines[0], lines[1]
    else:
        title, body = lines[0], " ".join(lines[1:])

    if len(body) > 500:
        body = body[:497] + "..."
    title = title or "来自伴侣"
    if re.match(r"^\d", title):
        title = "来自伴侣｜" + title
    return title, body


async def run_wake_once():
    """执行一次自动唤醒。查岗 + 天气 + 心潮状态注入 + LLM决定 + Bark推送。"""
    if not _should_wake():
        last = _get_last_user_time()
        if last:
            diff = (_now_cn() - last).total_seconds() / 60
            _log(f"检查唤醒：未到时间（距最后消息 {diff:.0f} 分钟，需 {_wake_after_minutes()} 分钟）")
        else:
            _log("检查唤醒：时间线无用户消息记录，暂不唤醒")
        return {"woke": False, "reason": "未到唤醒时间"}

    _log("触发唤醒：已超过静默时间，开始执行唤醒流程")

    check_data = reporting.get_summary()
    check_result = _fmt_check(check_data)
    _log("已获取查岗数据")

    weather = await _fetch_weather()
    _log("已获取天气数据" if weather else "天气未启用或获取失败")

    mood_text = xinchao_client.get_mood_text()
    _log("已获取心潮状态")

    recent_ctx = timeline.get_recent_context()

    now_str = _now_cn().strftime("%Y-%m-%d %H:%M")
    last = _get_last_user_time()
    diff_min = (_now_cn() - last).total_seconds() / 60 if last else 0
    prompt = _build_wake_prompt(now_str, diff_min, check_result, mood_text, weather)

    if not cfg.TARGET_API_URL or not cfg.TARGET_API_KEY:
        _log("错误：未配置LLM，无法唤醒")
        return {"woke": True, "error": "未配置LLM"}

    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": f"以下是你与用户最近的聊天记录，仅供回忆。你现在处于后台自主唤醒状态。\n\n{recent_ctx}"},
    ]

    _log("调用LLM决定是否联系用户...")
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            cfg.TARGET_API_URL,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {cfg.TARGET_API_KEY}"},
            json={"model": cfg.MODEL_NAME, "messages": messages, "temperature": 0.8, "stream": False},
        )
        data = resp.json()

    raw_text = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
    _log(f"LLM返回：{raw_text[:200]}")

    diary_blocks, remaining = _extract_diary(raw_text)
    diary_saved = _save_diary("\n".join(diary_blocks))
    if diary_blocks:
        _log(f"已保存日记（{len(diary_blocks)}段）")

    if not remaining:
        event_content = f"自动唤醒：本次未发送推送｜原因：{'只写日记' if diary_saved else '模型空回复'}"
        _log(event_content)
        timeline.append_special_event(event_content)
        return {"woke": True, "pushed": False, "reason": event_content}

    if remaining.startswith("[NO_ACTION]"):
        reason = remaining.replace("[NO_ACTION]", "").strip()[:20]
        event_content = f"自动唤醒：本次未发送推送｜原因：{reason}" if reason else "自动唤醒：本次未发送推送"
        _log(event_content)
        timeline.append_special_event(event_content)
        return {"woke": True, "pushed": False, "reason": event_content}

    title, body = _parse_push_lines(remaining)
    if not title or not body:
        event_content = "自动唤醒：本次未发送推送｜原因：推送内容为空"
        _log(event_content)
        timeline.append_special_event(event_content)
        return {"woke": True, "pushed": False, "reason": event_content}

    _log(f"发送Bark推送：{title}｜{body[:100]}")
    result = bark.bark_alert(title, body)
    if result.get("ok") or result.get("code") == 200:
        event_content = f"自动唤醒：刚刚给用户发了Bark推送：{title}｜{body}"
        _log("Bark推送成功")
    else:
        event_content = f"自动唤醒：本次未发送推送｜原因：Bark推送失败：{result}"
        _log(f"Bark推送失败：{result}")
    timeline.append_special_event(event_content)
    return {"woke": True, "pushed": True, "title": title, "body": body}


def _fmt_check(data):
    lines = []
    if data.get("last_update"):
        lines.append(f"采集时间：{data['last_update']}")
    apps = data.get("recent_apps", [])
    lines.append(f"最近打开：{', '.join(apps)}" if apps else "暂无记录")
    ses = data.get("sessions", {})
    if ses:
        for app, secs in sorted(ses.items(), key=lambda x: x[1], reverse=True):
            m, s = divmod(secs, 60)
            lines.append(f" {app}: {m}分{s}秒")
    if data.get("battery"):
        lines.append(f"电量：{data['battery']}%")
    if data.get("location"):
        lines.append(f"位置：{data['location']}")
    if data.get("weather"):
        lines.append(f"天气：{data['weather']}")
    if data.get("steps"):
        lines.append(f"步数：{data['steps']}")
    return "\n".join(lines)


async def wake_loop():
    """定时循环，按间隔执行自动唤醒。"""
    _log(f"唤醒循环已启动，检查间隔 {_check_interval_minutes()} 分钟")
    while True:
        try:
            await run_wake_once()
        except Exception as e:
            _log(f"唤醒循环出错：{e}")
        await asyncio.sleep(_check_interval_minutes() * 60)
