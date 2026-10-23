#!/usr/bin/env bash
set -uo pipefail
mkdir -p runtime/mastering payload
cd "$GITHUB_WORKSPACE"
gradle --no-daemon -p mastering-app testDebugUnitTest assembleDebug assembleRelease > runtime/mastering/build.log 2>&1
code=$?
export MASTR_BUILD_EXIT="$code"
python - <<'PY'
from pathlib import Path
import json,os,hashlib,xml.etree.ElementTree as ET
log=Path('runtime/mastering/build.log').read_text(errors='replace')
apk=Path('mastering-app/app/build/outputs/apk/release/app-release.apk')
reports=[ET.parse(f).getroot() for f in Path('mastering-app/app/build/test-results/testDebugUnitTest').glob('*.xml')]
result={'run_id':os.environ['GITHUB_RUN_ID'],'exit_code':int(os.environ['MASTR_BUILD_EXIT']),'unit_tests':sum(int(r.get('tests','0')) for r in reports),'unit_failures':sum(int(r.get('failures','0')) for r in reports),'apk_size':apk.stat().st_size if apk.exists() else 0,'apk_sha256':hashlib.sha256(apk.read_bytes()).hexdigest() if apk.exists() else None,'log_tail':log[-18000:]}
Path('payload/mastr-build.json').write_text(json.dumps(result,indent=2)+'\n')
print('Gradle build exit:',os.environ['MASTR_BUILD_EXIT'])
PY
if [ "$code" -eq 0 ]; then
  cp mastering-app/app/build/outputs/apk/release/app-release.apk payload/mastr-studio.apk
fi
exit "$code"
