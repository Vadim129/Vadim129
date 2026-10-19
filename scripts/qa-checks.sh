#!/usr/bin/env bash
# Ten deterministic release checks. Run by CI after every APK build.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APK="${1:-$ROOT/release/RhythmOverlay-v1.2.0.apk}"
SKIN="$ROOT/app/src/main/java/com/vadim129/rhythmoverlay/Skin.java"
VIEW="$ROOT/app/src/main/java/com/vadim129/rhythmoverlay/EqualizerOverlayView.java"
SERVICE="$ROOT/app/src/main/java/com/vadim129/rhythmoverlay/OverlayService.java"
DANCER="$ROOT/app/src/main/java/com/vadim129/rhythmoverlay/DancerSprite.java"
GRADLE="$ROOT/app/build.gradle"
MANIFEST="$ROOT/app/src/main/AndroidManifest.xml"
KEYSTORE="$ROOT/app/signing/rhythm-overlay.keystore"
ASSETS="$ROOT/app/src/main/assets/dancers"

ok=0
check() {
  ok=$((ok + 1))
  printf '✓ %02d/10  %s\n' "$ok" "$1"
}
fail() {
  printf '✗ %02d/10  %s\n' "$((ok + 1))" "$1" >&2
  exit 1
}

# 1. Required source files and the transparent dance-frame assets are present.
test -f "$SKIN" && test -f "$VIEW" && test -f "$SERVICE" && test -f "$DANCER" && test -f "$GRADLE" && test -f "$MANIFEST" || fail "Android source layout is incomplete"
test "$(find "$ASSETS" -type f -name 'frame_*.png' | wc -l | tr -d ' ')" -eq 60 || fail "Expected 60 transparent dance frames"
check "Source layout and 60 dancer frames are present"

# 2. The requested output exists and is nonempty.
test -s "$APK" || fail "APK was not produced: $APK"
check "APK output exists"

# 3. A malformed ZIP/APK is rejected before delivery.
unzip -tq "$APK" >/dev/null || fail "APK archive integrity failed"
check "APK archive integrity"

# 4. The archive has the fundamental Android payload.
for entry in AndroidManifest.xml resources.arsc; do
  unzip -l "$APK" | awk '{print $4}' | grep -Fx "$entry" >/dev/null || fail "Missing $entry"
done
unzip -l "$APK" | awk '{print $4}' | grep -E '^classes[0-9]*\.dex$' >/dev/null || fail "Missing DEX payload"
check "Manifest, resources and DEX payload are packaged"

# 5. The package identity and delivery version are decoded by Android build-tools.
AAPT="$(find "${ANDROID_HOME:-/nonexistent}/build-tools" -type f -name aapt 2>/dev/null | sort -V | tail -n 1 || true)"
test -n "$AAPT" || fail "aapt was not found"
BADGING="$($AAPT dump badging "$APK")"
printf '%s\n' "$BADGING" | grep -F "package: name='com.vadim129.rhythmoverlay' versionCode='4' versionName='1.2.0'" >/dev/null || fail "Package identity/version check failed"
check "Fixed package identity and v1.2.0 version"

# 6. APK signature is valid and uses the persistent keystore rather than a transient runner debug key.
APKSIGNER="$(find "${ANDROID_HOME:-/nonexistent}/build-tools" -type f -name apksigner 2>/dev/null | sort -V | tail -n 1 || true)"
test -n "$APKSIGNER" && test -s "$KEYSTORE" || fail "Persistent signing identity is missing"
"$APKSIGNER" verify --verbose "$APK" >/dev/null || fail "APK signature verification failed"
key_fingerprint="$(keytool -list -v -keystore "$KEYSTORE" -storepass rhythm-overlay-persistent-2026 -alias rhythm-overlay 2>/dev/null | awk -F': ' '/SHA256:/{gsub(":", "", $2); print $2; exit}')"
apk_fingerprint="$("$APKSIGNER" verify --print-certs "$APK" 2>/dev/null | awk -F': ' '/certificate SHA-256 digest:/{gsub(":", "", $2); print $2; exit}')"
test -n "$key_fingerprint" && test "$key_fingerprint" = "$apk_fingerprint" || fail "APK was not signed by the persistent keystore"
grep -F "signingConfig signingConfigs.persistent" "$GRADLE" >/dev/null || fail "Persistent signing config is not assigned"
check "Persistent APK signature matches the committed identity"

