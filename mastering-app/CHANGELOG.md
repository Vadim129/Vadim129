# MASTR Studio

## 1.1.0 · versionCode 3
- Automatic per-track settings and full preset strength; no intensity or manual mastering sliders.
- Target cannot be below source LUFS. Measure and correct loudness after limiting (up to ten passes).
- WAV export writes the measured PCM without another limiter. A safety warning appears if an extreme source cannot reach its input level safely.
- Remove UVR/ONNX, separation, model downloads and the ONNX native runtime. Delete previously installed model/stem cache during migration.
- One universal “Открыть аудиофайл” import action, including mislabelled WAVs.
- Atomic export directly to Downloads (Android 10+ MediaStore, legacy permission on Android 8/9).
- GitHub MASTR release checks weekly on app foreground and manually from About/Library. Explicit opt-in APK downloads; no silent installation.
- Procedural aurora background, refreshed cards, persistent A/B controls and before/after loudness readings.
- Same permanent signing certificate as 1.0.1.

## 1.0.1
- Canonical audio/x-wav exports and universal import option.
