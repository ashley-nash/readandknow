"""网站配置：全部从环境变量（服务器上的 .env 文件）读取，改配置不用改代码。"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv():
    env = BASE_DIR / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv()

SITE_NAME = os.getenv("SITE_NAME", "观星知己")
SITE_NAME_EN = os.getenv("SITE_NAME_EN", "Read & Know")
SITE_URL = os.getenv("SITE_URL", "http://localhost:8000")
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "data" / "site.db"))
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@example.com")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "change-me-now")
HTTPS_ONLY = os.getenv("HTTPS_ONLY", "false").lower() == "true"
# 订单时间等记录用的时区（你在马德里就用 Europe/Madrid）
TIMEZONE = os.getenv("TIMEZONE", "Europe/Madrid")
