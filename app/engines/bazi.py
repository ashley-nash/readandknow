"""八字（四柱）排盘。

算法思路
--------
1. 八字的年、月柱以「节气」为界（立春换年、每月的“节”换月），不是以农历初一为界。
   节气需要精确的天文历表，所以这里用成熟的开源库 lunar_python 来做公历→干支的换算。
2. 日柱按六十甲子连续循环；时柱由「日干 + 时辰」用“五鼠遁”推出（库内完成）。
3. 在四柱基础上计算：十神（与日主的生克关系）、藏干、纳音、十二长生、五行统计、大运。
4. 五行统计：天干、地支本气各记 1 分，地支藏干中的余气各记 0.3 分，
   得到一个“五行能量分布”，再找出最旺 / 最弱的五行，给出温和的调和建议。
"""
from lunar_python import Solar

from .common import BRANCH_WX, STEM_WX, WX, WX_COLOR
from ..content.symbols import ELEMENTS, STEMS as STEM_INFO, TEN_GOD_ORDER


def _pillar(label, gan, zhi, shishen_gan, hide_gan, hide_shishen, nayin, dishi, xunkong):
    return {
        "label": label,
        "gan": gan,
        "zhi": zhi,
        "gan_wx": STEM_WX[gan],
        "zhi_wx": BRANCH_WX[zhi],
        "shishen": shishen_gan,
        "hide": [{"gan": g, "wx": STEM_WX[g], "shishen": s} for g, s in zip(hide_gan, hide_shishen)],
        "nayin": nayin,
        "dishi": dishi,
        "xunkong": xunkong,
    }


def bazi_chart(year: int, month: int, day: int, hour: int, minute: int = 0, gender: str = "女") -> dict:
    solar = Solar.fromYmdHms(year, month, day, hour, minute, 0)
    lunar = solar.getLunar()
    ec = lunar.getEightChar()

    pillars = [
        _pillar("年柱", ec.getYearGan(), ec.getYearZhi(), ec.getYearShiShenGan(), ec.getYearHideGan(),
                ec.getYearShiShenZhi(), ec.getYearNaYin(), ec.getYearDiShi(), ec.getYearXunKong()),
        _pillar("月柱", ec.getMonthGan(), ec.getMonthZhi(), ec.getMonthShiShenGan(), ec.getMonthHideGan(),
                ec.getMonthShiShenZhi(), ec.getMonthNaYin(), ec.getMonthDiShi(), ec.getMonthXunKong()),
        _pillar("日柱", ec.getDayGan(), ec.getDayZhi(), "日主", ec.getDayHideGan(),
                ec.getDayShiShenZhi(), ec.getDayNaYin(), ec.getDayDiShi(), ec.getDayXunKong()),
        _pillar("时柱", ec.getTimeGan(), ec.getTimeZhi(), ec.getTimeShiShenGan(), ec.getTimeHideGan(),
                ec.getTimeShiShenZhi(), ec.getTimeNaYin(), ec.getTimeDiShi(), ec.getTimeXunKong()),
    ]

    # ---- 五行能量统计 ----
    score = {w: 0.0 for w in WX}
    for p in pillars:
        score[p["gan_wx"]] += 1.0
        score[p["zhi_wx"]] += 1.0
        for h in p["hide"][1:]:          # 第一个藏干是本气，已经算在地支里了
            score[h["wx"]] += 0.3
    total = sum(score.values())
    wuxing = [
        {"wx": w, "score": round(score[w], 1), "pct": round(score[w] / total * 100), "color": WX_COLOR[w]}
        for w in WX
    ]
    strongest = max(WX, key=lambda w: score[w])
    weakest = min(WX, key=lambda w: score[w])

    # ---- 大运 ----
    is_male = gender == "男"
    yun = ec.getYun(1 if is_male else 0)
    dayun = [
        {"ganzhi": d.getGanZhi(), "start_age": d.getStartAge(), "start_year": d.getStartYear()}
        for d in yun.getDaYun()[1:9]   # 第 0 项是起运前的童限，跳过
    ]

    # ---- 命中出现的十神（天干 + 藏干），按出现次数排序；每个都只讲利弊 ----
    count = {}
    for p in pillars:
        for name in [p["shishen"]] + [h["shishen"] for h in p["hide"]]:
            if name in TEN_GOD_ORDER:
                count[name] = count.get(name, 0) + 1
    tengods = sorted(count, key=lambda n: (-count[n], TEN_GOD_ORDER.index(n)))

    day_gan = ec.getDayGan()
    return {
        "type": "bazi",
        "solar": f"{year}年{month}月{day}日 {hour:02d}:{minute:02d}",
        "lunar": f"农历{lunar.getYearInGanZhi()}年 {lunar.getMonthInChinese()}月{lunar.getDayInChinese()} {lunar.getTimeZhi()}时",
        "zodiac": lunar.getYearShengXiaoByLiChun(),
        "gender": "男" if is_male else "女",
        "pillars": pillars,
        "bazi_str": f"{ec.getYear()} {ec.getMonth()} {ec.getDay()} {ec.getTime()}",
        "day_master": {"gan": day_gan, "wx": STEM_WX[day_gan], **STEM_INFO[day_gan]},
        "wuxing": wuxing,
        "strongest": strongest,
        "weakest": weakest,
        "balance_tip": ELEMENTS[weakest]["tip"],
        "strong_gift": ELEMENTS[strongest]["gift"],
        "strong_shadow": ELEMENTS[strongest]["shadow"],
        "tengods": tengods,
        "qiyun": f"出生后约 {yun.getStartYear()} 年 {yun.getStartMonth()} 个月起运，大运{'顺' if yun.isForward() else '逆'}排",
        "dayun": dayun,
        "minggong": ec.getMingGong(),
        "taiyuan": ec.getTaiYuan(),
    }
