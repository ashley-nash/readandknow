"""合盘文案。{A} {B} 是两个人的称呼，{wx} 是五行名。不打分，只写「默契之处」和「需要练习的地方」。"""
from .symbols import T

RELATION_TYPES = {
    "couple": T("恋人 / 伴侣", "Couple", "Pareja"),
    "friends": T("朋友", "Friends", "Amistad"),
    "partners": T("合作伙伴", "Business partners", "Socios"),
    "family": T("家人", "Family", "Familia"),
}

AREA = {
    "daymaster": T("日主 · 你们的核心性格", "Day masters · your core natures", "Maestros del día · vuestra esencia"),
    "tengod": T("在彼此命里的角色", "The role you play in each other's chart", "El papel de cada uno en la carta del otro"),
    "zodiac": T("生肖 · 年支", "Zodiac signs · year branch", "Signos del zodiaco · rama del año"),
    "daybranch_couple": T("日支 · 夫妻宫", "Day branch · spouse palace", "Rama del día · palacio del cónyuge"),
    "daybranch": T("日支 · 内心深处", "Day branch · inner self", "Rama del día · el yo interior"),
    "elements": T("五行互补", "How your elements complement", "Cómo se complementan vuestros elementos"),
}

# 地支关系
BRANCH_REL = {
    "liuhe": {"title": T("六合 · 天生默契", "Six Harmony · natural rapport", "Seis armonías · complicidad natural"),
              "gift": T("相处自然、互相吸引，很多事不用说就懂。", "Natural ease and attraction; much is understood without words.",
                        "Facilidad y atracción natural; mucho se entiende sin palabras."),
              "challenge": T("太合拍的时候容易忽略分歧，有问题也要说出来。",
                             "When it feels this easy, differences get ignored; still say what's wrong.",
                             "Cuando todo fluye se ignoran las diferencias; aun así, hablad de lo que no va bien.")},
    "sanhe": {"title": T("三合 · 走在同一条路上", "Triple Harmony · the same path", "Triple armonía · el mismo camino"),
              "gift": T("目标和节奏相近，容易一起做成事。", "Similar goals and rhythm; easy to get things done together.",
                        "Metas y ritmo parecidos; es fácil lograr cosas juntos."),
              "challenge": T("太像的两个人，也需要各自的空间。", "Two people this alike still need their own space.",
                             "Dos personas tan parecidas también necesitan su espacio.")},
    "chong": {"title": T("六冲 · 相反相成", "Clash · opposites that complete", "Choque · opuestos que se completan"),
              "gift": T("个性互补，能把彼此带出舒适区，火花多。",
                        "Complementary natures that pull each other out of comfort zones; plenty of sparks.",
                        "Caracteres complementarios que se sacan de la zona de confort; muchas chispas."),
              "challenge": T("节奏和习惯差异大，容易争执，需要练习“各退一步”。",
                             "Very different habits and pace, so arguments come easily; practise meeting halfway.",
                             "Hábitos y ritmos muy distintos, así que discutir es fácil; practicad ceder un poco cada uno.")},
    "xing": {"title": T("相刑 · 互相打磨", "Punishment · polishing each other", "Castigo · pulirse mutuamente"),
             "gift": T("会逼对方成长，让彼此变得更成熟。", "You push each other to grow and mature.", "Os empujáis a crecer y madurar."),
             "challenge": T("容易挑剔、误会、说话带刺，需要更多体谅。",
                            "Prone to nitpicking, misunderstandings and barbed words; more patience is needed.",
                            "Tendencia a criticar, malentendidos y palabras punzantes; hace falta más paciencia.")},
    "hai": {"title": T("相害 · 留心暗礁", "Harm · hidden reefs", "Daño · arrecifes ocultos"),
            "gift": T("提醒你们更细致地照顾彼此的感受。", "A reminder to look after each other's feelings more carefully.",
                      "Un recordatorio para cuidar más los sentimientos del otro."),
            "challenge": T("容易因为小事积累心结，有话要及时说开。", "Small things can pile up into resentment; clear the air early.",
                           "Las pequeñas cosas pueden acumularse; aclaradlas pronto.")},
    "same": {"title": T("同支 · 像照镜子", "Same branch · a mirror", "Misma rama · un espejo"),
             "gift": T("你们很像，容易理解对方。", "You are very alike and understand each other easily.",
                       "Os parecéis mucho y os entendéis fácilmente."),
             "challenge": T("优点相同，缺点也相同，看到对方就像看到自己。",
                            "Same strengths, same flaws: seeing them is like seeing yourself.",
                            "Mismas virtudes y mismos defectos: ver al otro es verte a ti.")},
    "none": {"title": T("平和 · 由你们自己书写", "Neutral · yours to write", "Neutral · lo escribís vosotros"),
             "gift": T("没有特别的合冲，关系的样子由你们自己决定。", "No special harmony or clash; you decide what this becomes.",
                       "Sin armonías ni choques especiales: vosotros decidís lo que será."),
             "challenge": T("需要主动经营，默契要靠时间慢慢积累。", "It needs active care; rapport builds with time.",
                            "Requiere cuidado activo; la complicidad se construye con el tiempo.")},
}

