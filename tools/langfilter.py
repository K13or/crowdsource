#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Не-английские строки в батчах: найти, выписать, удалить.

    python tools/langfilter.py check [new/new_125.csv ...]   # список, без правок
    python tools/langfilter.py apply [new/new_125.csv ...]   # удалить уверенные
    python tools/langfilter.py apply --all [...]             # и «под вопросом» тоже
    python tools/langfilter.py markers                       # пересобрать словарь снятого

Зачем. Синк тянет строки с прокси, а прокси видел не только английский клиент:
в колонку `english` попадают французские (реже немецкие и испанские) строки.
Переводить их нельзя — в игре по этому хешу лежит французский оригинал, и наш
русский текст встал бы поверх французского клиента.

Признак не один, иначе ловится мусор: у «Place the Café Register decoration»
диакритика есть, а строка английская. Считаем ТРИ сигнала — служебные слова
языка, диакритику и характерные хвосты команд — и сравниваем с английскими
служебными словами. Отчёт всегда пишется целиком, удаляются только уверенные.
"""
import csv, glob, io, json, os, re, subprocess, sys, collections

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
CROWD = os.path.dirname(HERE)
REPORT = os.path.join(CROWD, "sync", "reports", "non_english.csv")
REPORT_APPLIED = os.path.join(CROWD, "sync", "reports", "non_english_deleted.csv")
# Слова, снятые прошлыми чистками: собираются командой `markers`, лежат рядом.
MARKERS = os.path.join(HERE, "lang_markers.json")

# Слова языка делятся надвое, иначе английское уходит в удаление.
# STRONG — французские и только французские. WEAK — те, что есть и в английском:
# «la» из напева «La-la-la», «suit» из «Dredge Diving Suit», «dire» из «Vicious
# Dire Boar», «possession», «son», «plus», «par», «note». Улика — только STRONG;
# WEAK лишь усиливает подозрение, но сам по себе ничего не доказывает.
FR = re.compile(r"\b(le|les|des|une|du|de|au|aux|vous|nous|pour|avec|dans|est|sont|été|"
                r"pièces?|secondes?|disponibles?|contre|semaine|terminer|"
                r"retour|jour|jeu|votre|tous|toutes|guilde|élite|manche|"
                r"marchandises?|actif|interne|suivant|exclusif|restants?|instable|"
                r"envahisseur|requis|acheter|épisode|succès|déverrouiller|gauche|droite|"
                r"salue|rit|pleure|prie|ramasse|remercie|menace|acclame|boude|creuse|"
                r"drague|fanfaronne|sifflote|titube|tombe|parle|joue|perd|chantons|"
                r"ici|ça|cette|cet|qui|que|quoi|mais|très|bien|ses|notre|leur|elle|ils|"
                r"elles|être|avoir|faire|aller|maintenant|beaucoup|obtention|objet|zone)\b", re.I)
FR_WEAK = re.compile(r"\b(la|plus|son|par|dire|non|sur|ma|mon|mes|suit|possession|place|"
                     r"note|coup|second)\b", re.I)
DE = re.compile(r"\b(der|die|das|und|nicht|sie|ihr|ein|eine|mit|für|auf|ist|sind|von|wird|"
                r"woche|zurück|gegen|beenden|spiel|kaufen|erforderlich|folge|freischalten)\b", re.I)
ES = re.compile(r"\b(los|las|una|para|con|por|que|más|está|son|semana|volver|contra|juego|"
                r"comprar|requiere|episodio|desbloquear)\b", re.I)
EN = re.compile(r"\b(the|and|you|your|for|with|that|this|are|was|have|will|from|not|but|all|"
                r"his|her|they|there|what|when|who|how|of|to|in|on|is|it|be|as|at|by|we|die|"
                r"defeated|used|given|eaten|crafted|collected|visited|completed|unlocked)\b", re.I)
DIA_FR = re.compile(r"[éèêëàâçùûîïôœÉÈÊÀÂÇÙÎÔŒ]")
DIA_DE = re.compile(r"[äöüßÄÖÜ]")
DIA_ES = re.compile(r"[áíóúñ¿¡]")
# Неразрывный пробел перед «!», «?», «:», «;» — французская типографика: клиент
# отдаёт U+00A0 там, где в английском не бывает пробела вовсе. Признак сильный,
# он один вытащил 942 строки, которых не видели списки слов, — в том числе 411 в
# одном new_172, где текст сплошь из имён и цифр.
NBSP_FR = re.compile("\u00a0\\s*[!?:;\u00bb]|\u00ab\\s*\u00a0")

# французские хвосты команд и звуков, где служебных слов нет вовсе
FR_TAIL = re.compile(r"^/(?:boire|carte|ciseaux|danseducrabe|dire|escouade|feuille|groupe|"
                     r"pierre|poucebas|poucehaut|siffler|tremblefort|chuchoter|biceps|"
                     r"héroïque|possédé)\b|^\((?:grogne|gazouillement|jacassement|gribouillis|"
                     r"aboiement|rire|soupir)\)|^\"?(?:Wouf|Miaou|MIAOU)\b", re.I)


# Названия дополнений и игр остаются английскими в любой локализации, поэтому
# из подсчёта английских слов их надо вынуть: иначе «La Corne de Maguuma est
# accessible avec l'extension "Secrets of the Obscure"» набирает два «английских»
# слова из кавычек и перестаёт считаться французской.
QUOTED = re.compile(r"[\"«][^\"»]{3,60}[\"»]")
PRODUCT = re.compile(r"Guild Wars 2|Secrets of the Obscure|Heart of Thorns|Path of Fire|"
                     r"End of Dragons|Janthir Wilds|Visions of Eternity|Living World", re.I)


# Списки слов молчат на коротких названиях: «Revanche», «Rifle rapide», «Sol nu»
# служебных слов не содержат, диакритики тоже. Поэтому есть два словаря.
#
# EN собирается из строк корпуса, У КОТОРЫХ ЕСТЬ ПЕРЕВОД. Ход не случайный:
# французские хвосты синка лежат непереведёнными, значит в такой словарь они не
# попадут, и язык не выучится на том же мусоре, который ищем.
#
# MARKERS — слова из строк, снятых прошлыми чистками (команда `markers` собирает
# их из git-истории). Слово оттуда, которого английский корпус почти не знает,
# перевешивает соседей-когнатов: «revolver» и «rifle» есть в обоих языках, а
# «assaillant» и «rapide» — только во французском.
WORD = re.compile(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ']{2,}")
_LEX = {}


def lexicons():
    if _LEX:
        return _LEX
    en = collections.Counter()
    for fp in sorted(glob.glob(os.path.join(CROWD, "*", "*.csv"))):
        if os.path.basename(os.path.dirname(fp)) in ("sync", "tools", ".batch_bak"):
            continue
        try:
            rows = list(csv.reader(io.open(fp, encoding="utf-8-sig", newline="")))
        except OSError:
            continue
        for i, r in enumerate(rows):
            if i and len(r) > 1 and r[1].strip():
                for w in WORD.findall(r[0]):
                    en[w.lower()] += 1
    try:
        marks = set(json.load(io.open(MARKERS, encoding="utf-8")))
    except (OSError, ValueError):
        marks = set()
    _LEX.update(en=en, marks=marks)
    return _LEX


def foreign_words(e):
    """Слова строки, которые знает только снятый корпус."""
    lex = lexicons()
    return [w for w in WORD.findall(e)
            if w.lower() in lex["marks"] and lex["en"].get(w.lower(), 0) <= 1]


def unknown_to_english(e):
    """Ни одно слово строки английскому корпусу не знакомо."""
    lex = lexicons()
    words = WORD.findall(e)
    return bool(words) and not any(lex["en"].get(w.lower(), 0) >= 5 for w in words)


def verdict(en_text, ru_text=""):
    """('fr'|'de'|'es'|'', уверенность, почему).

    Перевод нужен не для проверки языка, а как отсечка для самого слабого
    признака: у строки, которую человек уже перевёл, повода подозревать чужой
    язык нет, и незнакомые корпусу слова там — это имена и звуки («Abbik»,
    «(huffs)»), а не французский.
    """
    e = en_text
    bare = PRODUCT.sub(" ", QUOTED.sub(" ", e))
    n_en = len(EN.findall(bare))
    scores = {"fr": len(FR.findall(e)), "de": len(DE.findall(e)), "es": len(ES.findall(e))}
    lang = max(scores, key=scores.get)
    n = scores[lang]
    if FR_TAIL.search(e):
        return "fr", "уверенно", "команда или звук французского клиента"
    if NBSP_FR.search(e):
        return "fr", "уверенно", "неразрывный пробел перед знаком — французская типографика"
    # Улика из словаря снятого корпуса. Порог — ДВА слова: одного мало, на нём
    # правило цепляло английские названия («Abandon ship without a chute!»,
    # «Amduat Sceptre» — «chute» и «sceptre» частотны у снятых и почти не
    # встречаются у английских). Проверено по всему корпусу: при двух словах на
    # 477 374 переведённых строк срабатываний-ошибок нет ни одного, а найденные
    # семь оказались немецкими и испанскими строками, которые кто-то перевёл
    # транслитом («Alte Frau» -> «Альте Фрау») вместо того, чтобы снять.
    fw = foreign_words(e)
    if len(fw) >= 2 and n_en == 0:
        return lang, "уверенно", "слова только из снятого корпуса: %s" % ", ".join(fw[:3])
    if fw:
        return lang, "под вопросом", ("слова из снятого корпуса: %s" % ", ".join(fw[:3]))
    if n >= 2 and n > n_en:
        return lang, "уверенно", "служебных слов языка %d против английских %d" % (n, n_en)
    dia = ("fr" if DIA_FR.search(e) else "de" if DIA_DE.search(e) else
           "es" if DIA_ES.search(e) else "")
    if dia and n_en == 0 and n >= 1:
        return dia, "уверенно", "диакритика и служебное слово, английских слов нет"
    # одной диакритики мало: «Place the Café Register decoration» — английская
    # строка. Нужно, чтобы слов со знаками было несколько.
    acc = len(re.findall(r"[A-Za-zÀ-ÿ]*[éèêëàâçùûîïôœäöüßáíóúñ][A-Za-zÀ-ÿ]*", e))
    if dia and n_en == 0 and acc >= 2:
        return dia, "под вопросом", "несколько слов с диакритикой, английских слов нет"
    if n == 1 and n_en == 0 and dia and len(e.split()) <= 6:
        return lang, "под вопросом", "служебное слово языка и диакритика"
    # Короткие фразы вроде «La plus rapide» держатся на двусмысленных словах.
    # Признать их языком автоматически нельзя, но и молчать не стоит — в список,
    # и только если рядом есть хоть одно надёжное слово языка.
    weak = len(FR_WEAK.findall(e))
    if n >= 1 and weak >= 1 and n_en == 0 and len(e.split()) >= 2:
        return lang, "под вопросом", "надёжное слово языка %d + двусмысленных %d" % (n, weak)
    # Последний, самый слабый признак: корпус не знает ни одного слова строки.
    # Так выглядит и чужой язык, и редкое английское название вроде «Rimebreath»,
    # поэтому только «под вопросом» — apply такие не трогает. И только для
    # непереведённых строк: у переведённых это имена и звуки, а не язык.
    if not ru_text.strip() and n_en == 0 and unknown_to_english(e):
        return lang, "под вопросом", "английскому корпусу не знакомо ни одно слово"
    return "", "", ""


def scan(paths):
    out = []
    for fp in paths:
        rows = list(csv.reader(io.open(fp, encoding="utf-8")))
        for i, r in enumerate(rows[1:], start=2):
            if not r or not r[0].strip():
                continue
            lang, conf, why = verdict(r[0], r[1] if len(r) > 1 else "")
            if lang:
                out.append((os.path.basename(fp), i, lang, conf, why, r[0]))
    return out


def batch_paths(args):
    if args:
        return [a if os.path.exists(a) else os.path.join(CROWD, a) for a in args]
    return sorted(glob.glob(os.path.join(CROWD, "new", "new_*.csv")))


def write_report(found, path=None):
    path = path or REPORT
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with io.open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["файл", "строка", "язык", "уверенность", "признак", "english"])
        w.writerows(found)
    return path


def cmd_check(args):
    found = scan(batch_paths(args))
    per_lang = collections.Counter(x[2] for x in found)
    per_conf = collections.Counter(x[3] for x in found)
    per_file = collections.Counter(x[0] for x in found)
    print("найдено не-английских строк: %d" % len(found))
    print("по языкам:", dict(per_lang), "| по уверенности:", dict(per_conf))
    print("\nбольше всего в файлах:")
    for fn, n in per_file.most_common(10):
        print("   %-16s %d" % (fn, n))
    print("\nпримеры «под вопросом» (их apply НЕ трогает):")
    for x in [y for y in found if y[3] == "под вопросом"][:10]:
        print("   %-14s %s" % (x[0], x[5][:74].replace("\n", " ")))
    print("\n-> %s" % os.path.relpath(write_report(found), CROWD))


def cmd_apply(args):
    # --all добавляет «под вопросом»: их стоит удалять только после того, как
    # список прочитан глазами, поэтому по умолчанию они остаются в батчах
    take_all = "--all" in args
    args = [a for a in args if a != "--all"]
    paths = batch_paths(args)
    found = scan(paths)
    write_report(found, REPORT_APPLIED)
    kill = collections.defaultdict(set)
    for fn, line, lang, conf, why, en in found:
        if conf == "уверенно" or take_all:
            kill[fn].add(en)
    total = 0
    for fp in paths:
        fn = os.path.basename(fp)
        if fn not in kill:
            continue
        rows = list(csv.reader(io.open(fp, encoding="utf-8")))
        head, body = rows[0], rows[1:]
        keep = [r for r in body if not (r and r[0] in kill[fn])]
        n = len(body) - len(keep)
        if not n:
            continue
        with io.open(fp, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(head)
            w.writerows(keep)
        print("   %-16s удалено %3d, осталось %3d" % (fn, n, len(keep)))
        total += n
    print("удалено строк: %d | список удалённого: %s"
          % (total, os.path.relpath(REPORT_APPLIED, CROWD)))
    print("не забудь пересчитать доску: python stats.py --mark-done")


def cmd_markers(args):
    """Пересобрать tools/lang_markers.json из истории репозитория.

    Каждая прошлая чистка подписана «снято N французских», и снятые строки лежат
    в git. Брать все строки со знаком «минус» нельзя: в тех же коммитах правились
    переводы, а правка выглядит как «-строка/+строка». Настоящее удаление — это
    english-ключ, который в коммите исчез и обратно не появился.
    """
    def git(*a):
        r = subprocess.run(["git"] + list(a), cwd=CROWD, capture_output=True)
        return r.stdout.decode("utf-8", "replace")

    def key(line):
        try:
            return next(csv.reader([line]))[0]
        except Exception:
            return line.split(",", 1)[0].strip('"')

    shas = []
    for pat in ("французск", "не-английск"):
        shas += [s for s in git("log", "--all", "--format=%H", "--grep=" + pat, "-i").split() if s]
    shas = list(dict.fromkeys(shas))
    dirs = [d for d in sorted(os.listdir(CROWD))
            if os.path.isdir(os.path.join(CROWD, d)) and not d.startswith(".")
            and d not in ("sync", "tools", "skills", "__pycache__")]
    removed = []
    for sha in shas:
        diff = git("show", "--format=", "--unified=0", sha, "--", *dirs)
        minus, plus = [], set()
        for ln in diff.splitlines():
            if ln.startswith("---") or ln.startswith("+++"):
                continue
            if ln.startswith("-"):
                minus.append(key(ln[1:]))
            elif ln.startswith("+"):
                plus.add(key(ln[1:]))
        removed += [k for k in minus if k and k not in plus and len(k) > 2]
    removed = set(removed)
    print("коммитов с чисткой: %d | снятых записей: %d" % (len(shas), len(removed)))

    freq = collections.Counter()
    for e in removed:
        for w in WORD.findall(e):
            freq[w.lower()] += 1
    en = lexicons()["en"]
    # порог 5 против 1: слово должно быть частым у снятых и почти отсутствовать
    # у английских, иначе в список попадут когнаты вроде «rifle» и «revolver»
    marks = sorted(w for w, c in freq.items() if c >= 5 and en.get(w, 0) <= 1)
    with io.open(MARKERS, "w", encoding="utf-8") as f:
        json.dump(marks, f, ensure_ascii=False, indent=0)
    print("слов в словаре: %d -> %s" % (len(marks), os.path.relpath(MARKERS, CROWD)))


CMDS = {"check": cmd_check, "apply": cmd_apply, "markers": cmd_markers}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in CMDS:
        sys.exit(__doc__)
    CMDS[sys.argv[1]](sys.argv[2:])
