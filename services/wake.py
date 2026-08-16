import json
import asyncio
import httpx
from datetime import datetime, timedelta
from config import cfg
from services import reporting, dm, thoughts, bark, timeline


def _is_daytime():
    hour = datetime.now().hour
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
    """从时间线找最后一条真实用户消息时间。"""
    timeline_msgs = timeline.load_timeline()
    for m in reversed(timeline_msgs):
        if m.get("role") == "user":
            content = str(m.get("content", ""))
            # 提取时间戳
            import re
            match = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})[ T]?(\d{1,2})[:：](\d{2})", content)
            if match:
                try:
                    y, mo, d, h, mi = map(int, match.groups())
                    return datetime(y, mo, d, h, mi)
                except Exception:
                    pass
    return None


def _should_wake():
    last = _get_last_user_time()
    if not last:
        return False
    diff_min = (datetime.now() - last).total_seconds() / 60
    return diff_min >= _wake_after_minutes()


def _build_wake_prompt(current_time, diff_min, check_result, mood, thoughts_text, weather=""):
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

## 心潮动态状态
{json.dumps(mood, ensure_ascii=False)}

## 念头池
{thoughts_text}

{weather}

## 输出格式
- 如果想联系用户，直接写你想说的话。系统会自动打包成手机推送发送。可以是一句话，也可以第一行作为标题、第二行作为正文。
- 如果不想联系，只输出：[NO_ACTION]，可附带简短原因（10字以内）。
- 如果你想写日记，可以额外输出 [DIARY]...[/DIARY]。
"""


def _extract_diary(text):
    import re
    diary_blocks = re.findall(r"\[DIARY\]([\s\S]*?)\[/DIARY\]", text)
    remaining = re.sub(r"\[DIARY\][\s\S]*?\[/DIARY\]", "", text).strip()
    return diary_blocks, remaining


def _save_diary(content):
    if not cfg.DIARY_ENABLED or not content:
        return False
    from pathlib import Path
    diary_dir = Path(cfg.DIARY_DIR)
    diary_dir.mkdir(exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    time_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    file = diary_dir / f"{date_str}.md"
    with open(file, "a", encoding="utf-8") as f:
        f.write(f"\n\n## {time_str}\n\n{content}\n")
    return True


def _parse_push_lines(text):
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if len(lines) == 1:
        return "祁宴", lines[0]
    elif len(lines) >= 2:
        return lines[0], " ".join(lines[1:])
    return "祁宴", text


async def run_wake_once():
    """执行一次自动唤醒。"""
    if not _should_wake():
        return {"woke": False, "reason": "未到唤醒时间"}

    # 1. 查岗
    check_data = reporting.get_summary()
    check_result = _fmt_check(check_data)

    # 2. DM状态
    mood = dm.get_mood()

    # 3. 念头池
    pool = thoughts.get_pool()
    thoughts_text = json.dumps(pool, ensure_ascii=False)

    # 4. 最近时间线
    recent_ctx = timeline.get_recent_context()

    # 5. 构建prompt
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    last = _get_last_user_time()
    diff_min = (datetime.now() - last).total_seconds() / 60 if last else 0
    prompt = _build_wake_prompt(now_str, diff_min, check_result, mood, thoughts_text)

    # 6. 调LLM
    if not cfg.TARGET_API_URL or not cfg.TARGET_API_KEY:
        return {"woke": True, "error": "未配置LLM"}

    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": f"以下是你与用户最近的聊天记录，仅供回忆。你现在处于后台自主唤醒状态。\n\n{recent_ctx}"},
    ]

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            cfg.TARGET_API_URL,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {cfg.TARGET_API_KEY}"},
            json={"model": cfg.MODEL_NAME, "messages": messages, "temperature": 0.8, "stream": False},
        )
        data = resp.json()

    raw_text = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()

    # 7. 处理结果
    diary_blocks, remaining = _extract_diary(raw_text)
    diary_saved = _save_diary("\n".join(diary_blocks))

    if not remaining:
        event_content = f"自动唤醒：本次未发送推送｜原因：{'只写日记' if diary_saved else '模型空回复'}"
        timeline.append_special_event(event_content)
        return {"woke": True, "pushed": False, "reason": event_content}

    if remaining.startswith("[NO_ACTION]"):
        reason = remaining.replace("[NO_ACTION]", "").strip()[:20]
        event_content = f"自动唤醒：本次未发送推送｜原因：{reason}" if reason else "自动唤醒：本次未发送推送"
        timeline.append_special_event(event_content)
        return {"woke": True, "pushed": False, "reason": event_content}

    # 8. 发推送
    title, body = _parse_push_lines(remaining)
    result = bark.bark_alert(title, body)
    event_content = f"刚刚给用户发了推送：{title}｜{body}"
    timeline.append_special_event(event_content)
    return {"woke": True, "pushed": True, "bark": result, "title": title, "body": body}


def _fmt_check(data):
    lines = []
    if data.get("last_update"): lines.append(f"采集时间：{data['last_update']}")
    apps = data.get("recent_apps", [])
    lines.append(f"最近打开：{', '.join(apps)}" if apps else "暂无记录")
    ses = data.get("sessions", {})
    if ses:
        for app, secs in sorted(ses.items(), key=lambda x: x[1], reverse=True):
            m, s = divmod(secs, 60)
            lines.append(f" {app}: {m}分{s}秒")
    if data.get("battery"): lines.append(f"电量：{data['battery']}%")
    if data.get("location"): lines.append(f"位置：{data['location']}")
    return "\n".join(lines)


async def wake_loop():
    """后台唤醒循环。"""
    while True:
        try:
            await run_wake_once()
        except Exception as e:
            print(f"[wake] 出错: {e}")
        await asyncio.sleep(_check_interval_minutes() * 60)
