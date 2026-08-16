import json
import uuid
import requests
from datetime import datetime, timedelta
from db import get_conn
from config import cfg

COOLDOWN_DAYS = {"持续": 3.0, "项目": 2.0, "一次": 2.0}


def _now():
    return datetime.utcnow().isoformat()


def _load_remote():
    """拉远端GitHub的desires.json作为真源。"""
    if not cfg.GH_TOKEN or not cfg.GH_REPO:
        return []
    url = f"https://api.github.com/repos/{cfg.GH_REPO}/contents/{cfg.GH_DESIRES_FILE}"
    r = requests.get(url, headers={"Authorization": f"Bearer {cfg.GH_TOKEN}", "Accept": "application/vnd.github+json"})
    if r.status_code == 200:
        data = r.json()
        import base64
        return json.loads(base64.b64decode(data["content"]).decode("utf-8"))
    return []


def _save_remote(data):
    """写回远端GitHub。"""
    if not cfg.GH_TOKEN or not cfg.GH_REPO:
        return
    url = f"https://api.github.com/repos/{cfg.GH_REPO}/contents/{cfg.GH_DESIRES_FILE}"
    import base64
    content = base64.b64encode(json.dumps(data, ensure_ascii=False).encode()).decode()
    r = requests.get(url, headers={"Authorization": f"Bearer {cfg.GH_TOKEN}", "Accept": "application/vnd.github+json"})
    sha = r.json().get("sha") if r.status_code == 200 else None
    payload = {"message": "update desires", "content": content}
    if sha:
        payload["sha"] = sha
    requests.put(url, json=payload, headers={"Authorization": f"Bearer {cfg.GH_TOKEN}", "Accept": "application/vnd.github+json"})


def _sync_cache():
    """远端拉到本地缓存。"""
    remote = _load_remote()
    conn = get_conn()
    now = _now()
    for d in remote:
        conn.execute(
            "INSERT OR REPLACE INTO desires (id, text, why_mine, track, status, state, kind, lineage_parent_id, cooldown_until, surfaced_count, last_touched_at, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (d.get("id"), d.get("text", ""), d.get("why_mine"), d.get("track", "持续"), d.get("status", "active"),
             d.get("state"), d.get("kind"), d.get("lineage_parent_id"), d.get("cooldown_until"),
             d.get("surfaced_count", 0), d.get("last_touched_at"), d.get("created_at", now), now))
    conn.commit()
    conn.close()


def _on_cooldown(entry):
    if not entry.get("cooldown_until"):
        return False
    try:
        return datetime.fromisoformat(entry["cooldown_until"]) > datetime.utcnow()
    except Exception:
        return False


def desire_add(text, why_mine="", track="持续", grew_from=None, kind=""):
    _sync_cache()
    remote = _load_remote()
    now = _now()
    entry = {
        "id": str(uuid.uuid4()),
        "text": text,
        "why_mine": why_mine,
        "track": track,
        "status": "active",
        "state": "",
        "kind": kind,
        "lineage_parent_id": grew_from,
        "cooldown_until": None,
        "surfaced_count": 0,
        "last_touched_at": None,
        "created_at": now,
        "updated_at": now,
    }
    remote.append(entry)
    _save_remote(remote)
    _sync_cache()
    return entry


def desire_list(include_archived=False):
    _sync_cache()
    conn = get_conn()
    if include_archived:
        rows = conn.execute("SELECT * FROM desires ORDER BY created_at DESC").fetchall()
    else:
        rows = conn.execute("SELECT * FROM desires WHERE status IN ('active','touched') ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def desire_act(id, note="", done=False):
    _sync_cache()
    remote = _load_remote()
    now = _now()
    for entry in remote:
        if entry["id"] == id:
            if _on_cooldown(entry):
                return {"error": "还没冷却完"}
            entry["last_touched_at"] = now
            entry["surfaced_count"] = 0
            track = entry.get("track", "持续")
            cd = COOLDOWN_DAYS.get(track, 3.0)
            entry["cooldown_until"] = (datetime.utcnow() + timedelta(days=cd)).isoformat()
            if done:
                entry["status"] = "done"
            entry["updated_at"] = now
            conn = get_conn()
            conn.execute("INSERT INTO desire_notes (desire_id, note, kind, created_at) VALUES (?,?,?,?)",
                         (id, note or "碰了一下", "footprint", now))
            conn.commit()
            conn.close()
            break
    _save_remote(remote)
    _sync_cache()
    return {"status": "ok"}


def desire_reflect(id, action, text="", track="", note="", days=0):
    """照镜子处置一条欲望。
    action: release放下 / rewrite改写(带text和track) / snooze歇几天(带days) / note留反思
    """
    _sync_cache()
    remote = _load_remote()
    now = _now()
    found = False
    for entry in remote:
        if entry["id"] == id:
            found = True
            if action == "release":
                entry["status"] = "released"
            elif action == "rewrite":
                if text:
                    entry["text"] = text
                if track:
                    entry["track"] = track
                entry["status"] = "active"
            elif action == "snooze":
                days = int(days) if days else 3
                entry["cooldown_until"] = (datetime.utcnow() + timedelta(days=days)).isoformat()
                entry["status"] = "active"
            elif action == "note":
                pass  # 只留反思，不改变状态
            else:
                return {"error": f"未知action: {action}"}
            entry["updated_at"] = now
            conn = get_conn()
            conn.execute("INSERT INTO desire_notes (desire_id, note, kind, created_at) VALUES (?,?,?,?)",
                         (id, note or text or action, "reflection", now))
            conn.commit()
            conn.close()
            break
    if not found:
        return {"error": "欲望不存在"}
    _save_remote(remote)
    _sync_cache()
    return {"status": "ok", "action": action, "id": id}


def desire_history(id):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM desire_notes WHERE desire_id=? ORDER BY id ASC", (id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]
