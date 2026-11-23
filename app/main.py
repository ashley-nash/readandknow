"""网站主程序：所有页面路由都在这里。

启动：uvicorn app.main:app --reload
"""
import json
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from markupsafe import Markup, escape
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from . import config
from .auth import current_user, hash_password, new_invite_code, verify_password
from .db import get_db, get_settings, init_db, loads, now
import math

from .content import symbols as SYM_MODULE
from .content.hepan_texts import RELATION_TYPES
from .content.readings import DAILY_WORDS
from .content.symbols import T
from .engines import bazi_chart, hepan_chart, liuyao_chart, ziwei_chart
from .engines.common import SHICHEN_LABELS
from .i18n import DEFAULT_MODE, MODE_LABELS, MODES, I18n

APP_DIR = Path(__file__).resolve().parent



@asynccontextmanager
async def lifespan(_app):
    init_db()          # 启动时自动建表、创建管理员
    yield


app = FastAPI(title=config.SITE_NAME, docs_url=None, redoc_url=None, lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=config.SECRET_KEY, same_site="lax",
                   https_only=config.HTTPS_ONLY, max_age=60 * 60 * 24 * 30)
app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
templates = Jinja2Templates(directory=APP_DIR / "templates")

KINDS = {"bazi": "八字", "ziwei": "紫微斗数", "liuyao": "六爻", "hepan": "合盘"}
THEMES = {"night": T("夜观星空", "Night sky", "Cielo nocturno"),
          "ink": T("水墨宣纸", "Ink and paper", "Tinta y papel"),
          "dunhuang": T("敦煌壁画", "Dunhuang mural", "Mural de Dunhuang")}
SYM = {"STEMS": SYM_MODULE.STEMS, "BRANCHES": SYM_MODULE.BRANCHES, "TEN_GODS": SYM_MODULE.TEN_GODS,
       "ELEMENTS": SYM_MODULE.ELEMENTS, "TEN_GOD_ORDER": SYM_MODULE.TEN_GOD_ORDER}
# 敦煌主题首页的十二生肖轮盘：子在正上方，顺时针排列（百分比坐标）
WHEEL = [(z, round(50 + 41 * math.sin(math.radians(i * 30)), 2), round(50 - 41 * math.cos(math.radians(i * 30)), 2))
         for i, z in enumerate("子丑寅卯辰巳午未申酉戌亥")]
STATUS = {
    "pending_payment": ("待付款", "amber"),
    "payment_submitted": ("待平台确认收款", "amber"),
    "paid": ("待分析师接单", "violet"),
    "in_progress": ("解读中", "violet"),
    "delivered": ("已交付", "jade"),
    "cancelled": ("已取消", "grey"),
}


# ---------------------------------------------------------------- 工具函数
def nl2br(text):
    return Markup("<br>".join(escape(text or "").split("\n")))


templates.env.filters["nl2br"] = nl2br
templates.env.filters["kind"] = lambda k: KINDS.get(k, k)
templates.env.filters["status"] = lambda s: STATUS.get(s, (s, "grey"))[0]
templates.env.filters["status_color"] = lambda s: STATUS.get(s, (s, "grey"))[1]
templates.env.filters["money"] = lambda v: f"€{float(v or 0):.2f}"
templates.env.filters["stars"] = lambda r: "★" * int(round(r or 0)) + "☆" * (5 - int(round(r or 0)))
templates.env.globals.update(SITE_NAME=config.SITE_NAME, SITE_NAME_EN=config.SITE_NAME_EN, KINDS=KINDS,
                             SHICHEN_LABELS=SHICHEN_LABELS, current_year=date.today().year, THEMES=THEMES,
                             SYM=SYM, WHEEL=WHEEL, RELATION_TYPES=RELATION_TYPES, MODE_LABELS=MODE_LABELS)


class Redirect(Exception):
    def __init__(self, url):
        self.url = url


@app.exception_handler(Redirect)
async def _redirect_handler(request, exc):
    return RedirectResponse(exc.url, status_code=303)


@app.exception_handler(StarletteHTTPException)
async def _http_error(request, exc):
    with get_db() as db:
        return render(request, db, "error.html", code=exc.status_code,
                      message="这一页迷失在星海里了" if exc.status_code == 404 else str(exc.detail),
                      status_code=exc.status_code)


def flash(request: Request, msg: str, kind: str = "info"):
    request.session.setdefault("flash", []).append([kind, msg])


