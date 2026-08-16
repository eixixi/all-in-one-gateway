from datetime import datetime, timedelta
from db import get_conn

JST = timedelta(hours=8)


def add_record(app_name, event, battery="", location="", weather="", device="", brightness="", volume=""):
    now = datetime.utcnow().isoformat()
    conn = get_conn()
    conn.execute(
        "INSERT INTO records (app_name, event, battery, location, weather, device, brightness, volume, timestamp) VALUES (?,?,?,?,?,?,?,?,?)",
        (app_name, event, battery, location, weather, device, brightness, volume, now))
    conn.commit()
    conn.close()
    return {"status": "ok"}


def get_summary():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT app_name, event, battery, location, weather, device, brightness, volume, timestamp FROM records ORDER BY id DESC LIMIT 5")
    recent = cur.fetchall()
    cur.execute("SELECT app_name, event, battery, location, weather, device, brightness, volume, timestamp FROM records ORDER BY id ASC")
    rows = cur.fetchall()
    conn.close()

    sessions, opens = {}, {}
    latest_battery = latest_location = latest_weather = latest_device = ""
    latest_brightness = latest_volume = latest_ts = ""
    now_jst = datetime.utcnow() + JST
    today_start = datetime(now_jst.year, now_jst.month, now_jst.day)
    today_start_utc = today_start - JST

    for r in rows:
        app, ev, battery, location, weather, device, brightness, volume, ts = r
        if battery: latest_battery = battery
        if location: latest_location = location
        if weather: latest_weather = weather
        if device: latest_device = device
        if brightness: latest_brightness = brightness
        if volume: latest_volume = volume
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
        "last_update": latest_ts
    }
