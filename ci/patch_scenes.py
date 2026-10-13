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

# 6) монтаж своих кадров: функция mount(spec) кладёт страницы-картинки по таймингу песни
MOUNT_JS = r'''
function __photoScene(makeCanvas, dur) {
  return {
    id: 'shot', dur,
    draw(p, t, S) {
      const canvas = makeCanvas();
      if (!canvas) return;
      const grow = U.ss(.7, 2.0, t);
      const z = 1 + grow * .014;
      p.raster(canvas, 540 - 540 * z, 960 - 960 * z, 1080 * z, 1920 * z, { t0: .7, t1: 2.0, alpha: 1 });
    },
  };
}

function mount(spec) {
  const frames = window.__FRAMES || {};
  const segs = spec.scenes.map((s, i) => {
    const dur = s.t1 - s.t0;
    const sc = __photoScene(() => frames[s.key], dur);
    sc.id = s.key;
    byId[s.key] = sc;
    const seg = {
      id: s.key, t0: s.t0, t1: s.t1, dur, index: i, params: {},
      seed: s.seed || (11 + i * 37), transition: s.transition || 'flip',
      cam: s.cam || { a: { nx: 0, ny: 0, z: 1.0, r: -.003 }, b: { nx: 0, ny: 0, z: 1.05, r: .004 } },
    };
    seg.local = t => U.clamp(t - seg.t0, 0, seg.dur);
    return seg;
  });
  if (spec.profile) state.profile = spec.profile;
  if (spec.paper) state.paper = spec.paper;
  if (spec.palette) state.palette = spec.palette;
  if (spec.mood) state.mood = spec.mood;
  if (spec.dens) state.dens = spec.dens;
  if (spec.size) { state.quality = spec.size[0] + 'x' + spec.size[1]; setSize(spec.size[0], spec.size[1]); }
  tl = { segments: segs, duration: spec.duration, profile: state.profile, paper: state.paper,
         palette: state.palette, mood: state.mood, dens: state.dens, analysis: audio.analysis,
         scenesById: byId };
  applyStyle();
  renderer.setStyle({ paper: state.paper });
  if (typeof invalidateClip === 'function') invalidateClip();
  seek(0);
  return { scenes: segs.length, duration: tl.duration, size: [canvas.width, canvas.height] };
}
'''
s = app.read_text(encoding='utf-8')
if 'function mount(spec)' not in s:
    if 'window.INK = { state, audio,' not in s:
        problems.append('app.js: не нашёл строку window.INK = { state, audio, — mount не вставится')
    else:
        s = s.replace('window.INK = { state, audio,',
                      MOUNT_JS + '\nwindow.INK = { mount, state, audio,')
        app.write_text(s, encoding='utf-8')
        print('  app.js: добавлена функция mount(spec)')
if 'mount,' not in app.read_text(encoding='utf-8'):
    problems.append('app.js: mount так и не подключён к window.INK')

if problems:
    print('\nПРОБЛЕМЫ:')
    for p in problems:
        print(' -', p)
    sys.exit(1)
print('scenes patched ok')