def render(request: Request, db, name: str, status_code: int = 200, **ctx):
    user = current_user(request, db)
    settings = get_settings(db)
    messages = request.session.pop("flash", [])
    i18n = I18n(request.cookies.get("lang"))
    theme = request.cookies.get("theme")
    if theme not in THEMES:
        theme = settings.get("default_theme") if settings.get("default_theme") in THEMES else "night"
    return templates.TemplateResponse(
        request, name, {"user": user, "settings": settings, "messages": messages, "theme": theme,
                        "lang_mode": i18n.mode, "t": i18n.t, "s": i18n.s, "L": i18n.L, "Ls": i18n.Ls,
                        "one": i18n.one, "tro": i18n.tr_only, **ctx},
        status_code=status_code,
    )


def safe_next(url: str) -> str:
    return url if url and url.startswith("/") and not url.startswith("//") else "/"


def require_user(request, db, *roles):
    user = current_user(request, db)
    if not user:
        flash(request, "请先登录", "warn")
        raise Redirect(f"/login?next={request.url.path}")
    if roles and user["role"] not in roles:
        raise StarletteHTTPException(403, "你没有权限访问这个页面")
    return user


def go(url: str):
    return RedirectResponse(url, status_code=303)


def parse_birth(birth_date: str, birth_time: str, gender: str):
    d = datetime.strptime(birth_date, "%Y-%m-%d")
    t = datetime.strptime(birth_time or "12:00", "%H:%M")
    if not 1900 <= d.year <= 2100:
        raise ValueError("出生年份需在 1900–2100 之间")
    return d.year, d.month, d.day, t.hour, t.minute, ("男" if gender == "男" else "女")


def parse_tosses(raw: str):
    try:
        t = [int(x) for x in (raw or "").split(",") if x.strip()]
    except ValueError:
        return None
    return t if len(t) == 6 and all(x in (6, 7, 8, 9) for x in t) else None


def gua_time(client_time: str) -> datetime:
    """六爻以起卦那一刻的日干支装六神、定旬空，所以要用客户自己所在地的时间。
    浏览器会把本地时间传上来；如果没有或明显不对，就用网站设置的时区。"""
    local_now = datetime.now(ZoneInfo(config.TIMEZONE)).replace(tzinfo=None)
    try:
        t = datetime.strptime(client_time, "%Y-%m-%dT%H:%M")
        utc_now = datetime.now(timezone.utc).replace(tzinfo=None)
        if abs((t - utc_now).total_seconds()) < 15 * 3600:   # 世界各地时差都在 ±14 小时内
            return t
    except (TypeError, ValueError):
        pass
    return local_now


def analyst_cards(db, kind: str = ""):
    rows = db.execute("""
        SELECT u.id, u.display_name, p.title, p.bio, p.specialties, p.years_exp,
               (SELECT ROUND(AVG(rating), 1) FROM reviews r WHERE r.analyst_id = u.id) AS rating,
               (SELECT COUNT(*) FROM reviews r WHERE r.analyst_id = u.id) AS review_count,
               (SELECT COUNT(*) FROM orders o WHERE o.analyst_id = u.id AND o.status='delivered') AS done_count,
               (SELECT MIN(price) FROM services s WHERE s.analyst_id = u.id AND s.active = 1) AS min_price
        FROM users u JOIN analyst_profiles p ON p.user_id = u.id
        WHERE p.status = 'approved'
        ORDER BY done_count DESC, rating DESC, u.id
    """).fetchall()
    cards = [dict(r) | {"spec_list": [s for s in (r["specialties"] or "").split(",") if s]} for r in rows]
    if kind in KINDS:
        cards = [c for c in cards if kind in c["spec_list"]]
    return cards


# ---------------------------------------------------------------- 首页 & 静态页
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    with get_db() as db:
        word = DAILY_WORDS[date.today().toordinal() % len(DAILY_WORDS)]
        reviews = db.execute("""
            SELECT r.rating, r.comment, r.created_at, o.kind, u.display_name AS analyst_name, u.id AS analyst_id
            FROM reviews r JOIN orders o ON o.id = r.order_id JOIN users u ON u.id = r.analyst_id
            WHERE r.comment != '' AND r.rating >= 4 ORDER BY r.id DESC LIMIT 3
        """).fetchall()
        return render(request, db, "index.html", word=word, analysts=analyst_cards(db)[:3], reviews=reviews)


@app.get("/about", response_class=HTMLResponse)
def about(request: Request):
    with get_db() as db:
        return render(request, db, "about.html")


@app.get("/healthz")
def healthz():
    return {"ok": True}


