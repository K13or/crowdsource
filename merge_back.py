#!/usr/bin/env python3
"""
Вливает готовые батчи перевода обратно в игровые файлы GlyphCore.

Использование:
    python merge_back.py <путь_к_папке_cyrillic> <папка_или_файл_с_готовыми_батчами>

Пример:
    python merge_back.py "C:/Games/Guild Wars 2/cyrillic" ./completed

Что делает:
  - собирает все переводы (english -> translate) из готовых батч-CSV;
  - в каждом игровом файле (dict_*.csv, cyrillic_strings.csv) заполняет ПУСТЫЕ строки,
    чей english совпадает (заполняет все дубли сразу);
  - проверяет, что набор плейсхолдеров/тегов в переводе совпадает с оригиналом
    (иначе строку пропускает и пишет в отчёт);
  - сохраняет исходные концы строк (CRLF/LF) и кодировку UTF-8;
  - никогда не перезаписывает уже переведённые строки.
"""
import csv, io, re, glob, os, sys

# Обязательны к сохранению: %подстановки%, <теги>, литеральные скобки [lbracket]/[rbracket]/[null].
# А вот [s] / [pl:"..."] (мн. число) ПРАВИЛЬНО превращаются в русское [форма1|форма2|форма3],
# поэтому в проверку токенов их НЕ включаем.
TOK = re.compile(r'%\w+%|<[^>]+>|\[lbracket\]|\[rbracket\]|\[null\]')

def tokens(s):
    return sorted(TOK.findall(s))

def load_completed(path):
    """path — файл .csv или папка с .csv (рекурсивно). Возвращает {english: translate}."""
    files = []
    if os.path.isdir(path):
        files = glob.glob(os.path.join(path, '**', '*.csv'), recursive=True)
    else:
        files = [path]
    m = {}
    dup_conflict = 0
    for p in files:
        with open(p, encoding='utf-8-sig', newline='') as f:
            r = csv.reader(f)
            header = next(r, None)
            for row in r:
                if len(row) < 2:
                    continue
                en, ru = row[0], row[1]
                if not ru.strip():
                    continue
                if en in m and m[en] != ru:
                    dup_conflict += 1
                    continue
                m.setdefault(en, ru)
    print(f"Загружено переводов: {len(m):,} из {len(files)} файлов "
          f"(конфликтов дублей проигнорировано: {dup_conflict})")
    return m

def merge_file(fn, tmap, report):
    raw = open(fn, 'rb').read()
    lt = '\r\n' if b'\r\n' in raw else '\n'
    rows = list(csv.reader(io.StringIO(raw.decode('utf-8'))))
    # защита: пере-сериализация без изменений должна дать байт-в-байт оригинал
    buf = io.StringIO(); csv.writer(buf, lineterminator=lt).writerows(rows)
    if buf.getvalue().encode('utf-8') != raw:
        print(f"  ПРОПУСК {os.path.basename(fn)}: не проходит round-trip (не трогаю)")
        return 0
    changed = 0
    for r in rows:
        if len(r) < 2 or r[1].strip():
            continue
        ru = tmap.get(r[0])
        if not ru:
            continue
        if tokens(r[0]) != tokens(ru):
            report.append((os.path.basename(fn), r[0][:60]))
            continue
        r[1] = ru
        changed += 1
    if changed:
        buf = io.StringIO(); csv.writer(buf, lineterminator=lt).writerows(rows)
        open(fn, 'wb').write(buf.getvalue().encode('utf-8'))
    return changed

def main():
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(1)
    cyr_dir, completed = sys.argv[1], sys.argv[2]
    tmap = load_completed(completed)
    if not tmap:
        print("Нет переводов для вливания."); return
    # off_dict_*.csv — временно отключённые словари (toggle_dict.bat):
    # переводы вливаем и в них, чтобы ничего не терялось, пока словарь выключен
    targets = sorted(glob.glob(os.path.join(cyr_dir, 'dict_*.csv'))) \
              + sorted(glob.glob(os.path.join(cyr_dir, 'off_dict_*.csv'))) \
              + [os.path.join(cyr_dir, 'cyrillic_strings.csv')]
    total = 0
    report = []
    for fn in targets:
        if not os.path.exists(fn):
            continue
        n = merge_file(fn, tmap, report)
        if n:
            print(f"  {os.path.basename(fn)}: +{n}")
        total += n
    print(f"\nИТОГО заполнено строк: {total:,}")
    if report:
        print(f"Пропущено из-за несовпадения плейсхолдеров: {len(report)} "
              f"(проверьте %str1%/теги в этих переводах):")
        for f, s in report[:30]:
            print(f"  [{f}] {s}")

if __name__ == '__main__':
    main()
