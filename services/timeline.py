import json
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent.parent
TIMELINE_PATH = BASE_DIR / "enhanced_messages.json"


def load_timeline():
    if not TIMELINE_PATH.exists():
        return []
    try:
        data = json.loads(TIMELINE_PATH.read_text("utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_timeline(messages):
    TIMELINE_PATH.write_text(json.dumps(messages, ensure_ascii=False, indent=2), "utf-8")


def build_timeline(kelivo_messages):
    """从Kelivo消息构建时间线。保留system，截断最近49条非system。"""
    sp = None
    non_sp = []
    for m in kelivo_messages:
        if m.get("role") == "system":
            sp = m
        else:
            non_sp.append(m)
    trimmed = non_sp[-49:]
    result = [sp] + trimmed if sp else trimmed
    return result


def append_special_event(content):
    """追加唤醒/推送等特殊事件，带时间戳，供Kelivo注入。"""
    timeline = load_timeline()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    event = {"role": "assistant", "content": f"（{now} {content}）"}
    timeline.append(event)
    # 保持长度
    sp = timeline[0] if timeline and timeline[0].get("role") == "system" else None
    non_sp = [m for m in timeline if m.get("role") != "system"]
    trimmed = non_sp[-50:]
    save_timeline([sp] + trimmed if sp else trimmed)
    return event


def is_special_event(msg):
    c = str(msg.get("content", ""))
    return (
        "刚刚给用户发了" in c or
        "自动唤醒：本次未发送" in c or
        "刚刚查岗" in c
    )


def get_recent_context():
    """给唤醒用的最近时间线文本。"""
    timeline = load_timeline()
    lines = []
    for m in timeline:
        if m.get("role") == "system":
            continue
        role = "用户" if m.get("role") == "user" else "AI"
        lines.append(f"[{role}] {m.get('content', '')}")
    return "\n\n".join(lines[-30:])