# ---------------------------------------------------------------- 免费排盘
@app.get("/bazi", response_class=HTMLResponse)
def bazi_page(request: Request):
    with get_db() as db:
        return render(request, db, "chart_form.html", kind="bazi", birth=request.session.get("birth", {}))


@app.post("/bazi", response_class=HTMLResponse)
def bazi_post(request: Request, birth_date: str = Form(...), birth_time: str = Form("12:00"),
              gender: str = Form("女")):
    with get_db() as db:
        try:
            args = parse_birth(birth_date, birth_time, gender)
        except ValueError as e:
            flash(request, f"日期格式有误：{e}", "warn")
            return go("/bazi")
        request.session["birth"] = {"date": birth_date, "time": birth_time, "gender": args[5]}
        return render(request, db, "chart_form.html", kind="bazi", chart=bazi_chart(*args),
                      birth=request.session["birth"])


@app.get("/ziwei", response_class=HTMLResponse)
def ziwei_page(request: Request):
    with get_db() as db:
        return render(request, db, "chart_form.html", kind="ziwei", birth=request.session.get("birth", {}))


@app.post("/ziwei", response_class=HTMLResponse)
def ziwei_post(request: Request, birth_date: str = Form(...), birth_time: str = Form("12:00"),
               gender: str = Form("女")):
    with get_db() as db:
        try:
            args = parse_birth(birth_date, birth_time, gender)
        except ValueError as e:
            flash(request, f"日期格式有误：{e}", "warn")
            return go("/ziwei")
        request.session["birth"] = {"date": birth_date, "time": birth_time, "gender": args[5]}
        return render(request, db, "chart_form.html", kind="ziwei", chart=ziwei_chart(*args),
                      birth=request.session["birth"])


@app.get("/liuyao", response_class=HTMLResponse)
def liuyao_page(request: Request):
    with get_db() as db:
        return render(request, db, "liuyao.html")


@app.post("/liuyao", response_class=HTMLResponse)
def liuyao_post(request: Request, question: str = Form(""), tosses: str = Form(""), client_time: str = Form("")):
    with get_db() as db:
        t = parse_tosses(tosses)
        chart = liuyao_chart(t, question=question.strip()[:200], when=gua_time(client_time))
        request.session["gua"] = {"tosses": ",".join(map(str, chart["tosses"])), "question": chart["question"],
                                  "time": chart["time"]}
        return render(request, db, "liuyao.html", chart=chart)


# ---------------------------------------------------------------- 语言 & 风格
@app.get("/lang/{mode}")
def set_lang(mode: str, next: str = "/"):
    resp = go(safe_next(next))
    resp.set_cookie("lang", mode if mode in MODES else DEFAULT_MODE, max_age=60 * 60 * 24 * 365, samesite="lax")
    return resp


@app.get("/theme/{name}")
def set_theme(name: str, next: str = "/"):
    resp = go(safe_next(next))
    if name in THEMES:
        resp.set_cookie("theme", name, max_age=60 * 60 * 24 * 365, samesite="lax")
    return resp


# ---------------------------------------------------------------- 八字合盘
def parse_person(name, birth_date, birth_time, gender):
    y, m, d, h, mi, g = parse_birth(birth_date, birth_time, gender)
    return {"name": name.strip()[:12], "year": y, "month": m, "day": d, "hour": h, "minute": mi, "gender": g}


@app.get("/hepan", response_class=HTMLResponse)
def hepan_page(request: Request):
    with get_db() as db:
        return render(request, db, "hepan.html", hp=request.session.get("hepan", {}))


@app.post("/hepan", response_class=HTMLResponse)
def hepan_post(request: Request, relation: str = Form("couple"),
               a_name: str = Form(""), a_birth_date: str = Form(...), a_birth_time: str = Form("12:00"), a_gender: str = Form("女"),
               b_name: str = Form(""), b_birth_date: str = Form(...), b_birth_time: str = Form("12:00"), b_gender: str = Form("男")):
    with get_db() as db:
        try:
            pa = parse_person(a_name, a_birth_date, a_birth_time, a_gender)
            pb = parse_person(b_name, b_birth_date, b_birth_time, b_gender)
        except ValueError:
            flash(request, "请填写正确的出生日期和时间", "warn")
            return go("/hepan")
        request.session["hepan"] = {
            "relation": relation,
            "a": {"name": pa["name"], "date": a_birth_date, "time": a_birth_time, "gender": pa["gender"]},
            "b": {"name": pb["name"], "date": b_birth_date, "time": b_birth_time, "gender": pb["gender"]},
        }
        return render(request, db, "hepan.html", chart=hepan_chart(pa, pb, relation), hp=request.session["hepan"])


