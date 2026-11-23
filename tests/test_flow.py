"""完整业务流程测试：站长发邀请码 → 分析师注册上架 → 审核 → 客户下单付款 → 确认 → 接单交付 → 评价。"""
import os
import re
import sys
import tempfile

TMP = tempfile.mkdtemp()
os.environ.update(DB_PATH=os.path.join(TMP, "test.db"), ADMIN_EMAIL="boss@test.com",
                  ADMIN_PASSWORD="adminpass123", SECRET_KEY="test")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


def ok(r, *needles):
    assert r.status_code == 200, (r.status_code, r.text[:500])
    plain = re.sub(r"<[^>]+>", "", r.text)
    for n in needles:
        assert n in r.text or n in plain, f"missing {n!r} in {r.url}"
    return r


def test_full_flow():
    with TestClient(app) as anon, TestClient(app) as admin, TestClient(app) as ana, TestClient(app) as cli:
        # 公开页面
        ok(anon.get("/"), "读懂星辰", "今日一签", "第一批分析师正在入驻")
        ok(anon.get("/bazi"), "八字排盘")
        r = ok(anon.post("/bazi", data={"birth_date": "1995-06-15", "birth_time": "08:30", "gender": "女"}),
               "五行分布", "大运", "你命中的十神", "礼物", "课题", "Ten Gods")
        glyphs = [g for g in re.findall(r'class="sg">([^<]+)<', r.text) if len(g) == 1]
        assert glyphs[:8] == ["乙", "亥", "壬", "午", "丁", "丑", "甲", "辰"], glyphs[:8]   # 四柱 + 悬停符号
        # 语言切换：中西对照 / 纯中文；风格切换
        anon.get("/lang/zh-es?next=/")
        ok(anon.get("/"), "Lee las estrellas", "Atlas de símbolos", "Rata")
        anon.get("/lang/zh?next=/")
        assert "Atlas" not in anon.get("/").text
        anon.get("/lang/zh-en?next=/")
        for th, marker in (("ink", "hero-ink"), ("dunhuang", "hero-dh"), ("night", 'class="dial"')):
            anon.get(f"/theme/{th}?next=/")
            ok(anon.get("/"), marker, f'data-theme="{th}"')
        assert anon.get("/lang/xx?next=//evil.com", follow_redirects=False).headers["location"] == "/"
        # 合盘
        ok(anon.post("/hepan", data={"a_name": "小雨", "a_birth_date": "1992-03-18", "a_birth_time": "09:20", "a_gender": "女",
                                     "b_name": "阿杰", "b_birth_date": "1990-09-02", "b_birth_time": "20:00", "b_gender": "男",
                                     "relation": "couple"}),
           "小雨滋养阿杰" if False else "阿杰滋养小雨", "正印", "伤官", "日支 · 夫妻宫", "默契之处", "需要练习的地方", "Where you click")
        ok(anon.post("/ziwei", data={"birth_date": "1990-07-26", "birth_time": "16:00", "gender": "女"}),
           "土五局", "命宫在亥", "生年四化")
        ok(anon.post("/liuyao", data={"question": "换工作好吗", "tosses": "9,7,7,7,7,7"}), "乾为天", "天风姤", "卦象寄语")
        ok(anon.post("/liuyao", data={"question": "随机", "tosses": ""}), "本卦")
        ok(anon.get("/about"), "免责声明")
        assert anon.get("/nope").status_code == 404
        assert anon.get("/admin", follow_redirects=False).status_code == 303

        # 站长登录、生成邀请码
        ok(admin.post("/login", data={"email": "boss@test.com", "password": "adminpass123"}), "管理后台")
        ok(admin.post("/admin/invites", data={"count": 2, "max_uses": 1, "note": "11月会员"}), "XING-")
        code = re.search(r"XING-[A-Z0-9]{6}", admin.get("/admin").text).group(0)

        # 分析师：错误邀请码被拒，正确邀请码注册
        r = ana.post("/register", data={"role": "analyst", "email": "a@test.com", "password": "password1",
                                        "display_name": "月白", "invite_code": "XING-WRONG1", "douyin_name": "x"})
        ok(r, "邀请码无效")
        r = ana.post("/register", data={"role": "analyst", "email": "a@test.com", "password": "password1",
                                        "display_name": "月白", "invite_code": code.lower(), "douyin_name": "月白在马德里"})
        ok(r, "分析师资料", "等待审核")
        ok(ana.post("/me/profile", data={"display_name": "月白", "title": "紫微斗数十年", "bio": "温柔地读盘",
                                         "years_exp": 10, "specialties": ["ziwei", "liuyao"]}), "资料已保存")
        ok(ana.post("/me/services", data={"kind": "ziwei", "title": "紫微命盘详批", "price": "39.9",
                                          "delivery_days": 3}), "服务已添加")
        ok(ana.post("/me/services", data={"kind": "liuyao", "title": "六爻一事一问", "price": "19",
                                          "delivery_days": 1}), "六爻一事一问")
        ok(ana.post("/me/services", data={"kind": "hepan", "title": "八字合盘详解", "price": "59",
                                          "delivery_days": 5}), "八字合盘详解")
        assert "月白" not in anon.get("/analysts").text          # 审核前不展示

        # 站长审核通过
        aid = int(re.search(r"/admin/analysts/(\d+)/approve", admin.get("/admin").text).group(1))
        admin.post(f"/admin/analysts/{aid}/approve")
        ok(anon.get("/analysts?kind=ziwei"), "月白", "€19.00 起")
        page = ok(anon.get(f"/analysts/{aid}"), "紫微命盘详批", "€39.90")
        sid = int(re.search(r"紫微命盘详批.*?service_id=(\d+)", page.text, re.S).group(1))

        # 客户注册 → 先免费排盘（会记住出生信息）→ 下单
        ok(cli.post("/register", data={"role": "client", "email": "c@test.com", "password": "password1",
                                       "display_name": "小雨"}), "你好，小雨")
        cli.post("/ziwei", data={"birth_date": "1990-07-26", "birth_time": "16:00", "gender": "女"})
        ok(cli.get(f"/order/new?service_id={sid}"), 'value="1990-07-26"')
        r = cli.post("/order/new", data={"service_id": sid, "birth_date": "1990-07-26", "birth_time": "16:00",
                                         "gender": "女", "birth_place": "唐山", "question": "事业方向"})
        ok(r, "付款说明", "我已付款", "土五局")
        oid = int(re.search(r"/orders/(\d+)/paid", r.text).group(1))

        # 分析师此时看不到未付款订单的“接单”
        assert f"/orders/{oid}/accept" not in ana.get(f"/orders/{oid}").text
        # 其他人看不到订单
        assert anon.get(f"/orders/{oid}", follow_redirects=False).status_code == 303

        ok(cli.post(f"/orders/{oid}/paid", data={"payment_note": "PayPal 小雨"}), "正在核对收款")
        ok(admin.get("/admin"), "PayPal 小雨")
        admin.post(f"/admin/orders/{oid}/confirm")
        ok(ana.get("/me"), f"#{oid}", "待分析师接单")
        ok(ana.post(f"/orders/{oid}/accept"), "撰写解读报告")
        ok(cli.post(f"/orders/{oid}/message", data={"body": "我最近想换城市"}), "我最近想换城市")
        ok(ana.post(f"/orders/{oid}/deliver", data={"report": "你的命宫……\n第二段"}), "解读报告已交付")
        ok(cli.get(f"/orders/{oid}"), "你的命宫", "评价这次解读")
        ok(cli.post(f"/orders/{oid}/review", data={"rating": 5, "comment": "很治愈，谢谢"}), "谢谢你的评价")
        ok(anon.get(f"/analysts/{aid}"), "很治愈，谢谢", "已完成 1 单")
        ok(anon.get("/"), "很治愈，谢谢", "月白")
        ok(ana.get("/me"), "€31.92")                              # 39.9 × 80%
        ok(admin.get("/admin"), "€31.92")

        # 六爻订单：使用刚摇的卦
        cli.post("/liuyao", data={"question": "这份工作适合我吗", "tosses": "6,8,8,8,8,8"})
        lsid = int(re.search(r"六爻一事一问.*?service_id=(\d+)", page.text, re.S).group(1))
        r = cli.post("/order/new", data={"service_id": lsid, "question": "这份工作适合我吗", "use_last_gua": "1"})
        ok(r, "坤为地", "地雷复")

        # 合盘订单：带上刚才合盘填写的两个人
        cli.post("/hepan", data={"a_name": "小雨", "a_birth_date": "1992-03-18", "a_birth_time": "09:20", "a_gender": "女",
                                 "b_name": "阿杰", "b_birth_date": "1990-09-02", "b_birth_time": "20:00", "b_gender": "男",
                                 "relation": "friends"})
        hsid = int(re.search(r"八字合盘详解.*?service_id=(\d+)", page.text, re.S).group(1)) if "八字合盘详解" in page.text else \
            int(re.search(r"八字合盘详解.*?service_id=(\d+)", anon.get(f"/analysts/{aid}").text, re.S).group(1))
        ok(cli.get(f"/order/new?service_id={hsid}"), 'value="小雨"', 'value="1990-09-02"')
        r = cli.post("/order/new", data={"service_id": hsid, "relation": "friends",
                                         "a_name": "小雨", "a_birth_date": "1992-03-18", "a_birth_time": "09:20", "a_gender": "女",
                                         "b_name": "阿杰", "b_birth_date": "1990-09-02", "b_birth_time": "20:00", "b_gender": "男"})
        ok(r, "付款说明", "日支 · 内心深处", "阿杰滋养小雨")

        # 客户取消、设置修改
        oid2 = int(re.search(r"/orders/(\d+)/paid", r.text).group(1))
        ok(cli.post(f"/orders/{oid2}/cancel"), "订单已取消")
        ok(admin.post("/admin/settings", data={"payment_instructions": "Bizum 600000000", "platform_fee_pct": "15",
                                               "announcement": "双十二优惠", "contact": "抖音",
                                               "default_theme": "dunhuang"}), "双十二优惠")
        ok(cli.get("/"), 'data-theme="dunhuang"')                  # 站长设置的默认风格
        ok(cli.get("/"), "双十二优惠")


if __name__ == "__main__":
    test_full_flow()
    print("✓ full flow")
