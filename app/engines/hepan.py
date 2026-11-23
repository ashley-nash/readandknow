"""八字合盘：看两个人之间的关系线索。不算“匹配度”，只列出默契之处和需要练习的地方。

算法思路
--------
1. 分别排出两人的八字（复用 bazi_chart）。
2. 日主关系：比较两人日干的五行——同五行为“同气”，相生为“滋养”，相克为“塑造”；
   日干若构成天干五合（甲己、乙庚、丙辛、丁壬、戊癸），再加一条“相互吸引”。
3. 互为十神：把对方的日干放进自己的命盘，按“五行生克 + 阴阳是否相同”算出对方是你的哪一个十神。
       同我：同阴阳比肩、异阴阳劫财      我生：食神 / 伤官      我克：偏财 / 正财
       克我：七杀 / 正官                  生我：偏印 / 正印
4. 地支关系：两人的年支（生肖）和日支（恋人看“夫妻宫”）分别查六合、三合、六冲、相刑、相害。
5. 五行互补：一方某五行占比 ≥24%、另一方 ≤10%，记为“补上不足”；两人都 ≤10% 记为“共同的课题”。
"""
from ..content.hepan_texts import (AREA, BRANCH_REL, COMPLEMENT, DM_REL, RELATION_TYPES, SHARED_WEAK, SIMILAR,
                                   STEM_COMBO, TENGOD_TITLE)
from ..content.symbols import BRANCHES as BRANCH_INFO
from ..content.symbols import ELEMENTS, TEN_GODS
from .bazi import bazi_chart
from .common import KE, SHENG, STEM_WX, STEMS

LIUHE = {frozenset(p) for p in ("子丑", "寅亥", "卯戌", "辰酉", "巳申", "午未")}
CHONG = {frozenset(p) for p in ("子午", "丑未", "寅申", "卯酉", "辰戌", "巳亥")}
HAI = {frozenset(p) for p in ("子未", "丑午", "寅巳", "卯辰", "申亥", "酉戌")}
XING = {frozenset(p) for p in ("子卯", "寅巳", "巳申", "寅申", "丑戌", "戌未", "丑未")}
SELF_XING = set("辰午酉亥")
SANHE = ("申子辰", "亥卯未", "寅午戌", "巳酉丑")
STEM_HE = {frozenset(p) for p in ("甲己", "乙庚", "丙辛", "丁壬", "戊癸")}


def ten_god(day_master: str, other: str) -> str:
    """other 这个天干，对日主 day_master 来说是哪一个十神。"""
    me, it = STEM_WX[day_master], STEM_WX[other]
    same = STEMS.index(day_master) % 2 == STEMS.index(other) % 2
    if me == it:
        return "比肩" if same else "劫财"
    if SHENG[me] == it:
        return "食神" if same else "伤官"
    if KE[me] == it:
        return "偏财" if same else "正财"
    if KE[it] == me:
        return "七杀" if same else "正官"
    return "偏印" if same else "正印"


def branch_relations(a: str, b: str) -> list:
    if a == b:
        return ["same", "xing"] if a in SELF_XING else ["same"]
    pair = frozenset((a, b))
    rels = []
    if pair in LIUHE:
        rels.append("liuhe")
    if any(a in g and b in g for g in SANHE):
        rels.append("sanhe")
    if pair in CHONG:
        rels.append("chong")
    if pair in XING:
        rels.append("xing")
    if pair in HAI:
        rels.append("hai")
    return rels or ["none"]


def fmt(t: dict, **kw) -> dict:
    """把 {A}{B}{wx} 等占位符按语言填进去；值可以是普通字符串，也可以是三语字典。"""
    return {lang: s.format(**{k: (v[lang] if isinstance(v, dict) else v) for k, v in kw.items()})
            for lang, s in t.items()}


def _item(kind, block, **kw):
    return {"kind": kind, "title": fmt(block["title"], **kw), "gift": fmt(block["gift"], **kw),
            "challenge": fmt(block["challenge"], **kw)}


