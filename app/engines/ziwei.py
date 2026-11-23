"""紫微斗数排盘（十四主星 + 常用辅星 + 生年四化 + 大限）。

算法思路（地支用 0..11 表示 子..亥，寅 = 2）
----------------------------------------------
1. 公历 → 农历（lunar_python）。紫微斗数用「农历正月初一」换年（不是立春）。
   23:00 以后的晚子时按次日算；闰月前 15 天算本月、后半月算下个月。
2. 安命宫 / 身宫：从寅宫起正月，顺数到生月；再从该宫起子时，
       命宫逆数到生时，身宫顺数到生时。
       命宫 = (2 + 月 - 1 - 时) mod 12，身宫 = (2 + 月 - 1 + 时) mod 12
3. 十二宫天干：用“五虎遁”由年干定寅宫天干，其余宫顺推。
4. 五行局：命宫干支的纳音五行 → 水二局 / 木三局 / 金四局 / 土五局 / 火六局。
5. 定紫微星：设局数 J、农历日 D，找最小的 x≥0 使 (D+x) 能被 J 整除，商为 q。
       从寅宫数 q 格；x 为偶数再顺进 x 格，x 为奇数则逆退 x 格。
6. 天府与紫微以“寅—申”线对称：天府 = (4 - 紫微) mod 12。
7. 紫微星系逆布：天机-1、太阳-3、武曲-4、天同-5、廉贞-8；
   天府星系顺布：太阴+1、贪狼+2、巨门+3、天相+4、天梁+5、七杀+6、破军+10。
8. 辅星按年干 / 年支 / 月 / 时的口诀查表；四化按年干查表。
9. 大限：起于局数，阳男阴女从命宫顺行，阴男阳女逆行，每宫十年。
"""
from datetime import datetime, timedelta

from lunar_python import Solar

from .common import BRANCHES, STEMS, hour_to_branch, nayin
from ..content.readings import STARS

PALACE_NAMES = ["命宫", "兄弟", "夫妻", "子女", "财帛", "疾厄",
                "迁移", "交友", "官禄", "田宅", "福德", "父母"]

JU = {"水": 2, "木": 3, "金": 4, "土": 5, "火": 6}
JU_NAME = {2: "水二局", 3: "木三局", 4: "金四局", 5: "土五局", 6: "火六局"}

# 四化：年干 -> (化禄, 化权, 化科, 化忌)
SIHUA = {
    "甲": ("廉贞", "破军", "武曲", "太阳"),
    "乙": ("天机", "天梁", "紫微", "太阴"),
    "丙": ("天同", "天机", "文昌", "廉贞"),
    "丁": ("太阴", "天同", "天机", "巨门"),
    "戊": ("贪狼", "太阴", "右弼", "天机"),
    "己": ("武曲", "贪狼", "天梁", "文曲"),
    "庚": ("太阳", "武曲", "太阴", "天同"),
    "辛": ("巨门", "太阳", "文曲", "文昌"),
    "壬": ("天梁", "紫微", "左辅", "武曲"),
    "癸": ("破军", "巨门", "太阴", "贪狼"),
}
SIHUA_TAGS = ("禄", "权", "科", "忌")

# 禄存：年干 -> 地支序号
LUCUN = {"甲": 2, "乙": 3, "丙": 5, "丁": 6, "戊": 5, "己": 6, "庚": 8, "辛": 9, "壬": 11, "癸": 0}
# 天魁、天钺：甲戊庚牛羊，乙己鼠猴乡，丙丁猪鸡位，壬癸兔蛇藏，六辛逢马虎
KUI_YUE = {"甲": (1, 7), "戊": (1, 7), "庚": (1, 7), "乙": (0, 8), "己": (0, 8),
           "丙": (11, 9), "丁": (11, 9), "壬": (3, 5), "癸": (3, 5), "辛": (6, 2)}

# 命主（按命宫地支）、身主（按年支）
MING_ZHU = ["贪狼", "巨门", "禄存", "文曲", "廉贞", "武曲", "破军", "武曲", "廉贞", "文曲", "禄存", "巨门"]
SHEN_ZHU = ["火星", "天相", "天梁", "天同", "文昌", "天机", "火星", "天相", "天梁", "天同", "文昌", "天机"]

# 命盘 4x4 格子里每个地支的位置 (行, 列)
GRID_POS = {5: (0, 0), 6: (0, 1), 7: (0, 2), 8: (0, 3), 4: (1, 0), 9: (1, 3),
            3: (2, 0), 10: (2, 3), 2: (3, 0), 1: (3, 1), 0: (3, 2), 11: (3, 3)}


def _ziwei_position(ju: int, lunar_day: int) -> int:
    x = 0
    while (lunar_day + x) % ju != 0:
        x += 1
    q = (lunar_day + x) // ju
    pos = 2 + q - 1                      # 从寅宫数 q 格
    pos = pos + x if x % 2 == 0 else pos - x
    return pos % 12


def _group(branch: int) -> int:
    """三合局分组：0=申子辰 1=巳酉丑 2=寅午戌 3=亥卯未"""
    return {8: 0, 0: 0, 4: 0, 5: 1, 9: 1, 1: 1, 2: 2, 6: 2, 10: 2, 11: 3, 3: 3, 7: 3}[branch]


