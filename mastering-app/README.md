# MASTR Studio 1.1.0

Local Android mastering (Kotlin/Compose, Android 8+). Audio stays on-device.
32 tonal presets, automatic per-track settings, source/master A/B, WAV 16/24 and AAC.
No neural network, ONNX library, model downloader or stem separation.

## Loudness

Settings default to full strength. On import, input loudness, crest and bass energy
select conservative dynamics settings. The target is `max(input LUFS, preset target)`.
After processing, a measured post-limiter feedback loop corrects level (up to 10
passes, tolerance 0.08 LU). Safety ceiling takes precedence for pathological inputs;
the UI explicitly warns when the result is >0.2 LU quieter than the input. WAV export
writes exactly this measured PCM, with only format quantization, and never limits again.
AAC is lossy and codec peaks/level can differ. Sample peaks are not true-peak meters.
These heuristics do not claim a perceptually optimal result for every song.

## Files

Single GET_CONTENT */* chooser (“Открыть аудиофайл”), no all-files access.
Android 10+: publish completed files to MediaStore Downloads with correct MIME,
IS_PENDING and failure cleanup. Android 8/9: request WRITE_EXTERNAL_STORAGE once,
write a unique Downloads filename and scan it. Never overwrite an existing export.
Up to 5 minutes/250 MB per import remain memory safety limits.

## GitHub updates

Repository: Vadim129/Vadim129. Stable releases tagged `mastr-vX.Y.Z`, exact asset
`MASTR-Studio-X.Y.Z.apk`. Other applications' tags, drafts, prereleases, HTTP and
unexpected asset URLs are ignored. Only numeric semver newer than VERSION_NAME
is offered. Check when foregrounded, at most once per seven days (including failed
attempts to avoid repeated network use). Manual checks bypass the interval.
Requests have timeouts and bounded responses. Checks send no audio or identifiers.
User-approved downloads use Android DownloadManager into Downloads; installation
is confirmed by the user through Android and must match the existing signing cert.

Publish every future update using the same permanent key and higher versionCode.
Never publish CI/debug-signed APKs. See SIGNING.md. For publishing:
`gh release create mastr-vX.Y.Z MASTR-Studio-X.Y.Z.apk --target arena/ebbb08ec-vadim129 ...`
(The application scans MASTR releases, not the repository's unrelated latest release.)

## Tests

`gradle -p mastering-app testDebugUnitTest assembleDebug assembleRelease`
`gradle -p mastering-app connectedDebugAndroidTest`
CI: DSP loudness/peak regressions for all presets, codec round trips, universal import,
actual Downloads publication/readback, update parser/schedule, and Compose UI flows.
No neural model is fetched or staged in CI. Release builds are separately smoke-tested.