# ---------------------------------------------------------------- 分析师
@app.get("/analysts", response_class=HTMLResponse)
def analysts(request: Request, kind: str = ""):
    with get_db() as db:
        return render(request, db, "analysts.html", analysts=analyst_cards(db, kind), kind=kind)


@app.get("/analysts/{aid}", response_class=HTMLResponse)
def analyst_detail(request: Request, aid: int):
    with get_db() as db:
        card = next((c for c in analyst_cards(db) if c["id"] == aid), None)
        if not card:
            raise StarletteHTTPException(404)
        services = db.execute("SELECT * FROM services WHERE analyst_id=? AND active=1 ORDER BY price", (aid,)).fetchall()
        reviews = db.execute("""SELECT r.*, o.kind FROM reviews r JOIN orders o ON o.id=r.order_id
                                WHERE r.analyst_id=? ORDER BY r.id DESC LIMIT 30""", (aid,)).fetchall()
        return render(request, db, "analyst_detail.html", a=card, services=services, reviews=reviews)


# ---------------------------------------------------------------- 注册登录
@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request, role: str = "client"):
    with get_db() as db:
        return render(request, db, "register.html", role=role)


@app.post("/register")
def register_post(request: Request, email: str = Form(...), password: str = Form(...),
                  display_name: str = Form(...), role: str = Form("client"),
                  invite_code: str = Form(""), douyin_name: str = Form("")):
    email = email.strip().lower()
    display_name = display_name.strip()[:30]
    with get_db() as db:
        if len(password) < 8:
            flash(request, "密码至少 8 位", "warn")
            return go(f"/register?role={role}")
        if db.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
            flash(request, "这个邮箱已经注册过了，请直接登录", "warn")
            return go("/login")
        code = None
        if role == "analyst":
            code = db.execute("SELECT * FROM invite_codes WHERE code=? AND active=1 AND used_count < max_uses",
                              (invite_code.strip().upper(),)).fetchone()
            if not code:
                flash(request, "邀请码无效或已用完。分析师邀请码仅向抖音会员发放。", "warn")
                return go("/register?role=analyst")
            if not douyin_name.strip():
                flash(request, "请填写你的抖音昵称，方便站长核对会员身份", "warn")
                return go("/register?role=analyst")
        cur = db.execute("INSERT INTO users(email, password_hash, display_name, role, created_at) VALUES (?,?,?,?,?)",
                         (email, hash_password(password), display_name, "analyst" if code else "client", now()))
        uid = cur.lastrowid
        if code:
            db.execute("UPDATE invite_codes SET used_count = used_count + 1 WHERE code=?", (code["code"],))
            db.execute("""INSERT INTO analyst_profiles(user_id, douyin_name, invite_code, status, created_at)
                          VALUES (?,?,?,?,?)""", (uid, douyin_name.strip()[:50], code["code"], "pending", now()))
        request.session["uid"] = uid
        if code:
            flash(request, "注册成功！请完善你的分析师资料并添加服务，站长审核通过后就会出现在分析师列表里。", "ok")
            return go("/me/profile")
        flash(request, "欢迎来到观星知己 ✨", "ok")
        return go(request.query_params.get("next") or "/me")


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, next: str = "/me"):
    with get_db() as db:
        return render(request, db, "login.html", next=next)


@app.post("/login")
def login_post(request: Request, email: str = Form(...), password: str = Form(...), next: str = Form("/me")):
    with get_db() as db:
        row = db.execute("SELECT * FROM users WHERE email=?", (email.strip().lower(),)).fetchone()
        if not row or not verify_password(password, row["password_hash"]):
            flash(request, "邮箱或密码不正确", "warn")
            return go(f"/login?next={next}")
        request.session["uid"] = row["id"]
        return go(safe_next(next) if next != "/" else "/me")


@app.post("/logout")
def logout(request: Request):
    request.session.clear()
    return go("/")


