"""六爻（金钱课）起卦与纳甲装卦。

算法思路
--------
1. 起卦：三枚铜钱掷六次，从下往上得到六爻。背面记 3、字面记 2，三枚相加：
       6 = 老阴（阴，动 → 变阳）   7 = 少阳（阳，静）
       8 = 少阴（阴，静）          9 = 老阳（阳，动 → 变阴）
   概率分别是 1/8、3/8、3/8、1/8 —— 用 secrets 模块产生真随机数。
2. 下三爻为内卦、上三爻为外卦，查表得到 64 卦卦名；动爻全部翻转得到变卦。
3. 八宫归属与世应：每宫从纯卦出发，依次翻转初爻、二爻……五爻，得到一世~五世卦；
   五世卦再翻回四爻为“游魂”，游魂卦内卦翻回本宫为“归魂”。
   提前生成 8×8 = 64 个卦的「所属宫、世爻位置」表，应爻 = 世爻 ± 3。
4. 纳甲：每个经卦内、外卦各有固定的天干地支（乾内甲子寅辰、外壬午申戌……）。
5. 六亲：以本宫五行为“我”，与爻支五行比较——同我兄弟、我生子孙、我克妻财、
   克我官鬼、生我父母。
6. 六神：由起卦当日的日干决定从哪一神开始，自初爻往上排。
"""
import secrets
from datetime import datetime

from lunar_python import Solar

from .common import BRANCH_WX, KE, SHENG
from ..content.readings import HEXAGRAMS

# 经卦：爻从下到上，1=阳 0=阴
TRIGRAMS = {
    (1, 1, 1): "乾", (1, 1, 0): "兑", (1, 0, 1): "离", (1, 0, 0): "震",
    (0, 1, 1): "巽", (0, 1, 0): "坎", (0, 0, 1): "艮", (0, 0, 0): "坤",
}
TRIGRAM_LINES = {v: k for k, v in TRIGRAMS.items()}
TRIGRAM_SYMBOL = {"乾": "☰", "兑": "☱", "离": "☲", "震": "☳", "巽": "☴", "坎": "☵", "艮": "☶", "坤": "☷"}
TRIGRAM_NATURE = {"乾": "天", "兑": "泽", "离": "火", "震": "雷", "巽": "风", "坎": "水", "艮": "山", "坤": "地"}
PALACE_WX = {"乾": "金", "兑": "金", "离": "火", "震": "木", "巽": "木", "坎": "水", "艮": "土", "坤": "土"}

# 纳甲：经卦 -> (内卦三爻干支, 外卦三爻干支)，从下往上
NAJIA = {
    "乾": (["甲子", "甲寅", "甲辰"], ["壬午", "壬申", "壬戌"]),
    "坤": (["乙未", "乙巳", "乙卯"], ["癸丑", "癸亥", "癸酉"]),
    "震": (["庚子", "庚寅", "庚辰"], ["庚午", "庚申", "庚戌"]),
    "巽": (["辛丑", "辛亥", "辛酉"], ["辛未", "辛巳", "辛卯"]),
    "坎": (["戊寅", "戊辰", "戊午"], ["戊申", "戊戌", "戊子"]),
    "离": (["己卯", "己丑", "己亥"], ["己酉", "己未", "己巳"]),
    "艮": (["丙辰", "丙午", "丙申"], ["丙戌", "丙子", "丙寅"]),
    "兑": (["丁巳", "丁卯", "丁丑"], ["丁亥", "丁酉", "丁未"]),
}

# 64 卦名：(上卦, 下卦) -> 卦名
_NAMES = """乾乾乾为天 坤坤坤为地 坎震水雷屯 艮坎山水蒙 坎乾水天需 乾坎天水讼 坤坎地水师 坎坤水地比
巽乾风天小畜 乾兑天泽履 坤乾地天泰 乾坤天地否 乾离天火同人 离乾火天大有 坤艮地山谦 震坤雷地豫
兑震泽雷随 艮巽山风蛊 坤兑地泽临 巽坤风地观 离震火雷噬嗑 艮离山火贲 艮坤山地剥 坤震地雷复
乾震天雷无妄 艮乾山天大畜 艮震山雷颐 兑巽泽风大过 坎坎坎为水 离离离为火 兑艮泽山咸 震巽雷风恒
乾艮天山遁 震乾雷天大壮 离坤火地晋 坤离地火明夷 巽离风火家人 离兑火泽睽 坎艮水山蹇 震坎雷水解
艮兑山泽损 巽震风雷益 兑乾泽天夬 乾巽天风姤 兑坤泽地萃 坤巽地风升 兑坎泽水困 坎巽水风井
兑离泽火革 离巽火风鼎 震震震为雷 艮艮艮为山 巽艮风山渐 震兑雷泽归妹 震离雷火丰 离艮火山旅
巽巽巽为风 兑兑兑为泽 巽坎风水涣 坎兑水泽节 巽兑风泽中孚 震艮雷山小过 坎离水火既济 离坎火水未济"""
HEX_NAME = {(w[0], w[1]): w[2:] for w in _NAMES.split()}

