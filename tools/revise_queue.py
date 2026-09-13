# -*- coding: utf-8 -*-
"""Ревизия веток очереди: перепроверить чужие правки другими проверками.

    python tools/revise_queue.py                 # все открытые PR автора
    python tools/revise_queue.py names-bulk5     # только эти ветки

Зачем. У каждой партии свой гейт, и он смотрит на свой класс в момент правки.
Но порча вылезает там, куда гейт не смотрел: партия имён следит за именами и не
замечает, что задвоился НОМЕР, партия транскрипции сводит буквы и не видит, что
получился тройной повтор слова. Поэтому здесь проверки НАМЕРЕННО другие — иначе
ревизия повторила бы ошибку применялки.

На очереди из 19 веток эти проверки нашли 12 испорченных строк, которые прошли
все входные гейты:

* «Охота на разломы 2-го уровняТы получил» -> подстановка `Tier 2` съела начало
  следующего предложения (в оригинале два предложения слиты без пробела);
* «до Mount Energy Booster 3 3» -> имя в слое уже несёт номер, а прежний остался;
* «Memory of Old Lion's Arch Lion's Arch» -> слой держит и целое, и часть,
  подстановка прошла дважды;
* «Давно утерянного Тахкаюна Тахкаюна Тахкаюна» -> сведение транскрипции в
  записи, где имя и так стояло дважды.

Что проверяется у каждой изменённой записи (исходник — из точки ветвления):

* **разметка**: число плейсхолдеров `%…%`, тегов `<c=…>`, скобочных групп и
  маркеров `[s]`/`[pl:…]` не должно измениться, а группы обязаны иметь ровно
  три части (две законны только при родовом маркере в оригинале);
* **числа**: набор чисел в переводе не должен разойтись с прежним;
* **латиница**: английские отрезки, стоявшие в переводе, не должны исчезнуть
  или удвоиться — так ловится порча подстановки имён;
* **повторы**: слово, идущее дважды подряд, — след склейки;
* **линтер**: ошибок не должно прибавиться.

Сравнение идёт с ТОЧКОЙ ВЕТВЛЕНИЯ, а не с текущим main: ветка, снятая до
вливания чужой очереди, иначе выглядит так, будто откатывает её правки, — и
отчёт тонет в тысячах мнимых замечаний.

Часть находок всегда ложная, и это нормально: партия, которая переводит
служебное слово («Recipe: X» -> «Рецепт: X»), законно убирает латиницу, а
партия групп форм законно меняет разметку. Отчёт называет класс и печатает
примеры — решение за человеком.

Притяжательная форма при сравнении имён нормализуется: без этого «Balthazar's»
в оригинале и «Balthazar» в переводе считаются разными словами, и класс
«имя удвоено» тонет в ложных срабатываниях.

Ветки читаются одним `git cat-file --batch`: отдельный `git show` на файл стоил
часа на прошлом заходе.
"""
import collections
import csv
import io
import os
import re
import subprocess
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import validate

PH = re.compile(r"%\w+%")
TAG = re.compile(r"<[^>]*>")
GROUP = re.compile(r"\[[^\[\]]*\|[^\[\]]*\]")
PLMARK = re.compile(r"\[s\]|\[pl:|\[pf:|\[pm:|\[f:")
NUM = re.compile(r"\d+")
LAT = re.compile(r"[A-Za-z][A-Za-z’\-]*(?:'s)?")
RU2 = re.compile(r"(?<![А-Яа-яЁё])([А-Яа-яЁё]{3,})\s+\1(?![А-Яа-яЁё])", re.I)
GENDER = re.compile(r"\[(?:f|pf|pm):")


def read_many(pairs):
    """{(ref, path): текст} одним процессом."""
    if not pairs:
        return {}
    keys = list(pairs)
    req = "".join("%s:%s\n" % k for k in keys).encode("utf-8")
    p = subprocess.run(["git", "cat-file", "--batch"], cwd=ROOT,
                       input=req, capture_output=True)
    out, buf, i = {}, p.stdout, 0
    for k in keys:
        nl = buf.find(b"\n", i)
        if nl < 0:
            out[k] = None
            continue
        head = buf[i:nl].decode("utf-8", "replace")
        if head.endswith(("missing", "ambiguous")):
            out[k] = None
            i = nl + 1
            continue
        size = int(head.rsplit(" ", 1)[1])
        out[k] = buf[nl + 1:nl + 1 + size].decode("utf-8-sig")
        i = nl + 1 + size + 1
    return out


