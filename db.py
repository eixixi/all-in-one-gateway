import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "all_in_one.db"


def get_conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.execute("""CREATE TABLE IF NOT EXISTS records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        app_name TEXT,
        event TEXT,
        battery TEXT,
        location TEXT,
        weather TEXT,
        device TEXT,
        brightness TEXT,
        volume TEXT,
        steps TEXT,
        timestamp TEXT NOT NULL)""")
    # 兼容旧表：加 steps 列
    try:
        conn.execute("ALTER TABLE records ADD COLUMN steps TEXT")
    except Exception:
        pass
    conn.execute("""CREATE TABLE IF NOT EXISTS desires (
        id TEXT PRIMARY KEY,
        text TEXT NOT NULL,
        why_mine TEXT,
        track TEXT NOT NULL DEFAULT '持续',
        status TEXT NOT NULL DEFAULT 'active',
        state TEXT,
        kind TEXT,
        lineage_parent_id TEXT,
        cooldown_until TEXT,
        surfaced_count INTEGER NOT NULL DEFAULT 0,
        last_touched_at TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS desire_notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        desire_id TEXT NOT NULL,
        note TEXT NOT NULL,
        kind TEXT NOT NULL DEFAULT 'note',
        provenance TEXT,
        created_at TEXT NOT NULL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS heartbeat_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        triggered_at TEXT NOT NULL,
        trigger_path TEXT,
        reason TEXT,
        outcome TEXT NOT NULL DEFAULT 'pending',
        thinking TEXT,
        error TEXT,
        updated_at TEXT)""")
    conn.commit()
    conn.close()


init_db()