# 日主（日干五行）关系
DM_REL = {
    "same": {"title": T("同气相求 · 都是{wx}", "Kindred · both {wx}", "Afines · ambos {wx}"),
             "gift": T("价值观相近，容易成为彼此的同伴。", "Similar values; natural companions.", "Valores parecidos; compañeros naturales."),
             "challenge": T("都想做主的时候容易较劲，需要分工。", "When both want to lead, rivalry appears; divide the roles.",
                            "Cuando ambos quieren mandar surge la rivalidad; repartíos los papeles.")},
    "nourish": {"title": T("{A}滋养{B}", "{A} nourishes {B}", "{A} nutre a {B}"),
                "gift": T("{A}自然地给予支持和包容，{B}在关系里感到被照顾。",
                          "{A} naturally gives support and acceptance; {B} feels cared for.",
                          "{A} da apoyo y comprensión de forma natural; {B} se siente cuidado."),
                "challenge": T("{A}容易付出过多而疲惫；{B}记得回应和感谢。",
                               "{A} may give until exhausted; {B}, remember to give back and say thanks.",
                               "{A} puede dar hasta agotarse; {B}, recuerda corresponder y agradecer.")},
    "shape": {"title": T("{A}塑造{B}", "{A} shapes {B}", "{A} moldea a {B}"),
              "gift": T("{A}给{B}方向和推动力，能让{B}更有成就。",
                        "{A} gives {B} direction and drive, helping {B} achieve more.",
                        "{A} da a {B} dirección e impulso, y le ayuda a lograr más."),
              "challenge": T("{B}可能觉得被管、有压力；{A}记得用商量代替要求。",
                             "{B} may feel managed or pressured; {A}, ask rather than demand.",
                             "{B} puede sentirse controlado o presionado; {A}, propón en lugar de exigir.")},
}
STEM_COMBO = {"title": T("天干五合 · 相互吸引", "Stem combination · a mutual pull", "Combinación de troncos · atracción mutua"),
              "gift": T("你们的日主相合，彼此之间有一种说不清的吸引和亲近感。",
                        "Your day masters combine: a pull and closeness that is hard to explain.",
                        "Vuestros maestros del día se combinan: una atracción y cercanía difícil de explicar."),
              "challenge": T("“合”也意味着会改变彼此，记得保留各自的样子。",
                             "Combining also means changing each other; keep your own shapes.",
                             "Combinarse también significa cambiarse; conservad cada uno vuestra forma.")}

TENGOD_TITLE = T("对{A}来说，{B}像命中的「{tg}」", "To {A}, {B} is like the \"{tg}\" in their chart",
                 "Para {A}, {B} es como el «{tg}» de su carta")

COMPLEMENT = {"title": T("{A}的{wx}，补上{B}的不足", "{A}'s {wx} fills a gap in {B}", "El {wx} de {A} cubre un hueco de {B}"),
              "gift": T("在{B}缺少{wx}的地方，{A}能自然地带来这份力量。",
                        "Where {B} is short of {wx}, {A} naturally brings that strength.",
                        "Donde a {B} le falta {wx}, {A} aporta esa fuerza con naturalidad."),
              "challenge": T("别让互补变成依赖，{B}也可以慢慢培养自己的{wx}。",
                             "Don't let complement turn into dependence; {B} can grow their own {wx} too.",
                             "Que la complementariedad no se vuelva dependencia; {B} también puede cultivar su {wx}.")}
SHARED_WEAK = {"title": T("共同的课题：{wx}", "A shared lesson: {wx}", "Una lección compartida: {wx}"),
               "gift": T("你们都缺{wx}，更能体谅对方在这方面的难处。",
                         "You are both short of {wx}, so you understand each other's struggle there.",
                         "A ambos os falta {wx}, así que comprendéis la dificultad del otro."),
               "challenge": T("可以一起有意识地补上它：{tip}", "You can make up for it together: {tip}",
                              "Podéis compensarlo juntos: {tip}")}
SIMILAR = {"title": T("五行分布相近", "Similar elemental balance", "Equilibrio elemental parecido"),
           "gift": T("你们的能量结构相似，容易理解彼此的节奏。", "Your energies are built alike; you understand each other's rhythm.",
                     "Vuestras energías se parecen; entendéis el ritmo del otro."),
           "challenge": T("相似也意味着同样的短板，需要一起向外补充。", "Being alike also means the same blind spots; look outward together.",
                          "Pareceros también significa compartir puntos ciegos; buscad fuera juntos.")}