# ---------------------------------------------------------------- 个人中心
@app.get("/me", response_class=HTMLResponse)
def me(request: Request):
    with get_db() as db:
        user = require_user(request, db)
        if user["role"] == "admin":
            return go("/admin")
        my_orders = db.execute("""SELECT o.*, u.display_name AS analyst_name FROM orders o
                                  JOIN users u ON u.id=o.analyst_id WHERE o.client_id=? ORDER BY o.id DESC""",
                               (user["id"],)).fetchall()
        ctx = {"my_orders": my_orders}
        if user["role"] == "analyst":
            ctx["profile"] = db.execute("SELECT * FROM analyst_profiles WHERE user_id=?", (user["id"],)).fetchone()
            ctx["incoming"] = db.execute("""SELECT o.*, u.display_name AS client_name FROM orders o
                                            JOIN users u ON u.id=o.client_id
                                            WHERE o.analyst_id=? AND o.status NOT IN ('pending_payment','cancelled')
                                            ORDER BY CASE o.status WHEN 'paid' THEN 0 WHEN 'in_progress' THEN 1
                                            ELSE 2 END, o.id DESC""", (user["id"],)).fetchall()
            ctx["services"] = db.execute("SELECT * FROM services WHERE analyst_id=? ORDER BY id", (user["id"],)).fetchall()
            fee = float(get_settings(db).get("platform_fee_pct", "20"))
            earned = db.execute("SELECT COALESCE(SUM(price),0) FROM orders WHERE analyst_id=? AND status='delivered'",
                                (user["id"],)).fetchone()[0]
            ctx["earnings"] = {"gross": earned, "fee": fee, "net": earned * (1 - fee / 100)}
        return render(request, db, "me.html", **ctx)


@app.get("/me/profile", response_class=HTMLResponse)
def profile_page(request: Request):
    with get_db() as db:
        user = require_user(request, db, "analyst")
        profile = db.execute("SELECT * FROM analyst_profiles WHERE user_id=?", (user["id"],)).fetchone()
        services = db.execute("SELECT * FROM services WHERE analyst_id=? ORDER BY id", (user["id"],)).fetchall()
        return render(request, db, "profile.html", profile=profile, services=services)


@app.post("/me/profile")
def profile_post(request: Request, display_name: str = Form(...), title: str = Form(""), bio: str = Form(""),
                 years_exp: int = Form(0), specialties: list[str] = Form([])):
    with get_db() as db:
        user = require_user(request, db, "analyst")
        specs = ",".join(s for s in specialties if s in KINDS)
        db.execute("UPDATE users SET display_name=? WHERE id=?", (display_name.strip()[:30], user["id"]))
        db.execute("UPDATE analyst_profiles SET title=?, bio=?, years_exp=?, specialties=? WHERE user_id=?",
                   (title.strip()[:60], bio.strip()[:2000], max(0, min(years_exp, 80)), specs, user["id"]))
        flash(request, "资料已保存", "ok")
        return go("/me/profile")


@app.post("/me/services")
def service_add(request: Request, kind: str = Form(...), title: str = Form(...), description: str = Form(""),
                price: float = Form(...), delivery_days: int = Form(3)):
    with get_db() as db:
        user = require_user(request, db, "analyst")
        if kind not in KINDS or price <= 0:
            flash(request, "请选择服务类型并填写大于 0 的价格", "warn")
            return go("/me/profile")
        db.execute("""INSERT INTO services(analyst_id, kind, title, description, price, delivery_days, created_at)
                      VALUES (?,?,?,?,?,?,?)""", (user["id"], kind, title.strip()[:60], description.strip()[:1000],
                                                  round(price, 2), max(1, min(delivery_days, 30)), now()))
        flash(request, "服务已添加", "ok")
        return go("/me/profile")


@app.post("/me/services/{sid}/toggle")
def service_toggle(request: Request, sid: int):
    with get_db() as db:
        user = require_user(request, db, "analyst")
        db.execute("UPDATE services SET active = 1 - active WHERE id=? AND analyst_id=?", (sid, user["id"]))
        return go("/me/profile")


# ---------------------------------------------------------------- 下单
@app.get("/order/new", response_class=HTMLResponse)
def order_new(request: Request, service_id: int):
    with get_db() as db:
        user = require_user(request, db)
        svc = db.execute("""SELECT s.*, u.display_name AS analyst_name FROM services s
                            JOIN users u ON u.id=s.analyst_id JOIN analyst_profiles p ON p.user_id=u.id
                            WHERE s.id=? AND s.active=1 AND p.status='approved'""", (service_id,)).fetchone()
        if not svc:
            raise StarletteHTTPException(404)
        if svc["analyst_id"] == user["id"]:
            flash(request, "不能给自己下单哦", "warn")
            return go(f"/analysts/{svc['analyst_id']}")
        return render(request, db, "order_new.html", svc=svc, birth=request.session.get("birth", {}),
                      gua=request.session.get("gua"), hp=request.session.get("hepan", {}))


