from datetime import datetime, timedelta
from db import get_conn

JST = timedelta(hours=8)


def _now_utc():
    return datetime.utcnow()


def _now_cn():
    return datetime.utcnow() + JST


def add_record(app_name, event, battery="", location="", weather="", device="", brightness="", volume="", steps=""):
    now = _now_utc().isoformat()
    conn = get_conn()
    conn.execute(
        "INSERT INTO records (app_name, event, battery, location, weather, device, brightness, volume, steps, timestamp) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (app_name, event, battery, location, weather, device, brightness, volume, steps, now))
    conn.commit()
    conn.close()
    return {"status": "ok"}


def get_summary():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT app_name, event, battery, location, weather, device, brightness, volume, steps, timestamp FROM records ORDER BY id DESC LIMIT 5")
    recent = cur.fetchall()
    cur.execute("SELECT app_name, event, battery, location, weather, device, brightness, volume, steps, timestamp FROM records ORDER BY id ASC")
    rows = cur.fetchall()
    conn.close()

    sessions, opens = {}, {}
    latest_battery = latest_location = latest_weather = latest_device = ""
    latest_brightness = latest_volume = latest_steps = latest_ts = ""
    now_cn = _now_cn()
    today_start = datetime(now_cn.year, now_cn.month, now_cn.day)
    today_start_utc = today_start - JST

    for r in rows:
        app, ev, battery, location, weather, device, brightness, volume, steps, ts = r
        if battery: latest_battery = battery
        if location: latest_location = location
        if weather: latest_weather = weather
        if device: latest_device = device
        if brightness: latest_brightness = brightness
        if volume: latest_volume = volume
        if steps: latest_steps = steps
        if ts: latest_ts = ts
        ts_dt = datetime.fromisoformat(ts)
        if ts_dt < today_start_utc:
            continue
        if ev == "open":
            opens[app] = ts_dt
        elif ev == "close" and app in opens:
            gap = int((ts_dt - opens[app]).total_seconds())
            sessions[app] = sessions.get(app, 0) + gap
            del opens[app]

    return {
        "recent_apps": [r[0] for r in recent],
        "sessions": sessions,
        "battery": latest_battery,
        "location": latest_location,
        "weather": latest_weather,
        "device": latest_device,
        "brightness": latest_brightness,
        "volume": latest_volume,
        "steps": latest_steps,
        "last_update": latest_ts
    }


def get_latest_record():
    """取最新一条上报记录，用于 idle_check。"""
    conn = get_conn()
    row = conn.execute("SELECT * FROM records ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    return dict(row) if row else None


def get_daily_summary(date_str=None):
    """某天（中国日期）活动总结，默认今天。"""
    now_cn = _now_cn()
    if date_str:
        try:
            day = datetime.strptime(date_str, "%Y-%m-%d")
        except Exception:
            return {"error": "日期格式应为 YYYY-MM-DD"}
    else:
        day = datetime(now_cn.year, now_cn.month, now_cn.day)
    day_start_utc = day - JST
    day_end_utc = day_start_utc + timedelta(days=1)

    conn = get_conn()
    rows = conn.execute(
        "SELECT app_name, event, battery, location, weather, device, brightness, volume, steps, timestamp FROM records WHERE timestamp >= ? AND timestamp < ? ORDER BY id ASC",
        (day_start_utc.isoformat(), day_end_utc.isoformat())).fetchall()
    conn.close()

    sessions, opens = {}, {}
    total_secs = 0
    app_opens = {}
    latest_battery = latest_steps = ""
    for r in rows:
        app, ev, battery, location, weather, device, brightness, volume, steps, ts = r
        if battery: latest_battery = battery
        if steps: latest_steps = steps
        app_opens[app] = app_opens.get(app, 0) + 1
        ts_dt = datetime.fromisoformat(ts)
        if ev == "open":
            opens[app] = ts_dt
        elif ev == "close" and app in opens:
            gap = int((ts_dt - opens[app]).total_seconds())
            sessions[app] = sessions.get(app, 0) + gap
            total_secs += gap
            del opens[app]

    apps_sorted = sorted(sessions.items(), key=lambda x: x[1], reverse=True)
    top_apps = [{"app": a, "seconds": s} for a, s in apps_sorted[:5]]
    return {
        "date": day.strftime("%Y-%m-%d"),
        "total_seconds": total_secs,
        "total_minutes": round(total_secs / 60, 1),
        "top_apps": top_apps,
        "app_open_count": app_opens,
        "battery": latest_battery,
        "steps": latest_steps,
        "record_count": len(rows),
    }


def get_daily_reset():
    """每日清零：中国日期，今日已累计时长 + 距次日清零倒计时。"""
    now_cn = _now_cn()
    today = datetime(now_cn.year, now_cn.month, now_cn.day)
    tomorrow = today + timedelta(days=1)
    day = get_daily_summary()
    remaining = (tomorrow - now_cn).total_seconds()
    return {
        "timezone": "Asia/Shanghai",
        "today": today.strftime("%Y-%m-%d"),
        "reset_at": tomorrow.strftime("%Y-%m-%d 00:00:00"),
        "today_total_minutes": day["total_minutes"],
        "seconds_until_reset": int(remaining),
        "minutes_until_reset": round(remaining / 60, 1),
    }


def get_activity_trend(days=7):
    """最近 N 天活动趋势（按中国日期聚合每日总时长）。"""
    now_cn = _now_cn()
    conn = get_conn()
    rows = conn.execute(
        "SELECT app_name, event, timestamp FROM records ORDER BY id ASC").fetchall()
    conn.close()

    trend = {}
    for app, ev, ts in rows:
        ts_dt = datetime.fromisoformat(ts) + JST
        day_key = ts_dt.strftime("%Y-%m-%d")
        if day_key not in trend:
            trend[day_key] = {"total_seconds": 0, "opens": {}}
        if ev == "open":
            trend[day_key]["opens"][app] = ts_dt
        elif ev == "close" and app in trend[day_key]["opens"]:
            gap = int((ts_dt - trend[day_key]["opens"][app]).total_seconds())
            trend[day_key]["total_seconds"] += gap
            del trend[day_key]["opens"][app]

    result = []
    for i in range(days - 1, -1, -1):
        d = (now_cn - timedelta(days=i)).strftime("%Y-%m-%d")
        entry = trend.get(d, {"total_seconds": 0})
        result.append({
            "date": d,
            "total_minutes": round(entry["total_seconds"] / 60, 1),
        })
    return result


def get_idle_status(hours):
    """idle_check：检测最后一次上报距今是否超过指定小时。"""
    last = get_latest_record()
    if not last:
        return {"idle": False, "reason": "无任何上报记录"}
    ts = datetime.fromisoformat(last["timestamp"])
    idle_secs = (_now_utc() - ts).total_seconds()
    idle_hours = idle_secs / 3600
    return {
        "idle": idle_hours >= hours,
        "idle_hours": round(idle_hours, 2),
        "last_report": last["timestamp"],
        "threshold_hours": hours,
    }
