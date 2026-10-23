#!/usr/bin/env bash
# Run inference without exposing the source recording or plaintext outputs.
set -uo pipefail
cd "$GITHUB_WORKSPACE/runtime/ace-step"
export PYTHONPATH="$GITHUB_WORKSPACE/runtime/ace-step"
mkdir -p "$GITHUB_WORKSPACE/runtime/result"
python "$GITHUB_WORKSPACE/music/ai_cover_runner.py" \
  --source "$GITHUB_WORKSPACE/runtime/audio/source.wav" \
  --output "$GITHUB_WORKSPACE/runtime/result" --mode "$MUSIC_MODE" \
  > "$GITHUB_WORKSPACE/runtime/inference.log" 2>&1
code=$?
export AI_EXIT_CODE="$code"
python - <<'PY'
import json,os
from pathlib import Path
root=Path(os.environ['GITHUB_WORKSPACE'])
log=(root/'runtime/inference.log').read_text(errors='replace')
status={'exit_code':int(os.environ['AI_EXIT_CODE']), 'run_id':os.environ['GITHUB_RUN_ID'],
        'diagnostic_tail':log[-14000:]}
(root/'runtime/result/status.json').write_text(json.dumps(status,indent=2)+'\n')
print('Inference process finished; encrypted diagnostics prepared.')
PY
exit "$code"