def index(text):
    """{english: translate} из содержимого батча.

    `csv.reader` по списку строк, а не по файлу: содержимое приходит из git.
    Разделение на строки делает сам reader, поэтому переносы внутри
    закавыченного поля не теряются — та же забота, что у `dict_tool.read_csv`
    с `newline=""`.
    """
    if not text:
        return {}
    rows = list(csv.reader(io.StringIO(text, newline="")))
    return {r[0]: r[1] for r in rows[1:] if len(r) >= 2}


def names(s):
    """Латинские слова, приведённые к общему виду: «Balthazar's» и «Balthazar»
    — одно имя, иначе подстановка притяжательной формы выглядит удвоением."""
    return collections.Counter(w.rstrip("'s").lower() for w in LAT.findall(s)
                               if len(w.rstrip("'s")) > 2)


def marks(s):
    return (len(PH.findall(s)), len(TAG.findall(s)), len(GROUP.findall(s)),
            len(PLMARK.findall(s)))


if len(sys.argv) > 1:
    pairs = [("-", b) for b in sys.argv[1:]]
else:
    # без аргументов берём открытые PR автора: gh сам знает, кто это
    out = subprocess.run(
        ["gh", "pr", "list", "--author", "@me", "--limit", "40", "--json",
         "number,headRefName", "--jq", r'.[] | "\(.number) \(.headRefName)"'],
        cwd=ROOT, capture_output=True, text=True).stdout
    pairs = [b.split() for b in out.splitlines() if b.strip()]

print("веток очереди: %d" % len(pairs))

total_bad = 0
for num, br in pairs:
    # Сравнивать надо с ТОЧКОЙ ВЕТВЛЕНИЯ, а не с текущим main: ветка, снятая до
    # вливания чужой очереди, иначе выглядит так, будто откатывает её правки —
    # хотя при слиянии они сохранятся.
    base = subprocess.run(["git", "merge-base", "refs/heads/main",
                           "refs/heads/" + br], cwd=ROOT,
                          capture_output=True, text=True).stdout.strip()
    files = subprocess.run(
        ["git", "-c", "core.quotepath=false", "diff", "--name-only",
         base, "refs/heads/" + br],
        cwd=ROOT, capture_output=True, text=True).stdout.split()
    files = [f for f in files if f.endswith(".csv")]
    if not files:
        print("  #%-4s %-22s правок нет (не батчи)" % (num, br))
        continue
    want = set()
    for rel in files:
        want.add((base, rel))
        want.add(("refs/heads/" + br, rel))
    blobs = read_many(sorted(want))
    bad = collections.Counter()
    shown = []
    n = 0
    for rel in files:
        a = index(blobs.get((base, rel)))
        b = index(blobs.get(("refs/heads/" + br, rel)))
        for en, now in b.items():
            was = a.get(en)
            if was is None or was == now:
                continue
            n += 1
            if marks(was) != marks(now):
                bad["разметка изменилась"] += 1
                if len(shown) < 3:
                    shown.append((rel, was, now))
                continue
            for g in GROUP.finditer(now):
                if g.group(0).count("|") != 2 and not GENDER.search(en):
                    bad["группа не из трёх форм"] += 1
                    if len(shown) < 3:
                        shown.append((rel, was, now))
            if NUM.findall(was) != NUM.findall(now):
                bad["набор чисел изменился"] += 1
                if len(shown) < 3:
                    shown.append((rel, was, now))
            la, lb = names(was), names(now)
            ne = names(en)
            for w, c in la.items():
                if lb.get(w, 0) < c and w in en.lower():
                    bad["латиница из перевода исчезла"] += 1
                    if len(shown) < 3:
                        shown.append((rel, was, now))
                    break
            for w, c in lb.items():
                if c > max(ne.get(w, 0), la.get(w, 0)):
                    bad["имя стоит чаще, чем в оригинале"] += 1
                    if len(shown) < 3:
                        shown.append((rel, was, now))
                    break
            if RU2.search(now) and not RU2.search(was):
                bad["слово повторено подряд"] += 1
                if len(shown) < 3:
                    shown.append((rel, was, now))
            e1, _ = validate.check_row(en, was)
            e2, _ = validate.check_row(en, now)
            if len(e2) > len(e1):
                bad["линтер: новых ошибок"] += 1
    total_bad += sum(bad.values())
    flag = "  ".join("%s %d" % (k, v) for k, v in bad.most_common())
    print("  #%-4s %-22s правок %5d   %s" % (num, br, n, flag or "чисто"))
    for rel, was, now in shown:
        print("        %s" % rel)
        print("           было  %s" % was[:88].replace("\n", " "))
        print("           стало %s" % now[:88].replace("\n", " "))
print("\nвсего замечаний по очереди: %d" % total_bad)