# 7. The published SHA-256 sidecar agrees with the exact delivered bytes.
SIDE_CAR="${APK}.sha256"
test -f "$SIDE_CAR" || fail "Checksum sidecar is missing"
sidecar_rel="${SIDE_CAR#$ROOT/}"
(
  cd "$ROOT"
  sha256sum -c "$sidecar_rel" >/dev/null
) || fail "Checksum sidecar does not match APK"
check "SHA-256 delivery checksum"

# 8. The rejected motif catalogue is replaced with 10 real visualizer formats × 10 presets.
family_count="$(grep -Ec '^[[:space:]]*add\(skins,' "$SKIN")"
test "$family_count" -eq 10 || fail "Expected 10 visualizer families, got $family_count"
grep -F 'EXPECTED_SKIN_COUNT = 100' "$SKIN" >/dev/null || fail "Expected visualizer count constant is not 100"
grep -F 'PRESETS_PER_FAMILY = 10' "$SKIN" >/dev/null || fail "Expected 10 presets per family"
grep -F 'case Skin.CIRCULAR' "$VIEW" >/dev/null || fail "Circular spectrum renderer is missing"
grep -F 'case Skin.WAVE' "$VIEW" >/dev/null || fail "Waveform renderer is missing"
grep -F 'case Skin.TUNNEL' "$VIEW" >/dev/null || fail "Tunnel renderer is missing"
! grep -Eiq 'cards|rubies|sapphires|gems|stones|animals' "$SKIN" || fail "Rejected thematic motif catalogue leaked into Skin.java"
check "100 normal visualizer presets across 10 distinct formats"

# 9. Overlay is transparent, label-free, audio-reactive, and advances dance frames from beat energy.
grep -F 'canvas.drawColor(Color.TRANSPARENT, PorterDuff.Mode.CLEAR)' "$VIEW" >/dev/null || fail "Transparent canvas clear is missing"
! grep -F 'drawText(' "$VIEW" >/dev/null || fail "Overlay must not draw text labels"
grep -F 'AudioLevels.snapshot()' "$VIEW" >/dev/null || fail "Audio level feed is missing"
grep -F 'DancerSprite.frame' "$VIEW" >/dev/null || fail "User dancer frame renderer is missing"
grep -F 'danceFrame = (danceFrame +' "$VIEW" >/dev/null || fail "Beat-driven dancer frame advance is missing"
check "Transparent audio-reactive renderer and beat-synced dancers"

# 10. Drag, pinch resize, long-hold settings, and the visible close action are wired.
grep -F 'ScaleGestureDetector' "$VIEW" >/dev/null || fail "Pinch detector is missing"
grep -F 'dragCallback.onResize' "$VIEW" >/dev/null || fail "Resize callback is missing"
grep -F 'postDelayed(longPress' "$VIEW" >/dev/null || fail "Long-hold scheduling is missing"
grep -F 'drawEditControls' "$VIEW" >/dev/null || fail "Long-hold controls renderer is missing"
grep -F 'dragCallback.onClose()' "$VIEW" >/dev/null || fail "Visible close action is missing"
grep -F 'dragCallback.onOpenSettings()' "$VIEW" >/dev/null || fail "Settings action is missing"
grep -F 'stopOverlay();' "$SERVICE" >/dev/null || fail "Service close handling is missing"
grep -F 'resizeOverlay(scaleFactor)' "$SERVICE" >/dev/null || fail "Service resize handling is missing"
check "Drag, pinch, long-hold settings and close gestures"

printf '\nAll 10 release checks passed.\n'
