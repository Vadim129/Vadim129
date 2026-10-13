import sys, pathlib

pkg = pathlib.Path(sys.argv[1])          # .../клипы
eng = pkg / 'движок'
repo = pathlib.Path(sys.argv[2])         # workspace (ci/)
problems = []

# 1) новые сцены
(eng / 'src' / 'scenes4.js').write_text((repo / 'ci' / 'scenes4.js').read_text(encoding='utf-8'), encoding='utf-8')

# 2) подключить в app.js
app = eng / 'src' / 'app.js'
s = app.read_text(encoding='utf-8')
if 'scenes4.js' not in s:
    before = s
    s = s.replace("import { SCENES_C, makePhotoScene, makeTraceScene } from './scenes3.js';",
                  "import { SCENES_C, makePhotoScene, makeTraceScene } from './scenes3.js';\nimport { SCENES_D } from './scenes4.js';")
    s = s.replace("const SCENES = [...SCENES_A, ...SCENES_B, ...SCENES_C];",
                  "const SCENES = [...SCENES_A, ...SCENES_B, ...SCENES_C, ...SCENES_D];")
    app.write_text(s, encoding='utf-8')
    if s == before:
        problems.append('app.js: ни одна строка не заменилась — не вижу import/SCENES в ожидаемом виде')
if 'scenes4.js' not in app.read_text(encoding='utf-8'):
    problems.append('app.js: SCENES_D так и не подключён')

# 3) синонимы сцен в script.js
sc = eng / 'src' / 'script.js'
t = sc.read_text(encoding='utf-8')
if "'солдат'" not in t:
    before = t
    t = t.replace("  my_trace: ['обводка', 'рисунок', 'мой рисунок', 'обведи', 'trace'],",
"""  my_trace: ['обводка', 'рисунок', 'мой рисунок', 'обведи', 'trace'],
  soldier: ['солдат', 'военный', 'боец', 'soldier'],
  letter: ['письмо', 'конверт', 'письмо домой', 'letter'],
  home: ['возвращение', 'возвращение домой', 'домой', 'дома', 'home'],
  flame: ['память', 'вечный огонь', 'вечныйогонь', 'огонь памяти', 'flame'],""")
    if t == before:
        problems.append('script.js: не нашёл строку синонимов my_trace — вставка не сработала')
    sc.write_text(t, encoding='utf-8')
if "'солдат'" not in sc.read_text(encoding='utf-8'):
    problems.append('script.js: синоним «солдат» так и не появился')

# 4) показать, что видит движок
print('=== сцены в patched app.js ===')
for line in app.read_text(encoding='utf-8').splitlines():
    if 'SCENES =' in line or 'scenes4' in line:
        print(' ', line.strip())
print('=== синонимы солдата/письма/дома/огня ===')
for line in sc.read_text(encoding='utf-8').splitlines():
    if any(k in line for k in ('soldier:', 'letter:', 'home:', 'flame:')):
        print(' ', line.strip())

# 5) надписи сцен: меняем «дневниковые» фразы на военные (по песне «Я вернусь к тебе домой»)
def swap(path, pairs):
    t = path.read_text(encoding='utf-8')
    for old, new in pairs:
        if new in t:
            print(f'  уже заменено в {path.name}: {new!r}')
            continue
        if old not in t:
            problems.append(f'{path.name}: не нашёл {old!r} — замена не сделана')
            continue
        t = t.replace(old, new, 1)
        print(f'  {path.name}: {old!r} → {new!r}')
    path.write_text(t, encoding='utf-8')

print('=== надписи сцен ===')
swap(eng / 'src' / 'scenes1.js', [
    ("p.text('мне сегодня', 540, 1320", "p.text('дождись меня', 540, 1320"),
    ("p.text('можно', 540, 1490", "p.text('вернусь', 540, 1490"),
])
swap(eng / 'src' / 'scenes2.js', [
    ("const txt1 = 'мне сегодня', txt2 = 'можно';", "const txt1 = 'я вернусь', txt2 = 'домой';"),
])
for f, want in ((eng / 'src' / 'scenes1.js', 'дождись меня'), (eng / 'src' / 'scenes1.js', 'вернусь'),
                (eng / 'src' / 'scenes2.js', "'я вернусь', txt2 = 'домой'")):
    if want not in f.read_text(encoding='utf-8'):
        problems.append(f'{f.name}: не вижу {want!r} после правки')

if problems:
    print('\nПРОБЛЕМЫ:')
    for p in problems:
        print(' -', p)
    sys.exit(1)
print('scenes patched ok')

