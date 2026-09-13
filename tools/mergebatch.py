#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Разрешить конфликт слияния батчей по ЗАПИСЯМ, а не по строкам файла.

    git merge <ветка>            # упал конфликт
    python tools/mergebatch.py   # свести и добавить в индекс
    git commit

Зачем. Очередь партий правит один и тот же корпус, и git видит конфликт там,
где спора нет: запись батча занимает десятки строк файла, соседние правки
попадают в один кусок diff, и слияние встаёт. Разрешать это руками — работа на
часы, а «взять свою сторону» молча теряет чужую партию.

Здесь конфликт разбирается по ключу `english`:

* запись изменила одна сторона — берётся она;
* обе изменили ОДИНАКОВО — берётся общий результат;
* обе изменили ПО-РАЗНОМУ — правки сводятся по словам: где куски не
  пересекаются, берутся обе; где пересекаются, решают два правила ниже;
* свести не удалось — это настоящий спор, он печатается, а файл остаётся
  конфликтным для разбора руками.

Два правила на пересекающиеся куски, и оба следуют уже записанному канону:

**Латиница старше орфографии.** Партия имён вернула кусок латиницей
(«свободных Пробужденных» -> `Free Awakened`), партия ё поправила буквы в том же
куске («Пробуждённых»). Обе правки верны порознь, но CLAUDE.md §1 требует, чтобы
строку, которую держит слой, батч хранил ПО-АНГЛИЙСКИ: иначе не работает
выключатель имён, а расставленная внутри имени ё всё равно исчезнет при
подстановке.

**Знаки складываются.** Партия многоточий приводит знак к форме оригинала
(«…» -> «...»), партия пунктуации переставляет его со знаком вопроса
(«...?» -> «?..»). Это не спор: нужно и то, и другое. Если после приведения к
общему виду обе стороны дают одно и то же — это и есть их сумма.

Проверено на очереди из 18 партий: 11 514 правок, слияние прошло без единого
настоящего спора, и ни одна правка не потерялась. Сверка обратная — для каждой
ветки берётся её собственный diff от main, и всё, что она вписала, ищется в
объединении.

