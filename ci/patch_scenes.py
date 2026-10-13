import sys, pathlib, re
pkg = pathlib.Path(sys.argv[1])          # .../клипы
eng = pkg / 'движок'
repo = pathlib.Path(sys.argv[2])         # workspace (ci/)
# 1) новые сцены
(eng / 'src' / 'scenes4.js').write_text((repo / 'ci' / 'scenes4.js').read_text(encoding='utf-8'), encoding='utf-8')
# 2) подключить в app.js
app = eng / 'src' / 'app.js'
s = app.read_text(encoding='utf-8')
if 'scenes4.js' not in s:
    s = s.replace("import { SCENES_C, makePhotoScene, makeTraceScene } from './scenes3.js';",
                  "import { SCENES_C, makePhotoScene, makeTraceScene } from './scenes3.js';\nimport { SCENES_D } from './scenes4.js';")
    s = s.replace("const SCENES = [...SCENES_A, ...SCENES_B, ...SCENES_C];",
                  "const SCENES = [...SCENES_A, ...SCENES_B, ...SCENES_C, ...SCENES_D];")
    app.write_text(s, encoding='utf-8')
# 3) синонимы сцен в script.js
sc = eng / 'src' / 'script.js'
t = sc.read_text(encoding='utf-8')
if "'солдат'" not in t:
    t = t.replace("  my_trace: ['обводка', 'рисунок', 'мой рисунок', 'обведи', 'trace'],",
"""  my_trace: ['обводка', 'рисунок', 'мой рисунок', 'обведи', 'trace'],
  soldier: ['солдат', 'военный', 'боец', 'война', 'soldier'],
  letter: ['письмо', 'конверт', 'треугольник', 'letter'],
  home: ['возвращение', 'домой', 'дома', 'home'],
  flame: ['память', 'вечныйогонь', 'вечный', 'огоньпамяти', 'flame'],""")
    sc.write_text(t, encoding='utf-8')
print('scenes patched ok')
