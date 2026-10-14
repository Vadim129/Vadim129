#!/bin/bash
# fetch-whisper-assets.sh — кладёт Whisper внутрь проекта: библиотека + wasm-движок + модель.
# Нужен, если папки vendor/ и models/ пропали (они тяжёлые и не всегда сохраняются).
# После этого папка www/ собирается build-www.mjs, а APK — npm run android:apk.
#
# Запуск:  bash tools/fetch-whisper-assets.sh
set -e
cd "$(dirname "$0")/.."
mkdir -p vendor/transformers vendor/ort vendor/node models/whisper-tiny/onnx

echo "1/5 библиотека transformers.js (локальная сборка)"
curl -sL -o vendor/transformers/transformers.js "https://esm.sh/@huggingface/transformers@3.3.3?bundle&target=es2022"
curl -sL -o vendor/transformers/transformers.bundle.mjs "https://esm.sh/@huggingface/transformers@3.3.3/es2022/transformers.bundle.mjs"
curl -sL -o vendor/node/process.mjs "https://esm.sh/node/process.mjs"
curl -sL -o vendor/node/buffer.mjs "https://esm.sh/node/buffer.mjs"

echo "2/5 заглушки node-модулей и относительные пути"
for m in events tty async_hooks; do curl -sL -o "vendor/node/$m.mjs" "https://esm.sh/node/$m.mjs"; done
python3 - <<'PY'
import re, pathlib
V = pathlib.Path('vendor')
def fix_spec(m):
    spec = m.group(1)
    if spec.startswith(('.', '/', 'http://', 'https://')) or ':' in spec.split('/')[0]:
        return m.group(0)
    return 'from"./%s"' % spec
def fix_import(m):
    spec = m.group(1)
    if spec.startswith(('.', '/', 'http')): return m.group(0)
    return 'import"./%s"' % spec
for f in list(V.rglob('*.mjs')):
    t0 = f.read_text(errors='ignore'); t = t0
    def rel(m):
        import os
        return m.group(0).replace(m.group(1), os.path.relpath(V / m.group(1).lstrip('/'), f.parent))
    t = re.sub(r'(?:from|import)\s*"(/[^"]+\.mjs)"', rel, t)       # абсолютные → относительные
    t = re.sub(r'from"([^"]+\.mjs)"', fix_spec, t)                # незнакомые → ./файл
    t = re.sub(r'import"([^"]+\.mjs)"', fix_import, t)
    if t != t0: f.write_text(t); print('  пути исправлены:', f)
for f in (V / 'node').glob('*.mjs'):
    t0 = f.read_text(errors='ignore'); t = t0.replace("'./node/", "'./").replace('"./node/', '"./')
    if t != t0: f.write_text(t); print('  пути исправлены:', f)
# onnxruntime ставит путь к wasm через CDN — переставляем на локальный
b = V / 'transformers' / 'transformers.bundle.mjs'
s = b.read_text()
s = s.replace("R.wasm.wasmPaths=`https://cdn.jsdelivr.net/npm/@huggingface/transformers@${z.env.version}/dist/`",
              "R.wasm.wasmPaths=new URL('../ort/',import.meta.url).href")
b.write_text(s)
print('  пути wasm → локальные')
PY
cat > vendor/transformers/transformers.js <<'EOF'
// локальная (офлайн) сборка transformers.js — лежит внутри приложения
export * from './transformers.bundle.mjs';
EOF

echo "3/5 движок ONNX (wasm)"
B="https://cdn.jsdelivr.net/npm/@huggingface/transformers@3.3.3/dist"
curl -sL -o vendor/ort/ort-wasm-simd-threaded.jsep.mjs  "$B/ort-wasm-simd-threaded.jsep.mjs"
curl -sL -o vendor/ort/ort-wasm-simd-threaded.jsep.wasm "$B/ort-wasm-simd-threaded.jsep.wasm"

echo "4/5 модель whisper-tiny_timestamped (44 МБ)"
H="https://huggingface.co/onnx-community/whisper-tiny_timestamped/resolve/main"
for f in config.json generation_config.json preprocessor_config.json tokenizer.json tokenizer_config.json \
         special_tokens_map.json normalizer.json added_tokens.json vocab.json merges.txt quantize_config.json; do
  curl -sL -o "models/whisper-tiny/$f" "$H/$f"
done
curl -sL -o models/whisper-tiny/onnx/encoder_model_quantized.onnx "$H/onnx/encoder_model_quantized.onnx"
curl -sL -o models/whisper-tiny/onnx/decoder_model_merged_quantized.onnx "$H/onnx/decoder_model_merged_quantized.onnx"

echo "5/5 проверка"
python3 - <<'PY'
import pathlib, json
ok = True
for p, check in [('vendor/transformers/transformers.bundle.mjs', None),
                 ('vendor/ort/ort-wasm-simd-threaded.jsep.wasm', b'\x00asm'),
                 ('models/whisper-tiny/onnx/encoder_model_quantized.onnx', None),
                 ('models/whisper-tiny/config.json', None)]:
    f = pathlib.Path(p)
    if not f.exists() or f.stat().st_size < 100: print('  НЕТ:', p); ok = False; continue
    if check:
        head = f.read_bytes()[:4]
        if head != check: print('  БИТЫЙ:', p, head); ok = False; continue
    print(f'  ок: {p} — {f.stat().st_size//1024} КБ')
json.load(open('models/whisper-tiny/config.json'))
print('ИТОГ:', 'всё на месте' if ok else 'чего-то не хватает')
PY
du -sh vendor models
