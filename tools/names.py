#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Реестр названий: что является названием, в каком словаре pn_* ему место.

    python tools/names.py scan     # построить реестр в графе (таблицы name, route)
    python tools/names.py gap [<класс>]   # названия, которых нет в слое pn_*
    python tools/names.py inline   # где общий словарь перевёл имя вместо латиницы
    python tools/names.py emit [<класс>]  # заготовки строк для pn/*.csv по дырам

Зачем. Выключатель «названия по-английски» работает так: словари `pn_*` гасятся,
и игрок видит оригинал — но только если в общем словаре имя оставлено латиницей
или строки там нет вовсе. Значит у каждого названия должно быть ДВА свойства:
оно заведено в `pn_*`, и общий словарь его не переводит. Ни одно из двух нигде
не проверялось. Реестр проверяет оба и говорит, чего не хватает.

Реестр выводится из API-кэша, категорий bin и слоя — как и весь граф, он не
версионируется. Версионируется только раскладка «класс -> словарь» в NAMEMAP.md.
"""
import collections, csv, glob, os, re, sqlite3, sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
CROWD = os.path.dirname(HERE)
DB = os.path.join(CROWD, "sync", "index.db")
sys.path.insert(0, HERE)
import dict_tool as D

PER_FILE = 500                      # столько же строк в файле, сколько в pn/ сейчас
# Ранговый префикс существа. `Ambient` в список НЕ входит, хотя ранг такой в игре
# есть: тем же словом названы настройки графики («Ambient Occlusion», «Ambient
# Audio»), и все три находки по нему оказались ложными.
RANK = re.compile(r"^(Champion|Veteran|Legendary|Elite)\b")
STRIP_STR = re.compile(r"%str\d+%")
STRIP_PL = re.compile(r"\[(?:s|pl:\"[^\"]*\")\]")

# Категории bin, где ВСЯ строка — название вещи, а не фраза. Список закрытый:
# «похоже на название» ловит хвосты флейвора, поэтому класс берём от источника.
# `wizardsvault` здесь больше нет (2026-09-28): там задания Хранилища
# («Defeat 25 Enemies», «Log In»), а не названия — см. NAMEMAP.md.
NAME_CATS = {
    "item_names": "items", "skins": "skins", "minis": "minis",
    "achievement_names": "achievements", "achievement_categories": "achievements",
    "achievement_groups": "achievements", "titles": "titles", "colors": "colors",
    "currencies": "currencies", "outfits": "outfits", "gliders": "gliders",
    "mounts": "mounts", "pets": "pets", "novelties": "novelties",
    "finishers": "finishers", "mailcarriers": "mailcarriers", "skiffs": "skiffs",
    "jadebots": "jadebots", "masteries": "masteries", "maps": "places",
    "guild_upgrades": "guild", "specializations": "skills", "professions": "skills",
    "skill_names": "skills", "traits": "skills", "wvw_objectives": "wvw",
    "wvw_abilities": "wvw", "wvw_ranks": "wvw", "pvp_ranks": "pvp",
    "pvp_heroes": "pvp", "itemstats": "itemstats",
    "materials": "items",
}
# Категории второстепенного контента: имена оттуда — это NPC и монстры квестов.
SIDE_CATS = {"events", "renown_hearts", "zone_dialogue", "npc_dialogue"}
# Сюжет трогать не договорились — класс проставляем, но в дыры он не идёт.
STORY_CATS = {
    "personal_story", "living_world_season_1", "living_world_season_2",
    "living_world_season_3", "living_world_season_4", "heart_of_thorns",
    "path_of_fire", "end_of_dragons", "the_icebrood_saga", "janthir_wilds",
    "secrets_of_the_obscure", "visions_of_eternity", "stories", "stories_seasons",
    "backstory", "quests",
}


def key(s):
    s = STRIP_PL.sub("", STRIP_STR.sub("", s or ""))
    return re.sub(r"\s{2,}", " ", s).strip()


def load_namemap():
    """Раскладка «класс названия -> словарь pn_*» из NAMEMAP.md.

    Держим её в версионируемом файле, а не в коде: это решение мейнтейнера, от
    него зависит, сколько выключателей увидит игрок, и меняться оно будет чаще,
    чем сам разбор.
    """
    fp = os.path.join(CROWD, "NAMEMAP.md")
    out = {}
    if not os.path.exists(fp):
        return out
    for line in open(fp, encoding="utf-8"):
        c = [x.strip() for x in line.split("|")]
        if len(c) < 4 or c[1].startswith("---") or c[1] in ("класс", "class"):
            continue
        # «—» в колонке словаря значит «класс размечаем, но в слой не тянем»:
        # так из раздачи выведен сюжет, который договорились не трогать.
        if c[1] and c[2] and c[2].strip("`") not in ("—", "-"):
            out[c[1]] = c[2].strip("`")
    return out


def api_catalogue():
    """{название: класс} по официальному API и спискам-исходникам."""
    out = {}
    skip = {"charr_wiki.csv", "warband_roster.csv", "mechanical.csv",
            "skills.csv", "gw2skills.csv", "places.csv"}
    api_cls = {
        "maps": "places", "minis": "minis", "colors": "colors",
        "currencies": "currencies", "titles": "titles", "outfits": "outfits",
        "gliders": "gliders", "novelties": "novelties", "finishers": "finishers",
        "mailcarriers": "mailcarriers", "skiffs": "skiffs", "jadebots": "jadebots",
        "masteries": "masteries", "pets": "pets", "specializations": "skills",
        "professions": "skills", "achievement_categories": "achievements",
        "achievement_groups": "achievements", "wvw_objectives": "wvw",
        "wvw_abilities": "wvw", "wvw_ranks": "wvw", "pvp_ranks": "pvp",
        "pvp_heroes": "pvp", "quests": "quests", "guild_permissions": "guild",
    }
    for fp in sorted(glob.glob(os.path.join(CROWD, "sync", "api", "*.csv"))):
        if os.path.basename(fp) in skip:
            continue
        for r in D.read_csv(fp)[1:]:
            if len(r) >= 2 and r[0].strip():
                cls = api_cls.get(r[1].strip())
                if cls:
                    out.setdefault(key(r[0]), cls)
    ifp = os.path.join(CROWD, "sync", "api", "facts", "items.csv")
    if os.path.exists(ifp):
        for r in list(csv.reader(open(ifp, encoding="utf-8-sig")))[1:]:
            if r and r[0].strip():
                out.setdefault(key(r[0]), "items")
    pfp = os.path.join(CROWD, "sync", "api", "places.csv")
    if os.path.exists(pfp):
        for r in list(csv.reader(open(pfp, encoding="utf-8-sig")))[1:]:
            # kind=task — это не топоним, а формулировка сердца целым
            # предложением («Aid the Temple of Kormir.»). Их 398, и без отсева
            # они уезжали в pn_world_map как названия мест.
            if r and r[0].strip() and (len(r) < 2 or r[1].strip() != "task"):
                out.setdefault(key(r[0]), "places")
    return out


def connect():
    if not os.path.exists(DB):
        sys.exit("нет sync/index.db — сначала `index.py build`")
    return sqlite3.connect(DB)


# Строка целиком — название: с заглавной, до семи слов, без разметки и хвостовой
# точки. Годится только как ПОЛОВИНА улики: под неё подходят и счётчики событий
# («Gate Repair Progress»), а они не имена.
BARE = re.compile(r"^[A-Z][A-Za-z'’.\-]*(?: [A-Z\d][A-Za-z'’.\-]*){0,6}$")
WORD = re.compile(r"[A-Z][A-Za-z'’\-]{2,}")
# Разметка, которую слой отрисовать не может: он подставляет подстроку и не умеет
# ни трёх форм числа, ни рода, ни плейсхолдеров. Такие названия остаются жить в
# своей категории — там разметка работает.
MARKUP = re.compile(r"\[(?:s|pl:|f:)")
# Вторая половина улики: та же строка стоит целью в формулировке задачи.
VERB = re.compile(r"^(?:Defeat|Kill|Slay|Revive|Rescue|Escort|Talk to|Speak to"
                  r"|Destroy|Capture|Subdue|Free|Interact with)\s+(.+?)[.!]?$")
# Ранговый префикс носят и системные строки: «Elite Specializations», «Legendary
# Armory», «Legendary Starter Kits». Отсекаем по словам, которыми существо не
# зовётся никогда. Список короткий намеренно: спорное («Elite Guards»,
# «Legendary Defender») оставляем человеку, ложный отказ здесь дороже лишней
# строки в листе вычитки.
SYSTEM_WORDS = {
    "Specializations", "Specialization", "Skill", "Skills", "Leaderboard",
    "Armory", "Kits", "Kit", "Starter", "Mode", "Match", "Preview", "Voucher",
    "Package", "Components", "Component", "Tributes", "Tribute", "Gifts",
    "Gift", "Precursor", "Patrols", "Supplies", "Station", "Training",
    "Weapons", "Armor", "Available", "Defeated",
    # Хвосты счётчиков событий: «Mordrem Vinewrath Defeated», «Camp Tier 3».
    "Collected", "Complete", "Completed", "Destroyed", "Remaining", "Progress",
    "Captured", "Cleared", "Killed", "Tier", "Rescued", "Repaired",
}
# Граница предложения внутри строки: значит это реплика, а не табличка
# («Agent Gritt. Report.»).
SENTENCE = re.compile(r"[.!?]\s")
# Позиции, в которых стоит ЛИЧНОЕ имя: подпись письма и обращение в реплике.
SIGNATURE = re.compile(r"[—–]\s*([A-Z][A-Za-z'’\-]*(?: [A-Z][A-Za-z'’\-.]*){0,3})\s*$")
ADDRESS = re.compile(r"^([A-Z][a-z]+(?: [A-Z][a-z]+){0,2}), (?:I|you|we|it|the"
                     r"|that|this|he|she|they|let|come|listen|please|get|don't)")


def prose_hits(db, cand, isname):
    """Сколько раз каждое название встречается ВНУТРИ чужой фразы.

    Это и есть критерий членства в слое. Строка, которая сама целиком является
    названием, в слое не нужна: её гасит категория («Предметы: названия»), и
    вторая копия в `pn_*` только заставит игрока гасить два выключателя вместо
    одного. А вот то же название внутри описания достижения или формулировки
    события категорией не гасится ничем — там работает только слой.

    Контейнером считаем фразу: строку, которая сама не название и длиннее трёх
    слов. Иначе «Short Bow» насчитает 1 498 вхождений внутри других названий
    предметов («Soft Wood Short Bow») — это название внутри названия, не улика.
    """
    by = collections.defaultdict(list)
    for en in cand:
        w = WORD.findall(en)
        if w:
            by[w[0]].append(
                (en, re.compile(r"(?<![A-Za-z])" + re.escape(en) + r"(?![A-Za-z])")))
    hits = collections.Counter()
    for h, en in db.execute("SELECT hash, english FROM string WHERE english<>''"):
        if h in isname or len(en.split()) < 4:
            continue
        e = en.strip()
        for w in set(WORD.findall(en)):
            for c, rx in by.get(w, ()):
                if c != e and rx.search(en):
                    hits[c] += 1
    return hits


def npc_titles(db, min_names=8):
    """Титулы NPC, выведенные из самого слоя.

    Титул — первое слово, которое повторяется у МНОГИХ разных имён («Warmaster
    Forgal», «Warmaster Efut», …). Выдумывать список не надо: корпус уже знает,
    чем игра метит NPC и существ. Порог 8 разных имён отделяет титул от совпадения.

    Служебные и родовые слова, которые так же часто начинают НЕ имя, выкидываем
    поимённо: «The Story So Far», «First Aid», «Mark of Blood» иначе пройдут.
    """
    junk = {"The", "Mini", "First", "High", "Black", "Mark", "Lost", "Elder",
            "Master", "Lady", "Lord", "Queen", "Shadow", "Jade", "Iron", "Flame",
            "Old", "Great", "Small", "Broken", "Ancient", "Empty"}
    first = collections.defaultdict(set)
    for (en,) in db.execute("SELECT en FROM entity WHERE layer='pn_names'"):
        w = en.strip().split()
        if len(w) >= 2 and re.match(r"^[A-Z][a-z]+$", w[0]):
            first[w[0]].add(" ".join(w[1:]))
    return {t for t, r in first.items() if len(r) >= min_names} - junk


def discover(db, ent, known):
    """Монстры и NPC, которых нет ни в API, ни в слое.

    Эндпоинта по существам у игры нет, поэтому имя приходится доказывать по
    корпусу. Берём две улики и не смешиваем их с догадками:

    * **ранговый префикс** — `Champion` / `Veteran` / `Legendary` / `Elite` /
      `Ambient` в начале строки-таблички. Так игра метит существо, и ни один
      счётчик события так не называется;
    * **перекрёстная улика** — строка встречается И отдельной табличкой, И целью
      в формулировке задачи («Defeat Bloomhunger»). Счётчик «Ruins Scanned»
      второй половины не наберёт.

    Одиночные слова без ранга отбрасываем: под улику попадают «Armor», «Camp»,
    «Flag» — подписи интерфейса, а не имена.
    """
    allen = {r[0].strip() for r in db.execute(
        "SELECT DISTINCT english FROM string WHERE english<>''")}
    tgt = set()
    for en in allen:
        m = VERB.match(en)
        if m:
            t = m.group(1).strip()
            if not t.startswith(("the ", "a ", "an ", "your ", "all ")) \
                    and t not in ("me", "us"):
                tgt.add(t)
    bare = {e for e in allen
            if len(e) <= 60 and BARE.match(e) and not set("%<[") & set(e)}
    # Четвёртая улика — для ОДНОСЛОВНЫХ имён, которых три предыдущие не видят:
    # они все требуют двух слов. Имя признаётся, если оно стоит в подписи письма
    # («—Аnnika») или в обращении («Adelia, I need…») И ни разу не встречается в
    # корпусе со строчной буквы. Второе условие и отделяет имя от того мусора,
    # которым слой уже засорён: «boots», «champion», «keep» в нижнем регистре
    # попадаются сотнями, «Brannen» — ни разу.
    lower = collections.Counter()
    for s in allen:
        for x in re.findall(r"(?<![A-Za-z'])[a-z]{2,}(?![A-Za-z'])", s):
            lower[x] += 1
    common = {x for x, n in lower.items() if n >= 3}
    person = set()
    for s in allen:
        m = SIGNATURE.search(s)
        if m:
            person.add(m.group(1).strip())
        m = ADDRESS.match(s)
        if m:
            person.add(m.group(1).strip())
    person = {p for p in person
              if p and not any(x.lower() in common
                               for x in re.findall(r"[A-Za-z'’\-]+", p))}

    titles = npc_titles(db)
    out = {}
    for e in bare - ent - known:
        w = e.split()
        if SYSTEM_WORDS & set(w) or SENTENCE.search(e):
            continue
        if e in person and len(e) > 3:
            # Позиция доказывает личное имя независимо от числа слов: так
            # берутся и однословные («Brannen»), и составные («Baron Jon
            # Xander»), которых не знает ни один титул из слоя.
            out[e] = ("npc_side", "имя в подписи или обращении")
            continue
        if len(w) < 2:
            continue
        if RANK.match(e):
            out[e] = ("creatures", "ранговый префикс")
        elif e in tgt:
            out[e] = ("npc_side", "перекрёстная улика")
        elif w[0] in titles:
            # Третья улика, самая урожайная: строка начинается титулом, который
            # слой уже знает по десяткам других имён. Так нашлись 3 598 табличек
            # NPC, лежавших в «основном» — там выключателя нет вовсе, и вернуть
            # их к английскому было нечем.
            out[e] = ("npc_side", "титул из слоя")
    return out


def cmd_scan(_a):
    db = connect()
    db.executescript("""
        DROP TABLE IF EXISTS name;
        DROP TABLE IF EXISTS route;
        CREATE TABLE name(hash TEXT, en TEXT, cls TEXT, src TEXT, layer TEXT,
                          file TEXT, cur_cat TEXT, state TEXT, prose INT);
        CREATE INDEX i_name_cls ON name(cls);
        CREATE INDEX i_name_state ON name(state);
        CREATE TABLE route(hash TEXT, en TEXT, file TEXT, why TEXT);
        CREATE INDEX i_route_file ON route(file);
    """)
    nmap = load_namemap()
    if not nmap:
        print("! NAMEMAP.md не найден — словарь-получатель не проставлен")
    cat_api = api_catalogue()
    print("названий в API-кэше: %d" % len(cat_api))

    # где строка лежит сейчас: категория bin и файл батча
    cur_cat = {}
    for h, ref in db.execute("SELECT hash, ref FROM place WHERE kind='категория'"):
        if not ref.startswith("pn_"):
            cur_cat.setdefault(h, ref)

    ent = {}
    for en, lay in db.execute("SELECT en, layer FROM entity"):
        ent[en.strip()] = lay

    # где имя упоминается: сюжет или второстепенный контент
    where = collections.defaultdict(set)
    for en, ref in db.execute("""SELECT m.en, p.ref FROM mention m
                                 JOIN place p ON p.hash=m.hash AND p.kind='категория'"""):
        where[en].add(ref)

    rows = []
    for h, en in db.execute("SELECT hash, english FROM string WHERE english<>''"):
        cls = src = None
        c = cur_cat.get(h)
        if c and c.endswith("_descriptions"):
            # Описание остаётся описанием, даже если API знает предмет с таким
            # же текстом: «чужой класс не указ» — правило разведения категорий
            # 2026-08-11. Без этого «A Fungus Among Us: Gold» из
            # achievement_descriptions уезжало в слой предметов.
            continue
        if c in NAME_CATS:
            cls, src = NAME_CATS[c], "cat:" + c
        else:
            k = cat_api.get(key(en))
            if k:
                cls, src = k, "api"
            elif en.strip() in ent:
                lay = ent[en.strip()]
                w = where.get(en.strip(), set())
                if RANK.match(en.strip()):
                    cls = "creatures"
                elif lay == "pn_world_map":
                    cls = "places"
                elif lay == "pn_terms":
                    cls = "terms"
                elif w & SIDE_CATS and not (w & STORY_CATS):
                    cls = "npc_side"
                elif w & STORY_CATS:
                    cls = "npc_story"
                else:
                    cls = "npc_side"
                src = "layer:" + lay
        if not cls:
            continue
        state = "в слое" if en.strip() in ent else "нет в слое"
        rows.append((h, en, cls, src, nmap.get(cls, ""), "", c or "", state))

    # Существа и NPC: API их не отдаёт, доказываем по корпусу (см. discover).
    known = {r[1].strip() for r in rows}
    found = discover(db, set(ent), known)
    for h, en in db.execute("SELECT hash, english FROM string WHERE english<>''"):
        f = found.get(en.strip())
        if f:
            rows.append((h, en, f[0], f[1], nmap.get(f[0], ""), "",
                         cur_cat.get(h, ""), "нет в слое"))
    print("найдено по корпусу (существа и NPC вне API): %d" % len(found))

    # Кому из дыры место в слое: только тем, кто встречается внутри чужих фраз
    # и кого слой способен отрисовать (без групп форм и плейсхолдеров).
    isname = {r[0] for r in rows}
    # Граница длины из README («Словари названий»): название — короткая строка.
    # Без неё в слой попадают описания, которые лежат в категории названий по
    # ошибке: «Acquired as a rare drop from the Guardian's Glade raid encounter…»
    # числится в `item_names`, класс берётся от категории — и описание уезжает
    # в слой. Число слов границей не годится: «Legendary Voice of the Fallen and
    # Claw of the Fallen» — настоящее название достижения из девяти слов.
    cand = {r[1].strip() for r in rows
            if r[7] == "нет в слое" and r[4]
            and not MARKUP.search(r[1]) and "%" not in r[1] and "<" not in r[1]
            and len(r[1].split()) >= 2 and 8 <= len(r[1]) <= 60}
    hits = prose_hits(db, cand, isname)
    rows = [r + (hits.get(r[1].strip(), 0),) for r in rows]
    db.executemany("INSERT INTO name VALUES (?,?,?,?,?,?,?,?,?)", rows)
    print("названий в реестре: %d | встречаются внутри фраз: %d"
          % (len(rows), sum(1 for r in rows if r[8])))

    # Целевой файл батча. Дыры режем по 500 строк, как нарезан pn/ сейчас,
    # и нумеруем ПОСЛЕ последнего существующего файла слоя — чтобы заготовки
    # не наезжали на то, что люди уже вычитали.
    last = collections.Counter()
    for fp in glob.glob(os.path.join(CROWD, "pn", "*.csv")):
        lay = D.pn_layer_of(fp)
        if lay:
            n = int(re.search(r"_(\d+)\.csv$", fp).group(1))
            last[lay] = max(last[lay], n)
    # В слой идут ВСЕ названия (решение мейнтейнера 2026-09-01). Прежнее правило
    # брало только те, что встречаются внутри чужих фраз или лежат вне именной
    # категории: довод был «строку-название гасит своя категория, копия в слое
    # заставит игрока щёлкать два выключателя». Довод остаётся верным, но выбор
    # сделан в пользу полноты слоя — чтобы любое название было видно и
    # переключалось в одном месте.
    #
    # Сюжетные классы по-прежнему вне раздачи, но не здесь: у них в NAMEMAP.md
    # стоит прочерк, и `lay` для них пуст.
    gaps = collections.defaultdict(list)
    for h, en, cls, src, lay, _f, c, state, prose in rows:
        if state != "нет в слое" or not lay:
            continue
        if MARKUP.search(en) or "%" in en or "<" in en:
            continue
        # Одно слово принимаем, когда названием его назвал ИСТОЧНИК — API или
        # категория словаря («Orr», «Hoelbrak», «Tyria»). Улики по корпусу
        # требуют двух слов: там одиночное слово почти всегда мусор вроде
        # «Boots», которым слой и засорён. Исключение — подпись и обращение:
        # позиция сама доказывает личное имя.
        strong = src == "api" or src.startswith("cat:") \
            or src == "имя в подписи или обращении"
        least = 1 if strong else 2
        if len(en.split()) < least or not 3 <= len(en) <= 60:
            continue
        gaps[lay].append((h, en))
    route = []
    for lay, items in gaps.items():
        items.sort(key=lambda x: x[1])
        for i, (h, en) in enumerate(items):
            fn = "pn/%s_%03d.csv" % (lay, last[lay] + 1 + i // PER_FILE)
            route.append((h, en, fn, "дыра в слое"))
    db.executemany("INSERT INTO route VALUES (?,?,?,?)", route)
    db.commit()
    print("строк с назначенным файлом: %d" % len(route))
    cnt = collections.Counter((r[2], r[7]) for r in rows)
    print("\n%-14s %8s %8s" % ("класс", "в слое", "нет"))
    for cls in sorted({r[2] for r in rows}):
        print("%-14s %8d %8d" % (cls, cnt[(cls, "в слое")], cnt[(cls, "нет в слое")]))


def cmd_gap(a):
    db = connect()
    q = "SELECT cls, layer, count(*) FROM name WHERE state='нет в слое'"
    p = ()
    if a:
        q += " AND cls=?"
        p = (a[0],)
    q += " GROUP BY cls, layer ORDER BY 3 DESC"
    print("%-14s %-16s %8s" % ("класс", "словарь", "дыра"))
    for cls, lay, n in db.execute(q, p):
        print("%-14s %-16s %8d" % (cls, lay or "— не задан —", n))
    if a:
        print("\nпримеры:")
        for en, c in db.execute("SELECT en, cur_cat FROM name WHERE state='нет в слое' "
                                "AND cls=? LIMIT 15", (a[0],)):
            print("   %-52s %s" % (en[:52], c))


def cmd_inline(_a):
    """Строки, где имя из слоя переведено прямо в тексте, а не оставлено латиницей.

    Такое имя выключателем не вернуть: игрок гасит `pn_*`, а в строке уже стоит
    кириллица. Одиночные слова не считаем — в слое их полно по ошибке («Boots»,
    «Champion»), и обычное слово в русской фразе не дефект.
    """
    db = connect()
    isname = {r[0] for r in db.execute("SELECT hash FROM name")}
    per = collections.Counter()
    kept = collections.Counter()
    bad = collections.Counter()
    for h, en, ru, ref, ename in db.execute("""
            SELECT s.hash, s.english, s.ru, p.ref, m.en FROM mention m
            JOIN string s ON s.hash=m.hash
            JOIN place p ON p.hash=m.hash AND p.kind='категория'
            JOIN entity e ON e.en=m.en
            WHERE s.ru<>'' AND s.english<>''"""):
        # Одиночное слово не улика: в слое полно обычных слов («Boots»,
        # «Champion», «Legendary»), и кириллица на их месте — нормальный перевод.
        # Сам слой из отчёта убираем: там записи ловят друг друга.
        if len(ename.split()) < 2 or ref.startswith("pn_"):
            continue
        # Контейнер, который сам является названием, — не дефект: он гасится
        # своей категорией целиком вместе с вложенным именем. Дефект только во
        # фразе, где категория до вложенного названия не достаёт.
        if h in isname or len(en.split()) < 4:
            continue
        per[ref] += 1
        if ename in ru:
            kept[ref] += 1
        else:
            bad[ename] += 1
    print("%-24s %8s %8s %8s" % ("категория", "пар", "латиница", "переведено"))
    for ref, n in per.most_common(20):
        print("%-24s %8d %8d %8d" % (ref, n, kept[ref], n - kept[ref]))
    print("\nуникальных имён, переведённых внутри строк: %d" % len(bad))
    for en, n in bad.most_common(20):
        print("   %-46s %d" % (en[:46], n))


def cmd_emit(a):
    """Строки слоя по дырам в файлы, назначенные scan.

    Без `--write` пишет заготовки в `sync/reports/names_emit` — посмотреть, что
    получится. С `--write` кладёт их прямо в `pn/`, откуда `frombatches` заводит
    слой в bin. Существующие файлы `pn/` не трогает никогда: scan нумерует новые
    ПОСЛЕ последнего занятого номера.
    """
    write = "--write" in a
    cls = [x for x in a if not x.startswith("--")]
    db = connect()
    q = ("SELECT r.file, r.en, s.ru, n.prose FROM route r "
         "JOIN string s ON s.hash=r.hash JOIN name n ON n.hash=r.hash")
    p = ()
    if cls:
        q += " WHERE n.cls=?"
        p = (cls[0],)
    byf = collections.defaultdict(list)
    for fn, en, ru, prose in db.execute(q, p):
        byf[fn].append((prose, en, ru))
    out = os.path.join(CROWD, "pn") if write \
        else os.path.join(CROWD, "sync", "reports", "names_emit")
    os.makedirs(out, exist_ok=True)
    for fn, rows in byf.items():
        dst = os.path.join(out, os.path.basename(fn))
        if write and os.path.exists(dst):
            sys.exit("файл уже есть, перезаписывать не буду: %s" % dst)
        # Сначала то, что чаще встречается во фразах: вычитывать с головы списка
        # выгоднее — одна запись закрывает десятки вхождений сразу.
        rows.sort(key=lambda r: (-r[0], r[1]))
        with open(dst, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(["english", "translate"])
            w.writerows((en, ru) for _n, en, ru in rows)
    print("файлов: %d | строк: %d" % (len(byf), sum(len(v) for v in byf.values())))
    print("-> %s" % os.path.relpath(out, CROWD))
    if not write:
        print("это ЗАГОТОВКИ; записать в pn/ — тот же вызов с --write")


CMDS = {"scan": cmd_scan, "gap": cmd_gap, "inline": cmd_inline, "emit": cmd_emit}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in CMDS:
        sys.exit(__doc__)
    CMDS[sys.argv[1]](sys.argv[2:])
