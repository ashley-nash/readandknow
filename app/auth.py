"""密码加密与登录状态。

密码不会明文保存：用 PBKDF2-SHA256（20 万次迭代 + 随机盐）做单向哈希。
登录状态存在加密签名的 Cookie 里（Starlette SessionMiddleware）。
"""
import hashlib
import hmac
import secrets

from fastapi import Request

ITERATIONS = 200_000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), ITERATIONS).hex()
    return f"pbkdf2${ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iters, salt, digest = stored.split("$")
    except ValueError:
        return False
    check = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(iters)).hex()
    return hmac.compare_digest(check, digest)


def current_user(request: Request, db):
    uid = request.session.get("uid")
    if not uid:
        return None
    row = db.execute("SELECT id, email, display_name, role FROM users WHERE id=?", (uid,)).fetchone()
    return dict(row) if row else None


def new_invite_code() -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"   # 去掉了容易看错的 0/O/1/I
    return "XING-" + "".join(secrets.choice(alphabet) for _ in range(6))
