# One permanent APK signing identity

The user's request is a **stable cryptographic signature**, NOT a visual author
signature. Do not add branding, regenerate a key per build, or ship CI debug keys.

## Pinned certificate

SHA-256:
`815ac7c1f9b6967fb51406c947d8cc8e1ef28d34fafa02d8c1e6c42e483b6933`

Alias `mastr-studio`, RSA 3072. Public PEM and metadata are tracked here.
The private key is **not** in Git. It is in the ignored `.signing/` directory,
with an owner-only private backup on the user's Drive, separate from the APK folder.
The backup is named `MASTR Studio — ЗАКРЫТЫЙ постоянный ключ подписи.zip`.
Its location is recorded privately in `.signing/backup-location.json`.
Never publish/share that archive: it includes both the keystore and its password.

## Every future delivery

1. Build/test the updated code in CI. CI must opt into
   `MASTR_ALLOW_TEMPORARY_SIGNING=true` only for emulator testing. This artifact
   is `payload/mastr-studio-ci.apk`, **not a deliverable**.
2. Reuse the existing `.signing/mastr-studio.p12` and `.signing/signing.json`.
   If absent, restore them from the user's private backup. **Fail rather than
   generating a different key.** Never put key/password in Git, logs, or chat.
3. Install local tooling if needed (`python -m venv .venv`, then
   `.venv/bin/pip install jdk4py cryptography`). The official Android SDK
   `apksigner.jar` and its pinned checksum are in `payload/`, retrieved by CI.
4. Run `.venv/bin/python ci/sign-mastering.py` from the repository root.
   This signs to `payload/mastr-studio.apk` and verifies the pinned certificate,
   v2/v3 signatures and unchanged code/resources. The script NEVER creates keys.
5. Check `payload/mastr-signature.json`, upload **that signed APK**, not the CI
   one. Increase Android versionCode for actual functional updates.

Local direct Gradle release builds can instead receive `MASTR_KEYSTORE_PATH` and
`MASTR_KEYSTORE_PASSWORD` as private environment variables; alias is fixed.
Without private key or explicit CI test opt-in, release packaging fails closed.
The final delivery must still be verified against the pinned certificate.

## First transition only

The earlier 1.0.0 APK used a discarded temporary Android Debug certificate:
`59c95b9aebfdbde508a627a5f2c1761f6a5acae32757240484a147a4b37d3a38`.
Its private key is not available. The new permanent-key APK cannot update over
that old install. Export any unsaved work, uninstall the old APK and install the
new one once. Subsequent versions reuse this permanent key and can update in place.

This change re-signs the existing tested APK, leaving its manifest, code,
resources, version and functionality unchanged. No author inscription was added.