def ziwei_chart(year: int, month: int, day: int, hour: int, minute: int = 0, gender: str = "女") -> dict:
    # 1) 农历日期（晚子时算次日）
    dt = datetime(year, month, day, hour, minute)
    calc_dt = dt + timedelta(hours=1) if hour == 23 else dt
    lunar = Solar.fromYmdHms(calc_dt.year, calc_dt.month, calc_dt.day, calc_dt.hour, calc_dt.minute, 0).getLunar()

    lm, ld = lunar.getMonth(), lunar.getDay()
    is_leap = lm < 0
    lm = abs(lm)
    if is_leap and ld > 15:
        lm = lm % 12 + 1

    year_gan = lunar.getYearGan()
    year_zhi = lunar.getYearZhi()
    ys, yb = STEMS.index(year_gan), BRANCHES.index(year_zhi)
    h = hour_to_branch(hour)

    # 2) 命宫、身宫
    ming = (2 + lm - 1 - h) % 12
    shen = (2 + lm - 1 + h) % 12

    # 3) 十二宫天干（五虎遁）
    yin_stem = ((ys % 5) * 2 + 2) % 10

    def palace_stem(b: int) -> int:
        return (yin_stem + (b - 2) % 12) % 10

    # 4) 五行局
    ming_nayin = nayin(palace_stem(ming), ming)
    ju = JU[ming_nayin[-1]]

    # 5)~7) 十四主星
    zw = _ziwei_position(ju, ld)
    tf = (4 - zw) % 12
    main = {
        "紫微": zw, "天机": zw - 1, "太阳": zw - 3, "武曲": zw - 4, "天同": zw - 5, "廉贞": zw - 8,
        "天府": tf, "太阴": tf + 1, "贪狼": tf + 2, "巨门": tf + 3, "天相": tf + 4,
        "天梁": tf + 5, "七杀": tf + 6, "破军": tf + 10,
    }
    main = {k: v % 12 for k, v in main.items()}

    # 8) 辅星
    lucun = LUCUN[year_gan]
    kui, yue = KUI_YUE[year_gan]
    huo_start, ling_start = [(2, 10), (3, 10), (1, 3), (9, 10)][_group(yb)]
    aux = {
        "文昌": (10 - h) % 12, "文曲": (4 + h) % 12,
        "左辅": (4 + lm - 1) % 12, "右弼": (10 - (lm - 1)) % 12,
        "天魁": kui, "天钺": yue,
        "禄存": lucun, "擎羊": (lucun + 1) % 12, "陀罗": (lucun - 1) % 12,
        "地空": (11 - h) % 12, "地劫": (11 + h) % 12,
        "火星": (huo_start + h) % 12, "铃星": (ling_start + h) % 12,
        "天马": [2, 11, 8, 5][_group(yb)],
        "红鸾": (3 - yb) % 12, "天喜": (9 - yb) % 12,
    }
    good_aux = {"文昌", "文曲", "左辅", "右弼", "天魁", "天钺", "禄存", "天马", "红鸾", "天喜"}

    # 生年四化
    sihua = dict(zip(SIHUA[year_gan], SIHUA_TAGS))

    # 9) 大限：阳男阴女顺行，阴男阳女逆行
    is_male = gender == "男"
    yang_year = ys % 2 == 0
    forward = (yang_year and is_male) or (not yang_year and not is_male)

    palaces = {}
    for i, name in enumerate(PALACE_NAMES):
        b = (ming - i) % 12
        palaces[b] = {"name": name, "branch": BRANCHES[b], "stem": STEMS[palace_stem(b)],
                      "main": [], "aux": [], "is_ming": b == ming, "is_shen": b == shen}
    for star, b in main.items():
        palaces[b]["main"].append({"name": star, "hua": sihua.get(star, "")})
    for star, b in aux.items():
        palaces[b]["aux"].append({"name": star, "hua": sihua.get(star, ""), "good": star in good_aux})
    for k in range(12):
        b = (ming + k) % 12 if forward else (ming - k) % 12
        start = ju + 10 * k
        palaces[b]["daxian"] = f"{start}-{start + 9}"

    grid = []
    for b, (r, c) in GRID_POS.items():
        grid.append({**palaces[b], "row": r + 1, "col": c + 1})

    # 命宫主星解读（空宫借对宫）
    ming_stars = [s["name"] for s in palaces[ming]["main"]]
    borrowed = False
    if not ming_stars:
        ming_stars = [s["name"] for s in palaces[(ming + 6) % 12]["main"]]
        borrowed = True
    readings = [{"star": s, **STARS[s]} for s in ming_stars]

    return {
        "type": "ziwei",
        "solar": f"{year}年{month}月{day}日 {hour:02d}:{minute:02d}",
        "lunar": f"农历{year_gan}{year_zhi}年 {lunar.getMonthInChinese()}月{lunar.getDayInChinese()} {BRANCHES[h]}时",
        "gender": "男" if is_male else "女",
        "yinyang": ("阳" if yang_year else "阴") + ("男" if is_male else "女"),
        "ju": JU_NAME[ju],
        "ming_branch": BRANCHES[ming],
        "shen_branch": BRANCHES[shen],
        "shen_palace": palaces[shen]["name"],
        "ming_zhu": MING_ZHU[ming],
        "shen_zhu": SHEN_ZHU[yb],
        "sihua": [{"star": s, "tag": t} for s, t in zip(SIHUA[year_gan], SIHUA_TAGS)],
        "grid": grid,
        "palaces_by_branch": palaces,
        "main_positions": {k: BRANCHES[v] for k, v in main.items()},
        "ming_stars": ming_stars,
        "ming_borrowed": borrowed,
        "readings": readings,
    }
