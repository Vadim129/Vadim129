#!/usr/bin/env bash
set -uo pipefail
adb install -r mastering-app/app/build/outputs/apk/debug/app-debug.apk
gradle --no-daemon -p mastering-app connectedDebugAndroidTest > runtime/mastering/device.log 2>&1
code=$?
export MASTR_DEVICE_EXIT="$code"
adb logcat -d -b all > runtime/mastering/instrument-logcat.txt
adb shell dumpsys meminfo > runtime/mastering/memory.txt
python - <<'PY'
import json,os,re
from pathlib import Path
log=Path('runtime/mastering/device.log').read_text(errors='replace')
details=[]
for f in Path('mastering-app/app/build/outputs/androidTest-results').rglob('*.xml'):
    details.append(f.read_text(errors='replace')[:20000])
lines=Path('runtime/mastering/instrument-logcat.txt').read_text(errors='replace').splitlines()
Path('payload/mastr-instrument-log.txt').write_text('\n'.join([x for x in lines if re.search('mastr|AndroidRuntime|libc|lmkd|lowmemory|OutOfMemory|Fatal|SIG|TestRunner',x,re.I)][-600:]))
Path('payload/mastr-test-xml.txt').write_text('\n'.join(details))
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
