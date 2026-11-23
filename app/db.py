"""SQLite 数据库：一个文件就是整个数据库（data/site.db），备份时复制这个文件即可。"""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    display_name TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'client',          -- client / analyst / admin
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS analyst_profiles (
    user_id INTEGER PRIMARY KEY REFERENCES users(id),
    douyin_name TEXT NOT NULL,
    title TEXT DEFAULT '',
    bio TEXT DEFAULT '',
    specialties TEXT DEFAULT '',                  -- 逗号分隔：bazi,ziwei,liuyao
    years_exp INTEGER DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending',       -- pending / approved / suspended
    invite_code TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS services (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analyst_id INTEGER NOT NULL REFERENCES users(id),
    kind TEXT NOT NULL,                           -- bazi / ziwei / liuyao
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    price REAL NOT NULL,
    delivery_days INTEGER DEFAULT 3,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS invite_codes (
    code TEXT PRIMARY KEY,
    note TEXT DEFAULT '',
    max_uses INTEGER NOT NULL DEFAULT 1,
    used_count INTEGER NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL REFERENCES users(id),
    analyst_id INTEGER NOT NULL REFERENCES users(id),
    service_id INTEGER REFERENCES services(id),
    kind TEXT NOT NULL,
    title TEXT NOT NULL,
    price REAL NOT NULL,
    status TEXT NOT NULL,
    question TEXT DEFAULT '',
    input_json TEXT DEFAULT '{}',
    chart_json TEXT DEFAULT '{}',
    report TEXT DEFAULT '',
    payment_note TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    paid_at TEXT,
    delivered_at TEXT
);
CREATE TABLE IF NOT EXISTS order_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL REFERENCES orders(id),
    sender_id INTEGER NOT NULL REFERENCES users(id),
    body TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER UNIQUE NOT NULL REFERENCES orders(id),
    client_id INTEGER NOT NULL REFERENCES users(id),
    analyst_id INTEGER NOT NULL REFERENCES users(id),
    rating INTEGER NOT NULL,
    comment TEXT DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_orders_client ON orders(client_id);
CREATE INDEX IF NOT EXISTS idx_orders_analyst ON orders(analyst_id);
"""

DEFAULT_SETTINGS = {
    "payment_instructions": "请通过 PayPal 或 Bizum 付款，并在付款备注里写上你的订单号。\n"
                            "付款后点击下方「我已付款」，平台确认收款后，分析师就会开始为你解读。",
    "platform_fee_pct": "20",
    "announcement": "",
    "contact": "",
    "default_theme": "night",
}


def now() -> str:
    return datetime.now(ZoneInfo(config.TIMEZONE)).strftime("%Y-%m-%d %H:%M:%S")


def _connect():
    Path(config.DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


@contextmanager
def get_db():
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    from .auth import hash_password

    with get_db() as db:
        db.executescript(SCHEMA)
        for k, v in DEFAULT_SETTINGS.items():
            db.execute("INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)", (k, v))
        # 第一次启动时自动创建管理员账号（账号密码来自 .env）
        if not db.execute("SELECT 1 FROM users WHERE role='admin'").fetchone():
            db.execute(
                "INSERT INTO users(email, password_hash, display_name, role, created_at) VALUES (?,?,?,?,?)",
                (config.ADMIN_EMAIL.lower(), hash_password(config.ADMIN_PASSWORD), "站长", "admin", now()),
            )


def get_settings(db) -> dict:
    return {r["key"]: r["value"] for r in db.execute("SELECT key, value FROM settings")}


def row_to_dict(row):
    return dict(row) if row else None


def loads(s, default=None):
    try:
        return json.loads(s) if s else default
    except (TypeError, ValueError):
        return default
