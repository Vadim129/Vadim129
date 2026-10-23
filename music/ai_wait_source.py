"""Wait for a source encrypted specifically to this temporary worker.

The sandbox downloads the worker's public-key artifact, encrypts the input,
and pushes ciphertext to the SAME working branch. No audio is logged.
"""
import os
from pathlib import Path
import subprocess
import time

from ai_artifacts import unseal

root=Path(__file__).resolve().parents[1]
key=(root/'runtime/worker_private.key').read_bytes()
output=root/'runtime/audio/source.mp3'
output.parent.mkdir(parents=True,exist_ok=True)
branch=os.environ['GITHUB_REF_NAME']
if branch!='arena/ebbb08ec-vadim129':
    raise SystemExit('Refusing to fetch audio on an unrelated branch')
print('Waiting for authenticated encrypted input; no public audio link required.',flush=True)
for _ in range(90):
    fetched=subprocess.run(['git','fetch','--quiet','origin',branch],cwd=root,capture_output=True)
    if fetched.returncode==0:
        blob=subprocess.run(['git','show','FETCH_HEAD:music/ai_input.encrypted'],cwd=root,capture_output=True)
        if blob.returncode==0:
            try:
                source=unseal(blob.stdout,key)
            except Exception:
                # Another invocation's ciphertext is intentionally undecryptable.
                pass
            else:
                if len(source)<1024:
                    raise SystemExit('Decrypted input is unexpectedly small')
                output.write_bytes(source)
                print('Encrypted input authenticated and received.',flush=True)
                break
    time.sleep(10)
else:
    raise SystemExit('Timed out waiting for this worker\'s encrypted source')
subprocess.run(['ffmpeg','-y','-v','error','-i',str(output),'-c:a','pcm_s24le',str(output.with_suffix('.wav'))],check=True)
