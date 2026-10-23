#!/usr/bin/env bash
set -uo pipefail
adb install -r mastering-app/app/build/outputs/apk/debug/app-debug.apk
adb shell run-as app.mastr.studio mkdir -p files
adb shell -T "run-as app.mastr.studio sh -c 'cat > files/UVR_MDXNET_Main.onnx'" < runtime/mastering/UVR_MDXNET_Main.onnx
adb shell run-as app.mastr.studio ls -l files
gradle --no-daemon -p mastering-app connectedDebugAndroidTest > runtime/mastering/device.log 2>&1
code=$?
export MASTR_DEVICE_EXIT="$code"
python - <<'PY'
import json,os
from pathlib import Path
log=Path('runtime/mastering/device.log').read_text(errors='replace')
Path('payload/mastr-device.json').write_text(json.dumps({'exit_code':int(os.environ['MASTR_DEVICE_EXIT']),'log_tail':log[-18000:]},indent=2)+'\n')
PY
adb install -r mastering-app/app/build/outputs/apk/release/app-release.apk
adb logcat -c
adb shell am start -W -S -n app.mastr.studio/.MainActivity --ez demo true
sleep 4
adb exec-out screencap -p > payload/mastr-screen.png
adb logcat -d -s AndroidRuntime:E > payload/mastr-release-log.txt
if grep -q 'Process: app.mastr.studio' payload/mastr-release-log.txt; then code=1; fi
exit "$code"
