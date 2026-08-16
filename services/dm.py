from datetime import datetime
from db import get_conn

# 四维状态 + 总欲望
DIMS = ["jealousy", "loneliness", "physical", "yearning"]

DEFAULT_STATE = {
    "jealousy": 0.0,
    "loneliness": 0.0,
    "physical": 0.0,
    "yearning": 0.0,
    "desire": 50.0,
}


def _now():
    return datetime.utcnow().isoformat()


def load_state():
    conn = get_conn()
    rows = conn.execute("SELECT key, value FROM dm_state").fetchall()
    conn.close()
    state = dict(DEFAULT_STATE)
    for r in rows:
        state[r["key"]] = r["value"]
    return state


def save_state(state):
    now = _now()
    conn = get_conn()
    for k, v in state.items():
        conn.execute(
            "INSERT INTO dm_state (key, value, updated_at) VALUES (?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
            (k, float(v), now))
    conn.commit()
    conn.close()


def tick():
    """每60秒跑一次：四维独立涨落，欲望随时间变化。"""
    state = load_state()
    # 简化的涨落模型：欲望静默时增长、联系后回落
    # 这里由唤醒/互动事件驱动调整，tick只做轻微漂移
    state["desire"] = max(0.0, min(100.0, state["desire"] + 0.1))
    save_state(state)
    return state


def record_interaction():
    """联系后欲望回落。"""
    state = load_state()
    state["desire"] = max(0.0, state["desire"] - 2.0)
    save_state(state)
    return state


def record_silence(hours):
    """静默后欲望增长 (+6/时，封顶100)。"""
    state = load_state()
    state["desire"] = max(0.0, min(100.0, state["desire"] + 6.0 * hours))
    save_state(state)
    return state


def set_dim(name, value):
    if name not in DIMS:
        raise ValueError(f"未知维度: {name}")
    state = load_state()
    state[name] = max(0.0, min(100.0, float(value)))
    save_state(state)
    return state


def get_mood():
    return load_state()
