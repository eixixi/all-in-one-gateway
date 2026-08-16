from datetime import datetime
from db import get_conn


def _now():
    return datetime.utcnow().isoformat()


def add_flash(content):
    """闪念：刚飘过的念头。"""
    now = _now()
    conn = get_conn()
    conn.execute(
        "INSERT INTO thoughts (content, kind, status, created_at, updated_at) VALUES (?,?,?,?,?)",
        (content, "flash", "active", now, now))
    conn.commit()
    conn.close()
    return {"status": "ok", "kind": "flash"}


def promote_to_obsession(thought_id):
    """闪念长成执念。"""
    now = _now()
    conn = get_conn()
    conn.execute("UPDATE thoughts SET kind='obsession', updated_at=? WHERE id=?", (now, thought_id))
    conn.commit()
    conn.close()
    return {"status": "ok", "kind": "obsession"}


def list_thoughts(kind=None, limit=20):
    conn = get_conn()
    if kind:
        rows = conn.execute(
            "SELECT * FROM thoughts WHERE kind=? AND status='active' ORDER BY id DESC LIMIT ?",
            (kind, limit)).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM thoughts WHERE status='active' ORDER BY id DESC LIMIT ?",
            (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_pool():
    """返回念头池：闪念+执念。"""
    return {
        "flashes": list_thoughts("flash"),
        "obsessions": list_thoughts("obsession"),
    }
