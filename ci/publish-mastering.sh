#!/usr/bin/env bash
# Only a permanently signed, tested APK is eligible. No private key goes to CI.
set -euo pipefail
python - <<'PY'
import hashlib,json,re,subprocess
from pathlib import Path
apk=Path('payload/mastr-studio.apk')
report=json.loads(Path('payload/mastr-signature.json').read_text())
expected=json.loads(Path('mastering-app/signing-certificate.json').read_text())['certificate_sha256']
assert hashlib.sha256(apk.read_bytes()).hexdigest()==report['apk_sha256']
assert report['certificate_sha256']==expected and report['unchanged_app_contents']
tool=Path('payload/android-apksigner.jar')
assert hashlib.sha256(tool.read_bytes()).hexdigest()==Path('payload/android-apksigner-sha256.txt').read_text().split()[0]
text=subprocess.check_output(['java','-jar',str(tool),'verify','--verbose','--print-certs',str(apk)],text=True)
assert set(re.findall(r'certificate SHA-256 digest: ([0-9a-f]+)',text))=={expected}
status=json.loads(Path('payload/mastr-status.json').read_text())
assert status['build']=='success' and status['device_tests']=='success'
source=Path('mastering-app/app/build.gradle.kts').read_text()
version=re.search(r'versionName = "([0-9]+\.[0-9]+\.[0-9]+)"',source).group(1)
name=f'MASTR-Studio-{version}.apk'
Path('runtime/publish').mkdir(parents=True,exist_ok=True)
Path('runtime/publish',name).write_bytes(apk.read_bytes())
Path('runtime/publish',name+'.sha256').write_text(f'{report["apk_sha256"]}  {name}\n')
Path('runtime/publish/version').write_text(version)
print('Verified permanent certificate, build tests and SHA-256; version',version)
PY