def hepan_chart(a: dict, b: dict, relation: str = "couple") -> dict:
    """a / b: {"name", "year", "month", "day", "hour", "minute", "gender"}"""
    relation = relation if relation in RELATION_TYPES else "couple"
    A, B = (a.get("name") or "A").strip()[:12], (b.get("name") or "B").strip()[:12]
    ca = bazi_chart(a["year"], a["month"], a["day"], a["hour"], a.get("minute", 0), a.get("gender", "女"))
    cb = bazi_chart(b["year"], b["month"], b["day"], b["hour"], b.get("minute", 0), b.get("gender", "女"))
    da, db = ca["day_master"]["gan"], cb["day_master"]["gan"]
    wa, wb = STEM_WX[da], STEM_WX[db]
    cards = []

    # 1) 日主
    items = []
    if wa == wb:
        items.append(_item("same", DM_REL["same"], A=A, B=B, wx=ELEMENTS[wa]["name"]))
    elif SHENG[wa] == wb:
        items.append(_item("nourish", DM_REL["nourish"], A=A, B=B))
    elif SHENG[wb] == wa:
        items.append(_item("nourish", DM_REL["nourish"], A=B, B=A))
    elif KE[wa] == wb:
        items.append(_item("shape", DM_REL["shape"], A=A, B=B))
    else:
        items.append(_item("shape", DM_REL["shape"], A=B, B=A))
    if frozenset((da, db)) in STEM_HE:
        items.append(_item("combo", STEM_COMBO))
    cards.append({"area": AREA["daymaster"], "left": {"name": A, "sym": da, "kind": "stem"},
                  "right": {"name": B, "sym": db, "kind": "stem"}, "items": items})

    # 2) 互为十神
    tg_ab, tg_ba = ten_god(da, db), ten_god(db, da)
    items = []
    for who, other, tg in ((A, B, tg_ab), (B, A, tg_ba)):
        g = TEN_GODS[tg]
        items.append({"kind": "tengod", "tengod": tg, "title": fmt(TENGOD_TITLE, A=who, B=other, tg=g["name"]),
                      "gift": g["gift"], "challenge": g["shadow"], "rel": g["rel"]})
    cards.append({"area": AREA["tengod"], "left": {"name": A, "sym": tg_ab, "kind": "tengod"},
                  "right": {"name": B, "sym": tg_ba, "kind": "tengod"}, "items": items})

    # 3) 生肖 / 4) 日支
    for area, ia in (("zodiac", 0), ("daybranch_couple" if relation == "couple" else "daybranch", 2)):
        za, zb = ca["pillars"][ia]["zhi"], cb["pillars"][ia]["zhi"]
        items = [_item(r, BRANCH_REL[r]) for r in branch_relations(za, zb)]
        cards.append({"area": AREA[area], "left": {"name": A, "sym": za, "kind": "branch"},
                      "right": {"name": B, "sym": zb, "kind": "branch"}, "items": items})

    # 5) 五行互补
    pa = {w["wx"]: w["pct"] for w in ca["wuxing"]}
    pb = {w["wx"]: w["pct"] for w in cb["wuxing"]}
    items = []
    for w in pa:
        if pa[w] >= 24 and pb[w] <= 10:
            items.append(_item("complement", COMPLEMENT, A=A, B=B, wx=ELEMENTS[w]["name"]))
        if pb[w] >= 24 and pa[w] <= 10:
            items.append(_item("complement", COMPLEMENT, A=B, B=A, wx=ELEMENTS[w]["name"]))
    for w in pa:
        if pa[w] <= 10 and pb[w] <= 10:
            items.append(_item("shared", SHARED_WEAK, wx=ELEMENTS[w]["name"], tip=ELEMENTS[w]["tip"]))
    if not items:
        items.append(_item("similar", SIMILAR))
    cards.append({"area": AREA["elements"], "left": None, "right": None, "items": items})

    return {
        "type": "hepan",
        "relation": relation,
        "relation_label": RELATION_TYPES[relation],
        "a": {"name": A, "chart": ca, "animal": BRANCH_INFO[ca["pillars"][0]["zhi"]]["animal"]},
        "b": {"name": B, "chart": cb, "animal": BRANCH_INFO[cb["pillars"][0]["zhi"]]["animal"]},
        "cards": cards,
    }