LIUSHEN = ["青龙", "朱雀", "勾陈", "螣蛇", "白虎", "玄武"]
LIUSHEN_START = {"甲": 0, "乙": 0, "丙": 1, "丁": 1, "戊": 2, "己": 3, "庚": 4, "辛": 4, "壬": 5, "癸": 5}


def _build_palace_table():
    """生成 64 卦 -> (所属宫, 世爻位置 1..6, 宫内序名)"""
    table = {}
    order = ["本宫", "一世", "二世", "三世", "四世", "五世", "游魂", "归魂"]
    shi = [6, 1, 2, 3, 4, 5, 4, 3]
    for palace, tri in TRIGRAM_LINES.items():
        h = list(tri + tri)
        seq = [tuple(h)]
        for i in range(5):            # 依次翻转初爻~五爻
            h[i] ^= 1
            seq.append(tuple(h))
        h[3] ^= 1                     # 游魂：五世卦翻回四爻
        seq.append(tuple(h))
        for i in range(3):            # 归魂：内卦翻回本宫
            h[i] ^= 1
        seq.append(tuple(h))
        for k, lines in enumerate(seq):
            table[lines] = (palace, shi[k], order[k])
    return table


PALACE_TABLE = _build_palace_table()
assert len(PALACE_TABLE) == 64 and len(HEX_NAME) == 64


def _liuqin(me: str, other: str) -> str:
    if me == other:
        return "兄弟"
    if SHENG[me] == other:
        return "子孙"
    if KE[me] == other:
        return "妻财"
    if KE[other] == me:
        return "官鬼"
    return "父母"


def _hexagram(lines6):
    lower, upper = TRIGRAMS[tuple(lines6[:3])], TRIGRAMS[tuple(lines6[3:])]
    palace, shi, order = PALACE_TABLE[tuple(lines6)]
    me = PALACE_WX[palace]
    najia = NAJIA[lower][0] + NAJIA[upper][1]
    yao = []
    for i in range(6):
        gz = najia[i]
        wx = BRANCH_WX[gz[1]]
        yao.append({"pos": i + 1, "yang": lines6[i] == 1, "ganzhi": gz, "wx": wx, "liuqin": _liuqin(me, wx),
                    "shi": i + 1 == shi, "ying": i + 1 == (shi + 3 - 1) % 6 + 1})
    name = HEX_NAME[(upper, lower)]
    return {
        "name": name, "upper": upper, "lower": lower,
        "symbol": TRIGRAM_SYMBOL[upper] + TRIGRAM_SYMBOL[lower],
        "image": f"上{TRIGRAM_NATURE[upper]}下{TRIGRAM_NATURE[lower]}",
        "palace": f"{palace}宫{order}", "palace_wx": me, "yao": yao,
        "name_tr": HEXAGRAMS[name]["name"],
        "message": HEXAGRAMS[name]["message"],
    }


def toss_coins() -> list:
    """模拟掷六次三枚铜钱，返回六个数字（6/7/8/9），从初爻到上爻。"""
    return [sum(secrets.choice((2, 3)) for _ in range(3)) for _ in range(6)]


def liuyao_chart(tosses=None, question: str = "", when: datetime | None = None) -> dict:
    tosses = tosses or toss_coins()
    if len(tosses) != 6 or any(t not in (6, 7, 8, 9) for t in tosses):
        raise ValueError("tosses 必须是 6 个 6/7/8/9 的数字")
    when = when or datetime.now()

    base = [1 if t in (7, 9) else 0 for t in tosses]
    moving = [t in (6, 9) for t in tosses]
    changed = [b ^ 1 if m else b for b, m in zip(base, moving)]

    lunar = Solar.fromYmdHms(when.year, when.month, when.day, when.hour, when.minute, 0).getLunar()
    day_gan = lunar.getDayGan()
    start = LIUSHEN_START[day_gan]

    ben = _hexagram(base)
    for i, y in enumerate(ben["yao"]):
        y["moving"] = moving[i]
        y["toss"] = tosses[i]
        y["liushen"] = LIUSHEN[(start + i) % 6]
    bian = _hexagram(changed) if any(moving) else None
    if bian:
        for y in bian["yao"]:   # 变卦六亲以本卦宫五行为准
            y["liuqin"] = _liuqin(ben["palace_wx"], y["wx"])

    return {
        "type": "liuyao",
        "question": question,
        "time": when.strftime("%Y-%m-%d %H:%M"),
        "ganzhi_date": f"{lunar.getYearInGanZhi()}年 {lunar.getMonthInGanZhi()}月 {lunar.getDayInGanZhi()}日",
        "xunkong": lunar.getDayXunKong(),
        "tosses": tosses,
        "ben": ben,
        "bian": bian,
        "moving_count": sum(moving),
    }