@app.post("/order/new")
def order_create(request: Request, service_id: int = Form(...), question: str = Form(""),
                 birth_date: str = Form(""), birth_time: str = Form(""), gender: str = Form("女"),
                 birth_place: str = Form(""), tosses: str = Form(""), use_last_gua: str = Form(""),
                 client_time: str = Form(""), relation: str = Form("couple"),
                 a_name: str = Form(""), a_birth_date: str = Form(""), a_birth_time: str = Form(""), a_gender: str = Form("女"),
                 b_name: str = Form(""), b_birth_date: str = Form(""), b_birth_time: str = Form(""), b_gender: str = Form("男")):
    with get_db() as db:
        user = require_user(request, db)
        svc = db.execute("SELECT * FROM services WHERE id=? AND active=1", (service_id,)).fetchone()
        if not svc or svc["analyst_id"] == user["id"]:
            raise StarletteHTTPException(404)
        question = question.strip()[:1000]
        inputs = {"birth_place": birth_place.strip()[:100]}
        if svc["kind"] in ("bazi", "ziwei"):
            try:
                args = parse_birth(birth_date, birth_time, gender)
            except ValueError:
                flash(request, "请填写正确的出生日期和时间", "warn")
                return go(f"/order/new?service_id={service_id}")
            inputs.update(date=birth_date, time=birth_time, gender=args[5])
            chart = (bazi_chart if svc["kind"] == "bazi" else ziwei_chart)(*args)
        elif svc["kind"] == "hepan":
            try:
                pa = parse_person(a_name, a_birth_date, a_birth_time, a_gender)
                pb = parse_person(b_name, b_birth_date, b_birth_time, b_gender)
            except ValueError:
                flash(request, "请填写正确的出生日期和时间", "warn")
                return go(f"/order/new?service_id={service_id}")
            inputs.update(a=pa, b=pb, relation=relation)
            chart = hepan_chart(pa, pb, relation)
        else:
            if not question:
                flash(request, "六爻需要一个具体的问题，请写下你想问的事", "warn")
                return go(f"/order/new?service_id={service_id}")
            gua = request.session.get("gua") if use_last_gua else None
            if gua:
                when = datetime.strptime(gua["time"], "%Y-%m-%d %H:%M")
                chart = liuyao_chart(parse_tosses(gua["tosses"]), question=question, when=when)
            else:
                chart = liuyao_chart(parse_tosses(tosses), question=question, when=gua_time(client_time))
            inputs.update(tosses=chart["tosses"])
        ts = now()
        cur = db.execute("""INSERT INTO orders(client_id, analyst_id, service_id, kind, title, price, status, question,
                            input_json, chart_json, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                         (user["id"], svc["analyst_id"], svc["id"], svc["kind"], svc["title"], svc["price"],
                          "pending_payment", question, json.dumps(inputs, ensure_ascii=False),
                          json.dumps(chart, ensure_ascii=False), ts, ts))
        flash(request, "订单已创建，请按说明完成付款 🙏", "ok")
        return go(f"/orders/{cur.lastrowid}")


def load_order(db, oid: int, user):
    o = db.execute("""SELECT o.*, c.display_name AS client_name, a.display_name AS analyst_name
                      FROM orders o JOIN users c ON c.id=o.client_id JOIN users a ON a.id=o.analyst_id
                      WHERE o.id=?""", (oid,)).fetchone()
    if not o or not (user["role"] == "admin" or user["id"] in (o["client_id"], o["analyst_id"])):
        raise StarletteHTTPException(404)
    return o


@app.get("/orders/{oid}", response_class=HTMLResponse)
def order_detail(request: Request, oid: int):
    with get_db() as db:
        user = require_user(request, db)
        o = load_order(db, oid, user)
        msgs = db.execute("""SELECT m.*, u.display_name, u.role FROM order_messages m JOIN users u ON u.id=m.sender_id
                             WHERE m.order_id=? ORDER BY m.id""", (oid,)).fetchall()
        review = db.execute("SELECT * FROM reviews WHERE order_id=?", (oid,)).fetchone()
        return render(request, db, "order_detail.html", o=o, chart=loads(o["chart_json"], {}),
                      inputs=loads(o["input_json"], {}), msgs=msgs, review=review,
                      is_client=user["id"] == o["client_id"], is_analyst=user["id"] == o["analyst_id"],
                      is_admin=user["role"] == "admin")


def _set_status(db, oid, status, **extra):
    sets = ", ".join(["status=?", "updated_at=?"] + [f"{k}=?" for k in extra])
    db.execute(f"UPDATE orders SET {sets} WHERE id=?", (status, now(), *extra.values(), oid))


@app.post("/orders/{oid}/paid")
def order_paid(request: Request, oid: int, payment_note: str = Form("")):
    with get_db() as db:
        user = require_user(request, db)
        o = load_order(db, oid, user)
        if o["client_id"] == user["id"] and o["status"] == "pending_payment":
            _set_status(db, oid, "payment_submitted", payment_note=payment_note.strip()[:200])
            flash(request, "已通知平台核对收款，确认后分析师会尽快接单", "ok")
        return go(f"/orders/{oid}")


@app.post("/orders/{oid}/cancel")
def order_cancel(request: Request, oid: int):
    with get_db() as db:
        user = require_user(request, db)
        o = load_order(db, oid, user)
        if (o["client_id"] == user["id"] and o["status"] == "pending_payment") or user["role"] == "admin":
            _set_status(db, oid, "cancelled")
            flash(request, "订单已取消", "info")
        return go(f"/orders/{oid}")


@app.post("/orders/{oid}/accept")
def order_accept(request: Request, oid: int):
    with get_db() as db:
        user = require_user(request, db)
        o = load_order(db, oid, user)
        if o["analyst_id"] == user["id"] and o["status"] == "paid":
            _set_status(db, oid, "in_progress")
            flash(request, "已接单，用心解读吧 ✨", "ok")
        return go(f"/orders/{oid}")


@app.post("/orders/{oid}/deliver")
def order_deliver(request: Request, oid: int, report: str = Form(...)):
    with get_db() as db:
        user = require_user(request, db)
        o = load_order(db, oid, user)
        if o["analyst_id"] == user["id"] and o["status"] in ("in_progress", "delivered") and report.strip():
            _set_status(db, oid, "delivered", report=report.strip()[:20000], delivered_at=now())
            flash(request, "解读报告已交付", "ok")
        return go(f"/orders/{oid}")


@app.post("/orders/{oid}/message")
def order_message(request: Request, oid: int, body: str = Form(...)):
    with get_db() as db:
        user = require_user(request, db)
        o = load_order(db, oid, user)
        if body.strip() and o["status"] != "cancelled":
            db.execute("INSERT INTO order_messages(order_id, sender_id, body, created_at) VALUES (?,?,?,?)",
                       (oid, user["id"], body.strip()[:2000], now()))
        return go(f"/orders/{oid}#messages")


@app.post("/orders/{oid}/review")
def order_review(request: Request, oid: int, rating: int = Form(...), comment: str = Form("")):
    with get_db() as db:
        user = require_user(request, db)
        o = load_order(db, oid, user)
        exists = db.execute("SELECT 1 FROM reviews WHERE order_id=?", (oid,)).fetchone()
        if o["client_id"] == user["id"] and o["status"] == "delivered" and not exists:
            db.execute("""INSERT INTO reviews(order_id, client_id, analyst_id, rating, comment, created_at)
                          VALUES (?,?,?,?,?,?)""", (oid, user["id"], o["analyst_id"], max(1, min(rating, 5)),
                                                    comment.strip()[:1000], now()))
            flash(request, "谢谢你的评价 🌙", "ok")
        return go(f"/orders/{oid}")


# ---------------------------------------------------------------- 管理后台
@app.get("/admin", response_class=HTMLResponse)
def admin(request: Request):
    with get_db() as db:
        require_user(request, db, "admin")
        fee = float(get_settings(db).get("platform_fee_pct", "20"))
        ctx = {
            "analysts": db.execute("""SELECT u.id, u.email, u.display_name, p.douyin_name, p.status, p.invite_code,
                                      p.created_at, p.specialties FROM users u JOIN analyst_profiles p
                                      ON p.user_id=u.id ORDER BY CASE p.status WHEN 'pending' THEN 0 ELSE 1 END,
                                      u.id DESC""").fetchall(),
            "to_confirm": db.execute("""SELECT o.*, c.display_name AS client_name, c.email AS client_email,
                                        a.display_name AS analyst_name FROM orders o JOIN users c ON c.id=o.client_id
                                        JOIN users a ON a.id=o.analyst_id WHERE o.status='payment_submitted'
                                        ORDER BY o.id""").fetchall(),
            "orders": db.execute("""SELECT o.*, c.display_name AS client_name, a.display_name AS analyst_name
                                    FROM orders o JOIN users c ON c.id=o.client_id JOIN users a ON a.id=o.analyst_id
                                    ORDER BY o.id DESC LIMIT 100""").fetchall(),
            "invites": db.execute("SELECT * FROM invite_codes ORDER BY created_at DESC").fetchall(),
            "payouts": [dict(r) | {"net": r["gross"] * (1 - fee / 100)} for r in db.execute(
                """SELECT u.display_name, p.douyin_name, COUNT(o.id) AS n, COALESCE(SUM(o.price),0) AS gross
                   FROM orders o JOIN users u ON u.id=o.analyst_id JOIN analyst_profiles p ON p.user_id=u.id
                   WHERE o.status='delivered' GROUP BY u.id ORDER BY gross DESC""").fetchall()],
            "stats": {
                "users": db.execute("SELECT COUNT(*) FROM users").fetchone()[0],
                "orders": db.execute("SELECT COUNT(*) FROM orders").fetchone()[0],
                "revenue": db.execute("SELECT COALESCE(SUM(price),0) FROM orders WHERE status IN "
                                      "('paid','in_progress','delivered')").fetchone()[0],
            },
            "fee": fee,
        }
        return render(request, db, "admin.html", **ctx)


@app.post("/admin/analysts/{uid}/{action}")
def admin_analyst(request: Request, uid: int, action: str):
    with get_db() as db:
        require_user(request, db, "admin")
        status = {"approve": "approved", "suspend": "suspended"}.get(action)
        if status:
            db.execute("UPDATE analyst_profiles SET status=? WHERE user_id=?", (status, uid))
            flash(request, "已更新分析师状态", "ok")
        return go("/admin#analysts")


@app.post("/admin/orders/{oid}/confirm")
def admin_confirm(request: Request, oid: int):
    with get_db() as db:
        require_user(request, db, "admin")
        db.execute("UPDATE orders SET status='paid', paid_at=?, updated_at=? WHERE id=? AND status='payment_submitted'",
                   (now(), now(), oid))
        flash(request, f"订单 #{oid} 已确认收款", "ok")
        return go("/admin")


@app.post("/admin/invites")
def admin_invites(request: Request, count: int = Form(1), max_uses: int = Form(1), note: str = Form("")):
    with get_db() as db:
        require_user(request, db, "admin")
        for _ in range(max(1, min(count, 50))):
            db.execute("INSERT INTO invite_codes(code, note, max_uses, created_at) VALUES (?,?,?,?)",
                       (new_invite_code(), note.strip()[:100], max(1, max_uses), now()))
        flash(request, "邀请码已生成，可以复制发到抖音会员群里", "ok")
        return go("/admin#invites")


@app.post("/admin/invites/{code}/toggle")
def admin_invite_toggle(request: Request, code: str):
    with get_db() as db:
        require_user(request, db, "admin")
        db.execute("UPDATE invite_codes SET active = 1 - active WHERE code=?", (code,))
        return go("/admin#invites")


@app.post("/admin/settings")
def admin_settings(request: Request, payment_instructions: str = Form(""), platform_fee_pct: str = Form("20"),
                   announcement: str = Form(""), contact: str = Form(""), default_theme: str = Form("night")):
    with get_db() as db:
        require_user(request, db, "admin")
        try:
            fee = str(max(0.0, min(float(platform_fee_pct), 100.0)))
        except ValueError:
            fee = "20"
        for k, v in {"payment_instructions": payment_instructions, "platform_fee_pct": fee,
                     "default_theme": default_theme if default_theme in THEMES else "night",
                     "announcement": announcement, "contact": contact}.items():
            db.execute("INSERT OR REPLACE INTO settings(key, value) VALUES (?,?)", (k, v.strip()))
        flash(request, "设置已保存", "ok")
        return go("/admin#settings")


@app.post("/admin/password")
def admin_password(request: Request, old_password: str = Form(...), new_password: str = Form(...)):
    with get_db() as db:
        user = require_user(request, db, "admin")
        row = db.execute("SELECT password_hash FROM users WHERE id=?", (user["id"],)).fetchone()
        if not verify_password(old_password, row["password_hash"]) or len(new_password) < 10:
            flash(request, "旧密码不对，或新密码少于 10 位", "warn")
        else:
            db.execute("UPDATE users SET password_hash=? WHERE id=?", (hash_password(new_password), user["id"]))
            flash(request, "管理员密码已修改", "ok")
        return go("/admin#settings")
