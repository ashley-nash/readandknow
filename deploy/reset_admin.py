"""忘记管理员密码时用：生成一个新的随机密码并打印出来。

在服务器上运行：
    sudo -u readandknow /opt/readandknow/venv/bin/python /opt/readandknow/deploy/reset_admin.py
"""
import os
import secrets
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.auth import hash_password  # noqa: E402
from app.db import get_db, init_db  # noqa: E402

init_db()
new_pw = secrets.token_urlsafe(12)
with get_db() as db:
    row = db.execute("SELECT id, email FROM users WHERE role='admin' ORDER BY id LIMIT 1").fetchone()
    db.execute("UPDATE users SET password_hash=? WHERE id=?", (hash_password(new_pw), row["id"]))
print(f"管理员邮箱：{row['email']}\n新密码：{new_pw}\n登录后请到「管理后台 → 网站设置」改成你自己的密码。")
