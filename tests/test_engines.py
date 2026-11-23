"""排盘引擎自测：python -m pytest tests  （或 python tests/test_engines.py）"""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.engines import bazi_chart, hepan_chart, liuyao_chart, ten_god, ziwei_chart  # noqa: E402
from app.engines.hepan import branch_relations  # noqa: E402
from app.engines.liuyao import PALACE_TABLE, TRIGRAM_LINES  # noqa: E402


def hexa(upper, lower):
    return TRIGRAM_LINES[lower] + TRIGRAM_LINES[upper]


def test_bazi_known_date():
    c = bazi_chart(2000, 1, 1, 12, 0, "男")
    assert c["bazi_str"] == "己卯 丙子 戊午 戊午"
    assert c["day_master"]["gan"] == "戊"
    assert len(c["dayun"]) == 8
    assert abs(sum(w["pct"] for w in c["wuxing"]) - 100) <= 2


def test_ziwei_ziwei_star_rule():
    # 已知口诀：各局初一紫微的位置
    from app.engines.ziwei import _ziwei_position
    assert [_ziwei_position(j, 1) for j in (2, 3, 4, 5, 6)] == [1, 4, 11, 6, 9]  # 丑 辰 亥 午 酉


def test_ziwei_chart_shape():
    c = ziwei_chart(1990, 7, 26, 16, 0, "女")
    assert c["ming_branch"] == "亥" and c["ju"] == "土五局"          # 与 iztro 一致
    assert c["main_positions"]["紫微"] == "寅"
    assert len(c["grid"]) == 12
    assert sum(len(p["main"]) for p in c["grid"]) == 14


def test_liuyao_palaces():
    # 乾为天：乾宫本宫，世六应三
    p, shi, _ = PALACE_TABLE[tuple(hexa("乾", "乾"))]
    assert (p, shi) == ("乾", 6)
    # 天风姤：乾宫一世；地火明夷：坎宫游魂；天火同人：离宫归魂
    assert PALACE_TABLE[tuple(hexa("乾", "巽"))][:2] == ("乾", 1)
    assert PALACE_TABLE[tuple(hexa("坤", "离"))][:2] == ("坎", 4)
    assert PALACE_TABLE[tuple(hexa("乾", "离"))][:2] == ("离", 3)


def test_liuyao_najia_liuqin():
    c = liuyao_chart([7, 7, 7, 7, 7, 7], when=datetime(2024, 1, 1, 10, 0))
    yao = c["ben"]["yao"]
    assert c["ben"]["name"] == "乾为天" and c["bian"] is None
    assert [y["ganzhi"] for y in yao] == ["甲子", "甲寅", "甲辰", "壬午", "壬申", "壬戌"]
    assert [y["liuqin"] for y in yao] == ["子孙", "妻财", "父母", "官鬼", "兄弟", "父母"]
    assert yao[5]["shi"] and yao[2]["ying"]


def test_liuyao_moving_lines():
    c = liuyao_chart([9, 7, 7, 7, 7, 7], when=datetime(2024, 1, 1, 10, 0))
    assert c["bian"]["name"] == "天风姤" and c["moving_count"] == 1


def test_ten_god_matches_lunar_python():
    import random
    from lunar_python import Solar
    random.seed(3)
    for _ in range(300):
        ec = Solar.fromYmdHms(random.randint(1940, 2030), random.randint(1, 12), random.randint(1, 28),
                              random.randint(0, 23), 0, 0).getLunar().getEightChar()
        assert ten_god(ec.getDayGan(), ec.getMonthGan()) == ec.getMonthShiShenGan()
        assert ten_god(ec.getDayGan(), ec.getTimeGan()) == ec.getTimeShiShenGan()


def test_branch_relations():
    assert branch_relations("子", "丑") == ["liuhe"]
    assert branch_relations("子", "午") == ["chong"]
    assert branch_relations("寅", "申") == ["chong", "xing"]
    assert branch_relations("申", "辰") == ["sanhe"]
    assert branch_relations("子", "未") == ["hai"]
    assert branch_relations("午", "午") == ["same", "xing"]
    assert branch_relations("子", "寅") == ["none"]


def test_hepan_has_no_score_and_all_cards():
    h = hepan_chart({"name": "A", "year": 1992, "month": 3, "day": 18, "hour": 9},
                    {"name": "B", "year": 1990, "month": 9, "day": 2, "hour": 20, "gender": "男"}, "couple")
    assert [c["area"]["zh"].split(" ")[0] for c in h["cards"]] == ["日主", "在彼此命里的角色", "生肖", "日支", "五行互补"]
    assert all(it["gift"]["en"] and it["challenge"]["es"] for c in h["cards"] for it in c["items"])
    # 关系本身没有任何分数 / 匹配度字段
    assert not any(k in h for k in ("score", "match", "percent"))
    assert "score" not in str(h["cards"]).lower() and "%" not in str(h["cards"])


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("✓", name)
