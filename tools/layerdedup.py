#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""НЕ ЗАПУСКАТЬ. Инструмент ломает перевод в игре (2026-09-28).

Он оставляет в категории английский оригинал в расчёте, что мод подставит
русскую форму из слоя. Мод этого не делает: запись категории, даже английская,
перекрывает слой, и игрок видит английский при любых настройках. Так 78 624
названия были английскими от 2026-09-03 до 2026-09-28. Оставлен ради истории.

Убрать дубли «категория повторяет слой»: одно название — одно место.

    python tools/layerdedup.py plan    # что изменится
    python tools/layerdedup.py apply   # переписать батчи и bin

Зачем. Название живёт в двух местах сразу: в своей категории и в слое `pn_*`,
с одинаковым русским текстом. Любой из двух выключателей по отдельности
бесполезен — игрок гасит слой, форму отдаёт категория; гасит категорию, форму
подставляет слой. Чтобы увидеть английское, надо погасить оба, а слой заводился
не для этого.

Лечение: **в категории остаётся английский оригинал, русскую форму держит слой**.
При включённом слое игрок видит тот же текст, что и раньше; при выключенном —
наконец английский. Перевод не пропадает: он никуда не девается из `pn_*`.

Английский ставим переводом, а не пустотой: строка остаётся «сделанной» и не
уйдёт снова в раздачу переводчикам.
"""
import collections, csv, glob, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
CROWD = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import dict_tool as D

CYR = re.compile("[А-Яа-яЁё]")
# Разметку слой не отрисует, поэтому такие строки обязаны остаться переведёнными
# в своей категории — их не трогаем, даже если текст совпал.
MARKUP = re.compile(r"\[(?:s|pl:|f:|pf:|pm:)|%\w+%|<[^>]+>")


def targets():
    """{english: (русский, [категории])} — дубли, которые можно снять."""
    lay, cat = {}, collections.defaultdict(dict)
    for name, es in D.read_sections(D.OUR_BIN):
        c = name.partition("\x1f")[0]
        if c.startswith("pn_"):
            for h, en, ru in es:
                lay.setdefault(en.strip(), ru.strip())
        else:
            for h, en, ru in es:
                cat[c][en.strip()] = ru.strip()
    out, skip = {}, collections.Counter()
    for c, m in cat.items():
        for en, ru in m.items():
            if not ru or lay.get(en) != ru:
                continue
            if not CYR.search(ru):
                skip["в категории уже латиница"] += 1
                continue
            if MARKUP.search(en):
                skip["разметка — слой не отрисует"] += 1
                continue
            out.setdefault(en, (ru, []))[1].append(c)
    return out, skip


def cmd_plan():
    t, skip = targets()
    per = collections.Counter()
    for en, (ru, cats) in t.items():
        for c in cats:
            per[c] += 1
    print("строк к снятию дубля: %d" % sum(per.values()))
    for c, v in per.most_common(12):
        print("  %-22s %6d" % (c, v))
    if skip:
        print("\nпропущено:")
        for k, v in skip.most_common():
            print("  %-32s %6d" % (k, v))


def cmd_apply():
    t, _skip = targets()
    names = set(t)
    nb = 0
    for fp in sorted(glob.glob(os.path.join(CROWD, "*", "*.csv"))):
        d = os.path.relpath(fp, CROWD).replace(os.sep, "/").split("/")[0]
        if d in ("sync", "split", "pn"):
            continue
        try:
            rows = D.read_csv(fp)
        except Exception:
            continue
        if not rows or rows[0][:1] != ["english"]:
            continue
        ch = 0
        for r in rows[1:]:
            if len(r) >= 2 and r[0].strip() in names and r[1].strip() != r[0]:
                r[1] = r[0]
                ch += 1
        if ch:
            D.write_csv(fp, rows)
            nb += ch
    print("правок в батчах: %d" % nb)

    sections = D.read_sections(D.OUR_BIN)
    out, nbin = [], 0
    for name, es in sections:
        c = name.partition("\x1f")[0]
        if c.startswith("pn_"):
            out.append((name, es))
            continue
        new = []
        for h, en, ru in es:
            if en.strip() in names and ru.strip() != en:
                ru = en
                nbin += 1
            new.append((h, en, ru))
        out.append((name, new))
    bak = D.backup(D.OUR_BIN)
    ncat, total = D.write_bin(D.OUR_BIN, out)
    print("правок в bin: %d | %d категорий, %d записей" % (nbin, ncat, total))
    print("бэкап: %s" % os.path.relpath(bak, D.ROOT))


if __name__ == "__main__":
    a = sys.argv[1] if len(sys.argv) > 1 else ""
    if a == "apply":
        # 2026-09-28: запись категории перекрывает слой — apply делает
        # названия английскими в игре. См. докстроку и DEFECTS.md.
        sys.exit("layerdedup apply отключён: английский в категории перекрывает слой, "
                 "игрок видит оригинал при любых настройках (DEFECTS.md, 2026-09-28)")
    if a == "plan":
        cmd_plan()
    elif a == "apply":
        cmd_apply()
    else:
        sys.exit(__doc__)
