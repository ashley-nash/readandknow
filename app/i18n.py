"""多语言：中文为主，可选「中英对照」「中西对照」「纯中文」。

模板里这样写：
    {{ t("免费排盘") }}              → 中文 + 下方小字译文（块级）
    {{ t("免费排盘", inline=True) }} → 中文 + 同一行译文
    {{ s("你想问的事") }}            → 纯文本 “你想问的事 · What's your question?”（用于 placeholder / title）
    {{ L(chart.day_master.gift) }}   → 三语字典 {"zh","en","es"} 的对照显示
UI 字典以中文原文为键，翻译放在 app/content/ui_strings.py。
"""
from markupsafe import Markup, escape

from .content.ui_strings import UI

MODES = {"zh-en": "en", "zh-es": "es", "zh": None}
DEFAULT_MODE = "zh-en"
MODE_LABELS = {"zh-en": "中·EN", "zh-es": "中·ES", "zh": "中文"}

MISSING = set()          # 开发时用来找出还没翻译的文字


class I18n:
    def __init__(self, mode: str | None):
        self.mode = mode if mode in MODES else DEFAULT_MODE
        self.second = MODES[self.mode]

    # 核心：把一对 (中文, 译文) 变成 HTML
    def _pair(self, zh: str, tr: str | None, inline: bool) -> Markup:
        zh_html = escape(zh)
        if not self.second or not tr:
            return Markup(f'<span class="bi"><span class="zh">{zh_html}</span></span>')
        cls = "bi inline" if inline else "bi"
        return Markup(f'<span class="{cls}"><span class="zh">{zh_html}</span>'
                      f'<span class="tr" lang="{self.second}">{escape(tr)}</span></span>')

    def _lookup(self, zh: str):
        entry = UI.get(zh)
        if entry is None:
            MISSING.add(zh)
            return None
        return entry[0] if self.second == "en" else entry[1] if self.second == "es" else None

    def t(self, zh: str, inline: bool = False, **kw) -> Markup:
        tr = self._lookup(zh)
        if kw:
            zh = zh.format(**kw)
            tr = tr.format(**kw) if tr else tr
        return self._pair(zh, tr, inline)

    def s(self, zh: str, **kw) -> str:
        tr = self._lookup(zh)
        if kw:
            zh = zh.format(**kw)
            tr = tr.format(**kw) if tr else tr
        return f"{zh} · {tr}" if (self.second and tr) else zh

    def tr_only(self, zh: str) -> str:
        """只要译文（没有就返回中文）。"""
        return self._lookup(zh) or zh

    def L(self, value, inline: bool = False) -> Markup:
        if isinstance(value, dict):
            return self._pair(value.get("zh", ""), value.get(self.second) if self.second else None, inline)
        return self._pair(str(value or ""), None, inline)

    def Ls(self, value) -> str:
        if isinstance(value, dict):
            zh, tr = value.get("zh", ""), value.get(self.second) if self.second else None
            return f"{zh} · {tr}" if tr else zh
        return str(value or "")

    def one(self, value) -> str:
        """三语字典里取当前第二语言（没有就中文），用在只放得下一种语言的地方。"""
        if isinstance(value, dict):
            return value.get(self.second) or value.get("zh", "") if self.second else value.get("zh", "")
        return str(value or "")
