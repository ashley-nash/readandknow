#!/usr/bin/env bash
# =====================================================================
#  观星知己 · 一键安装 / 更新脚本（Ubuntu 22.04 / 24.04，如 AWS Lightsail）
#
#  第一次安装：  sudo bash deploy/install.sh readandknow.eu 你的邮箱
#  以后更新代码：git pull && sudo bash deploy/install.sh
#
#  它会做这些事：
#    1. 安装 Python、Caddy（自动申请 HTTPS 证书的网页服务器）
#    2. 把网站文件复制到 /opt/readandknow，建 Python 虚拟环境、装依赖
#    3. 第一次运行时生成 .env（随机密钥 + 随机管理员密码，最后会打印出来）
#    4. 注册成系统服务：开机自启、崩溃自动重启
#    5. 每天自动备份数据库，保留最近 14 天
#  重复运行是安全的：不会覆盖你的 .env 和数据库。
# =====================================================================
set -euo pipefail

APP_DIR=/opt/readandknow
APP_USER=readandknow
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ $EUID -ne 0 ]]; then
  echo "请在命令前加 sudo 运行：sudo bash deploy/install.sh 域名 邮箱"; exit 1
fi

DOMAIN="${1:-}"
EMAIL="${2:-}"
if [[ -z "$DOMAIN" && -f "$APP_DIR/.env" ]]; then
  DOMAIN="$(grep -E '^SITE_DOMAIN=' "$APP_DIR/.env" | cut -d= -f2- || true)"
fi
if [[ -z "$DOMAIN" ]]; then
  echo "第一次安装需要域名和邮箱，例如：sudo bash deploy/install.sh readandknow.eu you@example.com"; exit 1
fi

echo "==> [1/6] 安装系统软件（第一次大约 2-3 分钟）"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y -q
apt-get install -y -q python3 python3-venv python3-pip rsync sqlite3 curl gnupg \
  debian-keyring debian-archive-keyring apt-transport-https >/dev/null
if ! command -v caddy >/dev/null; then
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor --yes -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' > /etc/apt/sources.list.d/caddy-stable.list
  chmod o+r /usr/share/keyrings/caddy-stable-archive-keyring.gpg /etc/apt/sources.list.d/caddy-stable.list
  apt-get update -y -q && apt-get install -y -q caddy >/dev/null
fi

# 小内存机器（512MB）加 1GB 交换空间，避免安装依赖时内存不够
if [[ ! -f /swapfile ]] && [[ $(free -m | awk '/^Mem:/{print $2}') -lt 1500 ]]; then
  echo "==> 添加 1GB 交换空间"
  fallocate -l 1G /swapfile && chmod 600 /swapfile && mkswap /swapfile >/dev/null && swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'; then
  echo "系统自带的 Python 版本太旧（需要 3.11+）。请在 Lightsail 创建实例时选择 Ubuntu 24.04。"; exit 1
fi

echo "==> [2/6] 复制网站文件到 $APP_DIR"
id -u "$APP_USER" >/dev/null 2>&1 || useradd --system --home "$APP_DIR" --shell /usr/sbin/nologin "$APP_USER"
mkdir -p "$APP_DIR/data" "$APP_DIR/backups"
rsync -a --delete --exclude '.git' --exclude 'data/' --exclude 'backups/' --exclude '.env' \
  --exclude 'venv/' --exclude '__pycache__' "$SRC_DIR/" "$APP_DIR/"

echo "==> [3/6] 安装 Python 依赖"
[[ -d "$APP_DIR/venv" ]] || python3 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install -q --upgrade pip
"$APP_DIR/venv/bin/pip" install -q -r "$APP_DIR/requirements.txt"

echo "==> [4/6] 生成配置文件 .env"
NEW_ADMIN_PASSWORD=""
if [[ ! -f "$APP_DIR/.env" ]]; then
  NEW_ADMIN_PASSWORD="$(python3 -c 'import secrets;print(secrets.token_urlsafe(12))')"
  cat > "$APP_DIR/.env" <<EOF
SITE_DOMAIN=$DOMAIN
SITE_URL=https://$DOMAIN
SECRET_KEY=$(python3 -c 'import secrets;print(secrets.token_hex(32))')
ADMIN_EMAIL=${EMAIL:-admin@$DOMAIN}
ADMIN_PASSWORD=$NEW_ADMIN_PASSWORD
HTTPS_ONLY=true
TIMEZONE=Europe/Madrid
EOF
fi
chown -R "$APP_USER:$APP_USER" "$APP_DIR"
chmod 600 "$APP_DIR/.env"

echo "==> [5/6] 注册系统服务 + 配置 HTTPS"
cat > /etc/systemd/system/readandknow.service <<EOF
[Unit]
Description=Read and Know website
After=network.target

[Service]
User=$APP_USER
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --proxy-headers --forwarded-allow-ips 127.0.0.1
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/caddy/Caddyfile <<EOF
$DOMAIN {
    encode gzip zstd
    reverse_proxy 127.0.0.1:8000
}

www.$DOMAIN {
    redir https://$DOMAIN{uri} permanent
}
EOF

cat > /etc/cron.daily/readandknow-backup <<EOF
#!/bin/sh
# 每天备份数据库，保留 14 天
sqlite3 $APP_DIR/data/site.db ".backup '$APP_DIR/backups/site-\$(date +%F).db'"
find $APP_DIR/backups -name 'site-*.db' -mtime +14 -delete
EOF
chmod +x /etc/cron.daily/readandknow-backup

systemctl daemon-reload
systemctl enable --now readandknow >/dev/null 2>&1
systemctl restart readandknow
systemctl enable caddy >/dev/null 2>&1
systemctl reload caddy 2>/dev/null || systemctl restart caddy

echo "==> [6/6] 检查网站是否在运行"
for i in $(seq 1 15); do
  if curl -fs http://127.0.0.1:8000/healthz >/dev/null; then OK=1; break; fi; sleep 1
done
if [[ "${OK:-0}" != 1 ]]; then
  echo "网站没有启动成功，请把下面的日志复制给 Claude："
  journalctl -u readandknow -n 40 --no-pager; exit 1
fi

echo
echo "================================================================"
echo "  ✓ 安装完成！网站地址：https://$DOMAIN"
echo "  （如果刚改完域名解析，HTTPS 证书可能要等几分钟才生效）"
if [[ -n "$NEW_ADMIN_PASSWORD" ]]; then
  echo
  echo "  管理员登录邮箱：$(grep -E '^ADMIN_EMAIL=' $APP_DIR/.env | cut -d= -f2-)"
  echo "  管理员初始密码：$NEW_ADMIN_PASSWORD"
  echo "  ↑ 请马上抄下来，登录后在「管理后台 → 网站设置」里改成你自己的密码"
fi
echo "================================================================"
