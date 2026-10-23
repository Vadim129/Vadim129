#!/usr/bin/env bash
set -uo pipefail
mkdir -p runtime/mastering payload
cd "$GITHUB_WORKSPACE"
gradle --no-daemon -p mastering-app testDebugUnitTest assembleDebug assembleRelease > runtime/mastering/build.log 2>&1
code=$?
export MASTR_BUILD_EXIT="$code"
python - <<'PY'
from pathlib import Path
import json,os
log=Path('runtime/mastering/build.log').read_text(errors='replace')
Path('payload/mastr-build.json').write_text(json.dumps({'run_id':os.environ['GITHUB_RUN_ID'],'exit_code':int(os.environ['MASTR_BUILD_EXIT']),'log_tail':log[-18000:]},indent=2)+'\n')
print('Gradle build exit:',os.environ['MASTR_BUILD_EXIT'])
PY
if [ "$code" -eq 0 ]; then
  cp mastering-app/app/build/outputs/apk/release/app-release.apk payload/mastr-studio.apk
fi
exit "$code"
