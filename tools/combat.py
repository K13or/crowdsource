#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Канон боевых терминов — только в механическом тексте.

    python tools/combat.py check     # что и где заменится
    python tools/combat.py apply     # применить к bin (бэкап + гейт линтера)
    python tools/combat.py batches   # то же по батчам (источник истины)

    --cats skill_descriptions,traits   только эти категории словаря
    --all                              check: показать все правки, а не 12

Почему отдельный инструмент, а не правило в `dict_tool.canon`: канон боевых
терминов действует НЕ везде. «The foolish vigor of youth» — обычное слово, там
«энергия юности» вернее «энергичности», а «Chilled to the Bone!» — название
умения с идиомой. Канон обязателен только в описаниях умений и талантов, а
границу знает граф (`index.py build` -> таблица `ctx`, вид «механика»).

Заменяем существительное на существительное. Глагольные формы не трогаем: у
`Launch` в описаниях стоит «запустите» про снаряд, у `Immobilize` —
«обездвижьте», у `Burning` — «поджигая», и всё это законно.

Эталон канона — https://ru.gw2skills.net/wiki (сверено 2026-08-11, совпадает с
GLOSSARY.md дословно).
"""
import os, re, sqlite3, sys, collections

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
CROWD = os.path.dirname(HERE)
DB = os.path.join(CROWD, "sync", "index.db")
sys.path.insert(0, HERE)
sys.path.insert(0, CROWD)
import dict_tool as D
try:
    import validate as _validate
except Exception:
    _validate = None

# термин -> ((неверная форма, канон в том же падеже), ...)
# Ключ — регулярное выражение по английскому: «Chill» в описании стоит и как
# «chill», и как «chilled», «chilling»; «Immobilize» — как «immobilized».
# Порядок важен: длинные окончания первыми, иначе «могущества» съест «могущество».
FIX = {
    "Might": (("могуществом", "Мощью"), ("могущества", "Мощи"),
              ("могуществу", "Мощи"), ("могуществе", "Мощи"),
              ("могущество", "Мощь")),
    "Protection": (("защитой", "Протекцией"), ("защиты", "Протекции"),
                   ("защите", "Протекции"), ("защиту", "Протекцию"),
                   ("защита", "Протекция")),
    "Stability": (("стабильностью", "Устойчивостью"),
                  ("стабильности", "Устойчивости"),
                  ("стабильность", "Устойчивость"),
                  # опечатка самого канона
                  ("устройчивостью", "Устойчивостью"),
                  ("устройчивости", "Устойчивости"),
                  ("устройчивость", "Устойчивость")),
    "Swiftness": (("стремительностью", "Быстротой"),
                  # в описаниях это родительный: «под действием стремительности»
                  ("стремительности", "Быстроты")),
    "Resistance": (("сопротивлением", "Сопротивляемостью"),
                   ("сопротивления", "Сопротивляемости"),
                   ("сопротивлению", "Сопротивляемости"),
                   ("сопротивление", "Сопротивляемость")),
    "Torment": (("мучениями", "Болью"), ("мучением", "Болью"),
                ("мучений", "Боли"), ("мучения", "Боли"),
                ("мучению", "Боли"), ("мучение", "Боль")),
    "Quickness": (("быстротой", "Проворством"), ("быстроты", "Проворства"),
                  ("быстроте", "Проворстве"), ("быстроту", "Проворство"),
                  ("быстрота", "Проворство")),
    # «сбивание с ног» — это всё название целиком, и менять надо его целиком,
    # иначе выходит «нокдаун с ног». Между словом и «с ног» бывает вставка
    # («сбивания ЦЕЛИ с ног»), поэтому допускаем до двух слов и возвращаем их.
    "Knockdown": ((r"сбиванием((?:\s+\w+){0,2})\s+с\s+ног", r"Нокдауном\1"),
                  (r"сбивания((?:\s+\w+){0,2})\s+с\s+ног", r"Нокдауна\1"),
                  (r"сбиванию((?:\s+\w+){0,2})\s+с\s+ног", r"Нокдауну\1"),
                  (r"сбивание((?:\s+\w+){0,2})\s+с\s+ног", r"Нокдаун\1"),
                  ("сбиванием", "Нокдауном"), ("сбивания", "Нокдауна"),
                  ("сбиванию", "Нокдауну"), ("сбивание", "Нокдаун")),
    "Cripple": (("увечьем", "Хромотой"), ("увечья", "Хромоты"),
                ("увечью", "Хромоте")),
    "Chill(?:ed|ing|s)?": (("охлаждением", "Заморозкой"), ("охлаждения", "Заморозки"),
                           ("охлаждению", "Заморозке"),
                           ("холодом", "Заморозкой"), ("холода", "Заморозки"),
                           ("холоду", "Заморозке")),
    "Blindness": (("ослеплением", "Слепотой"), ("ослепления", "Слепоты"),
                  ("ослеплению", "Слепоте")),
    "Vigor": (("бодростью", "Энергичностью"), ("бодрости", "Энергичности"),
              ("бодрость", "Энергичность")),
    "Regeneration": (("восстановлением", "Регенерацией"),
                     ("восстановления", "Регенерации")),
    # 2026-09-28: синонимы, найденные замером описаний умений и талантов.
    # Род у пары совпадает, и падеж сохраняется слово в слово.
    "Superspeed": (("суперскоростью", "Сверхскоростью"),
                   ("суперскорости", "Сверхскорости"),
                   ("суперскорость", "Сверхскорость")),
    "Expertise": (("сноровкой", "Экспертизой"), ("сноровки", "Экспертизы"),
                  ("сноровке", "Экспертизе"), ("сноровку", "Экспертизу"),
                  ("сноровка", "Экспертиза")),
    "Resolution": (("резолюцией", "Решимостью"), ("резолюции", "Решимости"),
                   ("резолюцию", "Решимость"), ("резолюция", "Решимость")),
    "Ferocity": (("жестокостью", "Свирепостью"), ("жестокости", "Свирепости"),
                 ("жестокость", "Свирепость")),
    "Toughness": (("прочностью", "Стойкостью"), ("прочности", "Стойкости"),
                  ("прочность", "Стойкость")),
    # «замедление» и «обездвиживание» — существительные; им. и вин. падежи
    # совпадают и у исходника, и у канона, так что выбирать падеж не нужно.
    # Глагольные формы («замедляет», «обездвиживает») не трогаем — см. выше.
    "Slow(?:ed|s|ing)?": (("замедлением", "Медлительностью"),
                          ("замедления", "Медлительности"),
                          ("замедлению", "Медлительности"),
                          ("замедлении", "Медлительности"),
                          ("замедление", "Медлительность")),
    "Immobiliz(?:e|ed|es|ing)": (("обездвиживанием", "Неподвижностью"),
                                 ("обездвиживания", "Неподвижности"),
                                 ("обездвиживанию", "Неподвижности"),
                                 ("обездвиживании", "Неподвижности"),
                                 ("обездвиживание", "Неподвижность")),
}
# Термин не правится вовсе, если в той же строке стоит соседний термин, для
# которого исходное слово — законный канон. «Дарует проворство и быстроту» при
# `quickness, swiftness`: «быстрота» — канон Swiftness, и замена по Quickness
# давала «проворство, проворство».
SKIP_IF = {
    "Quickness": r"swiftness",
}
# Вхождение не правится, если рядом стоит то, что делает слово другим понятием:
# «сопротивление агонии» — канон атрибута Agony Resistance; «время
# восстановления», «восстановление здоровья» — не Регенерация.
GUARD = {
    "Resistance": (None, r"^\s+агонии"),
    "Regeneration": (r"(?:врем(?:я|ени|енем)|скорост\w+)\s+$",
                     r"^\s+(?:здоровья|выносливост\w+|энерги\w+|жизнен\w+|сил\w*|инициатив\w+|адреналин\w*)"),
}
# «обездвиживание», «замедление», «холод» бывают ДЕЙСТВИЕМ, а не состоянием:
# «Ослепление, обездвиживание или применение контроля» = «Blinding,
# immobilizing, or affecting a foe…», «при обездвиживании противника» = «when
# you immobilize a foe». Там канон «Неподвижность» неверен. Признак состояния —
# слово перед ним в той же фразе: эффект, длительность, снять, лечит,
# накладывает, заряд. Без такого признака не трогаем.
COND_MARK = re.compile(r"(?<![А-Яа-яЁё])(?:эффект\w*|длительност\w+|сн[яи]\w*|леч\w+|"
                       r"излеч\w+|очищ\w+|наклад\w+|налож\w+|стак\w*|заряд\w*|"
                       r"вызыва\w+|вызов\w+|удал\w+)(?![А-Яа-яЁё])", re.I)
REQUIRE = {"Chill(?:ed|ing|s)?", "Chill(?:ed|ing|s)? ", "Slow(?:ed|s|ing)?",
           "Immobiliz(?:e|ed|es|ing)"}
# Замена, у которой меняется род («холод» м. -> «заморозка» ж., «могущество»
# ср. -> «мощь» ж.), ломает согласованное слово перед ней: «Зона леденящего
# холода» -> «леденящего заморозки», «ваше могущество» -> «ваше мощь». Если
# перед словом прилагательное или притяжательное — не трогаем.
SAME_GENDER = {"Protection", "Stability", "Vigor", "Superspeed", "Expertise",
               "Resolution", "Ferocity", "Toughness", "Swiftness"}
ADJ_BEFORE = re.compile(r"(?:(?<![А-Яа-яЁё])[А-Яа-яЁё]{2,}(?:ого|его|ому|ему|ым|им|ая|яя|"
                        r"ое|ее|ую|юю|ый|ий|ой)|(?<![А-Яа-яЁё])(?:ваш|наш|сво)[а-яё]*)\s+$", re.I)


def blocked(term, cur, start):
    """Нельзя ли менять слово в позиции start: нет признака состояния или
    перед ним согласованное слово, которое сломается от смены рода."""
    tail = re.split(r"[.;!?]|<br>|\n", cur[:start])[-1]
    if term in REQUIRE and not COND_MARK.search(tail):
        return True
    if term.split("(")[0].strip() not in SAME_GENDER and ADJ_BEFORE.search(cur[:start]):
        return True
    return False


# Пары, где у исходного слова именительный и винительный совпадают, а у канона
# нет: «увечье» среднего рода, «хромота» женского. Падеж выбираем по глаголу
# перед словом, иначе выходит «наносящих хромота».
AMBIG = {
    "Swiftness": ("стремительность", "Быстрота", "Быстроту"),
    "Cripple": ("увечье", "Хромота", "Хромоту"),
    "Chill(?:ed|ing|s)?": ("охлаждение", "Заморозка", "Заморозку"),
    # тот же ключ с пробелом — второе правило по тому же термину
    "Chill(?:ed|ing|s)? ": ("холод", "Заморозка", "Заморозку"),
    "Blindness": ("ослепление", "Слепота", "Слепоту"),
    "Regeneration": ("восстановление", "Регенерация", "Регенерацию"),
}
ACC_VERB = re.compile(r"(?<![А-Яа-яЁё])(?:получ\w+|дару\w+|даров\w+|подар\w+|"
                      r"наклад\w+|налож\w+|нанос\w+|нанес\w+|вызыва\w+|вызов\w+|"
                      r"вызыв\w+|причин\w+|прим\w+|обрет\w+|"
                      r"добав\w+|включ\w+|даёт|дает|дайте|снима\w+|снять|снимите|"
                      r"убира\w+|теря\w+|леч\w+|излеч\w+|очища\w+|очист\w+|"
                      # «обращает благодать врагов в мучение и увечье» — «в» + вин. падеж
                      r"обраща\w+|обрат\w+|превраща\w+|превра[тщ]\w+)(?![А-Яа-яЁё])", re.I)

# Канон в середине фразы пишется со строчной: корпус так делает в 1 218 случаях
# из 1 307, а заглавная («даровать Регенерацию») — след импорта с gw2skills,
# линтер ругает её как английский Title Case. Список — точные формы, а не
# основы: основа «Мощ» задела бы «Мощный», «Бол» — «Больше».
_CANON_FORMS = """
Эгида Эгиды Эгиде Эгиду Эгидой Рвение Рвения Рвению Рвением Рвении
Ярость Ярости Яростью Мощь Мощи Мощью Протекция Протекции Протекцию Протекцией
Проворство Проворства Проворству Проворством Проворстве
Регенерация Регенерации Регенерацию Регенерацией
Сопротивляемость Сопротивляемости Сопротивляемостью Решимость Решимости Решимостью
Устойчивость Устойчивости Устойчивостью Быстрота Быстроты Быстроте Быстроту Быстротой
Энергичность Энергичности Энергичностью
Кровотечение Кровотечения Кровотечению Кровотечением Кровотечении
Слепота Слепоты Слепоте Слепоту Слепотой Горение Горения Горению Горением Горении
Заморозка Заморозки Заморозке Заморозку Заморозкой
Замешательство Замешательства Замешательству Замешательством Замешательстве
Хромота Хромоты Хромоте Хромоту Хромотой Страх Страха Страху Страхом Страхе
Неподвижность Неподвижности Неподвижностью Отравление Отравления Отравлению Отравлением Отравлении
Медлительность Медлительности Медлительностью Провокация Провокации Провокацию Провокацией
Боль Боли Болью Уязвимость Уязвимости Уязвимостью Слабость Слабости Слабостью
Сверхскорость Сверхскорости Сверхскоростью Невидимость Невидимости Невидимостью
""".split()
LOWER_MID = re.compile(r"(?<=[а-яё,;] )(" + "|".join(sorted(_CANON_FORMS, key=len, reverse=True))
                       + r")(?![А-Яа-яЁё])")


def en_has(term, en):
    return re.search(r"(?<![A-Za-z])(?:" + term.strip() + r")(?![A-Za-z])", en, re.I)


def is_acc(before):
    """Винительный ли падеж — по управляющему глаголу в ТОМ ЖЕ предложении.

    Окном в пару слов не обойтись: в описаниях умений сплошные перечисления
    («Дарует ярость, мощь и быстроту»), и глагол оказывается далеко. Поэтому
    режем по границе предложения и ищем глагол во всём остатке.
    """
    tail = re.split(r"[.;!?]|<br>|\n", before)[-1]
    return bool(ACC_VERB.search(tail))


def load():
    if not os.path.exists(DB):
        sys.exit("нет sync/index.db — сначала `tools/index.py build`")
    db = sqlite3.connect(DB)
    mech = {r[0] for r in db.execute("SELECT hash FROM ctx WHERE kind='механика'")}
    return db, mech


def fix_one(en, ru):
    """Вернуть исправленный перевод и список сделанных замен."""
    out, done = ru, []
    for term, pairs in FIX.items():
        if not en_has(term, en):
            continue
        if term in SKIP_IF and re.search(SKIP_IF[term], en, re.I):
            continue
        before_rx, after_rx = GUARD.get(term, (None, None))
        for wrong, right in pairs:
            # Регистр берём символьным классом, а не группой: в шаблонах есть
            # свои скобки («сбивание ЦЕЛИ с ног»), и группа регистра сбила бы
            # им нумерацию — \1 в замене указывал бы на букву.
            rx = re.compile(r"(?<![А-Яа-яЁё])[" + wrong[0].upper() + wrong[0]
                            + "]" + wrong[1:] + r"(?![А-Яа-яЁё])")
            cur = out
            def rep(m, right=right, cur=cur, b=before_rx, a=after_rx, term=term):
                if blocked(term, cur, m.start()):
                    return m.group(0)
                if b and re.search(b, cur[:m.start()]):
                    return m.group(0)
                if a and re.search(a, cur[m.end():]):
                    return m.group(0)
                t = right if m.group(0)[0].isupper() else right[0].lower() + right[1:]
                return m.expand(t)
            new = rx.sub(rep, out)
            if new != out:
                done.append("%s: %s -> %s" % (term.split("(")[0], wrong, right))
                out = new
    for term, (wrong, nom, acc) in AMBIG.items():
        if not en_has(term, en):
            continue
        before_rx, after_rx = GUARD.get(term, (None, None))
        rx = re.compile(r"(?<![А-Яа-яЁё])(" + wrong[0].upper() + "|" + wrong[0]
                        + ")" + wrong[1:] + r"(?![А-Яа-яЁё])")
        cur = out
        def rep(m, nom=nom, acc=acc, cur=cur, b=before_rx, a=after_rx, term=term):
            if blocked(term, cur, m.start()):
                return m.group(0)
            if b and re.search(b, cur[:m.start()]):
                return m.group(0)
            if a and re.search(a, cur[m.end():]):
                return m.group(0)
            form = acc if is_acc(cur[:m.start()]) else nom
            return form if m.group(1).isupper() else form[0].lower() + form[1:]
        new = rx.sub(rep, out)
        if new != out:
            done.append("%s: %s -> %s/%s" % (term.split("(")[0], wrong, nom, acc))
            out = new
    resolve = re.search(r"(?<![A-Za-z])Resolve(?![A-Za-z])", en)
    def lower(m):
        w = m.group(1)
        if resolve and w.startswith("Решимост"):
            return w
        return w[0].lower() + w[1:]
    low = LOWER_MID.sub(lower, out)
    if low != out:
        done.append("регистр: заглавная в середине фразы")
        out = low
    return out, done


def is_skill_name(en):
    """Название умения, а не описание: несколько слов и без знака конца фразы.

    Решение пользователя 2026-08-11: в НАЗВАНИЯХ умений оставляем литературную
    форму — «Раскол мучений» читается лучше, чем «Раскол боли». Канон обязателен
    в описаниях. Голое имя самого термина («Torment», «Swiftness») — не название
    умения, а сам термин, и его канон касается.
    """
    en = en.strip()
    return (len(en.split()) > 1 and not re.search(r"[.!?:]", en)
            and len(en) < 48)


def cats_arg(args):
    """`--cats skill_descriptions,traits` -> множество категорий или None."""
    for i, a in enumerate(args):
        if a == "--cats" and i + 1 < len(args):
            return set(args[i + 1].split(","))
        if a.startswith("--cats="):
            return set(a.split("=", 1)[1].split(","))
    return None


def in_scope(db, mech, cats):
    """Хеши строк, которые правим: механика, и если заданы — только эти категории."""
    if not cats:
        return mech
    q = "SELECT hash FROM route_cat WHERE cat IN (%s)" % ",".join("?" * len(cats))
    return mech & {r[0] for r in db.execute(q, sorted(cats))}


def survey(cats=None):
    db, mech = load()
    mech = in_scope(db, mech, cats)
    changes, ex, refused = {}, [], 0
    skipped_names = 0
    for hh, en, ru in db.execute("SELECT hash, english, ru FROM string"):
        if hh not in mech or not en or not ru:
            continue
        if is_skill_name(en):
            skipped_names += 1
            continue
        new, done = fix_one(en, ru)
        if new == ru:
            continue
        if _validate is not None:
            was = len(_validate.check_row(en, ru)[0])
            if len(_validate.check_row(en, new)[0]) > was:
                refused += 1
                continue
        changes[hh] = (en, ru, new, done)
        if len(ex) < 12:
            ex.append((en, ru, new, done))
    return changes, ex, refused


def cmd_check(a):
    changes, ex, refused = survey(cats_arg(a))
    print("строк механики под правку: %d | отклонено гейтом: %d"
          % (len(changes), refused))
    per = collections.Counter(d.split(":")[0] for _e, _r, _n, dn in changes.values()
                              for d in dn)
    for t, n in per.most_common():
        print("   %5d  %s" % (n, t))
    print()
    if "--all" in a:
        ex = [(en, ru, new, done) for en, ru, new, done in changes.values()]
    for en, ru, new, done in ex:
        print("  EN    %s" % en[:100])
        print("  было  %s" % ru[:100])
        print("  стало %s   [%s]" % (new[:100], "; ".join(done)))


def cmd_apply(_a):
    changes, _ex, refused = survey(cats_arg(_a))
    if not changes:
        print("нечего менять")
        return
    by_en = {en: new for en, _ru, new, _d in changes.values()}
    upd = {}
    for h, (en, ru, _c) in D.load_map(D.OUR_BIN).items():
        if en in by_en and by_en[en] != ru:
            upd[h] = by_en[en]
    D.apply_changes(upd, {}, "канон боевых терминов")
    print("отклонено гейтом: %d" % refused)


def cmd_batches(_a):
    """Тот же канон по батчам — иначе bin и батчи разъедутся.

    Через `canonbatches` не выйдет: там правила `dict_tool.normalize`, а канон
    боевых терминов зависит от контекста строки, который знает только граф.

    Батч читается и пишется ТОЛЬКО через `dict_tool.read_csv`/`write_csv`.
    Прежняя версия писала голым `csv.writer` с разделителем LF, а корпус лежит
    с CR+LF: правка десяти ячеек переписывала каждую строку файла и давала
    гарантированный конфликт с любым открытым PR. И читала без `utf-8-sig`, так
    что файл с BOM молча пропускался — его шапка переставала быть «english».

    Правка считается по ячейке БАТЧА, а не берётся готовой из bin: источник
    истины — батч, и если он разошёлся с bin, затирать его значением из bin
    нельзя.
    """
    db, mech = load()
    mech = in_scope(db, mech, cats_arg(_a))
    want = {en for hh, en in db.execute("SELECT hash, english FROM string")
            if hh in mech and en and not is_skill_name(en)}
    total = refused = 0
    per = collections.Counter()
    for fp in D.batch_files():
        rows = D.read_csv(fp)
        if not rows or rows[0][:1] != ["english"]:
            continue
        n = 0
        for r in rows[1:]:
            if len(r) < 2 or r[0] not in want or not r[1].strip():
                continue
            new, done = fix_one(r[0], r[1])
            if new == r[1]:
                continue
            if _validate is not None:
                was = len(_validate.check_row(r[0], r[1])[0])
                if len(_validate.check_row(r[0], new)[0]) > was:
                    refused += 1
                    continue
            r[1] = new
            n += 1
            for d in done:
                per[d.split(":")[0]] += 1
        if n:
            D.write_csv(fp, rows)
            total += n
    print("поправлено ячеек батчей: %d | отклонено гейтом: %d" % (total, refused))
    for t, k in per.most_common():
        print("   %5d  %s" % (k, t))


CMDS = {"check": cmd_check, "apply": cmd_apply, "batches": cmd_batches}
if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in CMDS:
        sys.exit(__doc__)
    CMDS[sys.argv[1]](sys.argv[2:])