Формат файла сохраняется: записи режутся сырыми и склеиваются обратно, поэтому
кавычки и переносы остаются как были, а diff не раздувается на строки, которых
слияние не касалось.
"""
import difflib
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CROWD = os.path.dirname(HERE)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TOKEN = re.compile(r"\s+|\w+|.")
CYR = re.compile(r"[А-Яа-яЁё]")
SWAP = re.compile(r"(?:\.{3}|…)\s*([?!])")
QUOTE = '"'


# --- сырой разбор CSV -------------------------------------------------------
# Обычный csv.writer нормализует кавычки: поле, закавыченное без нужды, теряет
# кавычки, и diff раздувается на записи, которых слияние не касалось. Поэтому
# файл режется на сырые записи, а подменяется только колонка перевода.

def split_records(text):
    """[(raw, fields)] — сырой текст записи (с концом строки) и её поля."""
    out, i, n = [], 0, len(text)
    while i < n:
        start = i
        fields, cur, quoted, in_q = [], [], False, False
        while i < n:
            ch = text[i]
            if in_q:
                if ch == QUOTE:
                    if i + 1 < n and text[i + 1] == QUOTE:
                        cur.append(QUOTE)
                        i += 2
                        continue
                    in_q = False
                    i += 1
                    continue
                cur.append(ch)
                i += 1
                continue
            if ch == QUOTE and not cur:
                in_q, quoted = True, True
                i += 1
                continue
            if ch == ",":
                fields.append(("".join(cur), quoted))
                cur, quoted = [], False
                i += 1
                continue
            if ch == "\n":
                i += 1
                break
            if ch == "\r":
                i += 1
                continue
            cur.append(ch)
            i += 1
        fields.append(("".join(cur), quoted))
        out.append((text[start:i], fields))
    return out


def render_field(value, was_quoted):
    if was_quoted or any(c in value for c in ",\r\n" + QUOTE):
        return QUOTE + value.replace(QUOTE, QUOTE * 2) + QUOTE
    return value


def replace_field(raw, fields, idx, new_value):
    tail = ""
    while raw and raw[-1] in "\r\n":
        tail = raw[-1] + tail
        raw = raw[:-1]
    parts = [render_field(new_value if k == idx else val, q)
             for k, (val, q) in enumerate(fields)]
    return ",".join(parts) + tail


# --- правила на пересекающиеся правки ---------------------------------------

def dots_norm(s):
    """Многоточие к форме оригинала и порядок знаков к русскому: «…?» -> «?..»."""
    return SWAP.sub(r"\g<1>..", s.replace("…", "..."))


def dots_merge(a, b):
    na, nb = dots_norm("".join(a)), dots_norm("".join(b))
    return list(na) if na == nb else None


def latin_wins(base, a, b):
    """Кусок, возвращённый латиницей, старше правки букв внутри кириллицы."""
    if not CYR.search("".join(base)):
        return None
    ca, cb = CYR.search("".join(a)), CYR.search("".join(b))
    if ca and not cb:
        return b
    if cb and not ca:
        return a
    return None


# --- слияние одной записи ---------------------------------------------------

def weld(base, ours, theirs):
    """Строка, вобравшая правки обеих сторон, либо None — настоящий спор."""
    got = _weld(base, ours, theirs)
    if got is not None:
        return got
    # Запасной проход для спора о многоточии: границы правок разъезжаются —
    # одна сторона меняет знак на месте, другая переносит его через соседний
    # символ, — и куски базы уже не совпадают. Тогда обе стороны приводятся к
    # общему виду, и слияние повторяется: то, что осталось разным после этого,
    # уже не про знаки, а про слова.
    nb, no, nt = (dots_norm(x) for x in (base, ours, theirs))
    if nb != base and (no != ours or nt != theirs):
        return _weld(nb, no, nt)
    return None


def _weld(base, ours, theirs):
    b, o, t = (TOKEN.findall(x) for x in (base, ours, theirs))
    so = difflib.SequenceMatcher(None, b, o, autojunk=False).get_opcodes()
    st = difflib.SequenceMatcher(None, b, t, autojunk=False).get_opcodes()

    def marks(ops):
        return [(i1, i2) for tag, i1, i2, _j1, _j2 in ops if tag != "equal"]

    def span(ops, i1, i2):
        """Куда кусок базы [i1,i2) уехал на этой стороне."""
        j1 = j2 = None
        for tag, a1, a2, c1, c2 in ops:
            if a2 <= i1 or a1 >= i2:
                continue
            lo = c1 + (max(a1, i1) - a1 if tag == "equal" else 0)
            hi = c2 - (a2 - min(a2, i2) if tag == "equal" else 0)
            j1 = lo if j1 is None else min(j1, lo)
            j2 = hi if j2 is None else max(j2, hi)
        return (j1, j2) if j1 is not None else (None, None)

    groups = []
    for i1, i2 in sorted(marks(so) + marks(st)):
        if groups and i1 <= groups[-1][1]:
            groups[-1][1] = max(groups[-1][1], i2)
        else:
            groups.append([i1, max(i2, i1 + 1)])

    out, pos = [], 0
    for i1, i2 in groups:
        out.extend(b[pos:i1])
        oj = span(so, i1, i2)
        tj = span(st, i1, i2)
        po = o[oj[0]:oj[1]] if oj[0] is not None else b[i1:i2]
        pt = t[tj[0]:tj[1]] if tj[0] is not None else b[i1:i2]
        if po == pt or pt == b[i1:i2]:
            out.extend(po)
        elif po == b[i1:i2]:
            out.extend(pt)
        else:
            pick = latin_wins(b[i1:i2], po, pt) or dots_merge(po, pt)
            if pick is None:
                return None
            out.extend(pick)
        pos = i2
    out.extend(b[pos:])
    return "".join(out)


# --- слияние файла ----------------------------------------------------------

def stage(n, rel):
    """Ступень конфликта из индекса: 1 база, 2 наша, 3 их."""
    r = subprocess.run(["git", "show", ":%d:%s" % (n, rel)], cwd=CROWD,
                       capture_output=True)
    return r.stdout.decode("utf-8-sig") if r.returncode == 0 else None


def index(text):
    return {f[0][0]: (raw, f[1][0]) for i, (raw, f) in
            enumerate(split_records(text)) if i and len(f) >= 2}


def merge_file(rel):
    """(текст, споры). Текст None — файл этим способом не сводится."""
    base, ours, theirs = (stage(n, rel) for n in (1, 2, 3))
    if None in (base, ours, theirs):
        return None, [("<нет одной из ступеней>", "", "", "")]
    b, o, t = index(base), index(ours), index(theirs)
    fights, take, welded, dropped = [], {}, {}, set()
    for k in set(o) | set(t):
        ov = o.get(k, (None, None))[1]
        tv = t.get(k, (None, None))[1]
        bv = b.get(k, (None, None))[1]
        if ov == tv:
            continue
        # Запись СНЯТА одной стороной. Партии удаления («мёртвые копии»,
        # «немецкие строки») первыми принесли этот случай, и раньше он валил
        # слияние с KeyError: код лез за текстом туда, где записи уже нет.
        # Правило простое и совпадает с git: снятие проходит, если вторая
        # сторона запись не трогала. Тронула — это спор, и решать его руками.
        if k not in o or k not in t:
            if k not in b:
                # записи не было в базе: одна сторона её ДОБАВИЛА
                if k in t:
                    take[k] = t[k][0]
                continue
            # запись была в базе и снята одной из сторон
            other = tv if k not in o else ov
            if other == bv:
                dropped.add(k)
            else:
                fights.append((k, bv, ov, tv))
            continue
        if ov != bv and tv != bv:
            w = weld(bv, ov, tv) if None not in (bv, ov, tv) else None
            if w is None:
                fights.append((k, bv, ov, tv))
            elif w != ov:
                welded[k] = w
        elif ov != bv:
            take[k] = o[k][0]
        else:
            take[k] = t[k][0]
    if fights:
        return None, fights
    out, seen = [], set()
    for i, (raw, f) in enumerate(split_records(ours)):
        k = f[0][0] if len(f) >= 2 else None
        if i and k in dropped:
            continue
        if i and k in take:
            out.append(take[k])
        elif i and k in welded:
            out.append(replace_field(raw, f, 1, welded[k]))
        else:
            out.append(raw)
        seen.add(k)
    for k, raw in take.items():
        if k not in seen:
            out.append(raw)
    return "".join(out), []


def main(check):
    files = subprocess.run(["git", "diff", "--name-only", "--diff-filter=U"],
                           cwd=CROWD, capture_output=True,
                           text=True).stdout.split()
    if not files:
        print("конфликтов нет")
        return 0
    done, left = 0, 0
    for rel in files:
        text, fights = merge_file(rel)
        if text is None:
            left += 1
            print("СПОР в %s: %d записей" % (rel, len(fights)))
            for k, bv, ov, tv in fights[:3]:
                # None здесь значит «записи на этой стороне нет»: её сняла
                # партия удаления, а вторая сторона в это время правила текст
                show = lambda v: ("<запись снята>" if v is None
                                  else str(v)[:70].replace("\n", " "))
                print("   ключ  %s" % str(k)[:70].replace("\n", " "))
                print("   было  %s" % show(bv))
                print("   наше  %s" % show(ov))
                print("   их    %s" % show(tv))
            continue
        done += 1
        if check:
            continue
        path = os.path.join(CROWD, rel)
        blob = open(path, "rb").read()
        bom = blob[:3] == b"\xef\xbb\xbf"
        open(path, "wb").write((b"\xef\xbb\xbf" if bom else b"")
                               + text.encode("utf-8"))
        subprocess.run(["git", "add", "--", rel], cwd=CROWD, check=True)
    print("%s: %d, осталось на разбор руками: %d"
          % ("свелось" if check else "сведено и добавлено в индекс", done, left))
    return 1 if left else 0


if __name__ == "__main__":
    sys.exit(main("--check" in sys.argv))
