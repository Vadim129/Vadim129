#!/usr/bin/env bash
# Ten deterministic release checks. Run by CI after every APK build.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APK="${1:-$ROOT/release/RhythmOverlay-v1.1.0.apk}"
SKIN="$ROOT/app/src/main/java/com/vadim129/rhythmoverlay/Skin.java"
VIEW="$ROOT/app/src/main/java/com/vadim129/rhythmoverlay/EqualizerOverlayView.java"
SERVICE="$ROOT/app/src/main/java/com/vadim129/rhythmoverlay/OverlayService.java"
MANIFEST="$ROOT/app/src/main/AndroidManifest.xml"

ok=0
check() {
  ok=$((ok + 1))
  printf '✓ %02d/10  %s\n' "$ok" "$1"
}
fail() {
  printf '✗ %02d/10  %s\n' "$((ok + 1))" "$1" >&2
  exit 1
}

# 1. Required source files are present.
test -f "$SKIN" && test -f "$VIEW" && test -f "$SERVICE" && test -f "$MANIFEST" || fail "Android source layout is incomplete"
check "Android source layout is present"

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

# 5. The package identity is decoded by Android build-tools (not merely a file-name assertion).
AAPT="$(find "${ANDROID_HOME:-/nonexistent}/build-tools" -type f -name aapt 2>/dev/null | sort -V | tail -n 1 || true)"
test -n "$AAPT" && "$AAPT" dump badging "$APK" | grep -F "package: name='com.vadim129.rhythmoverlay'" >/dev/null || fail "Package identity check failed"
check "Android manifest package identity"

# 6. Android's own verifier confirms the debug signature schemes.
APKSIGNER="$(find "${ANDROID_HOME:-/nonexistent}/build-tools" -type f -name apksigner 2>/dev/null | sort -V | tail -n 1 || true)"
test -n "$APKSIGNER" && "$APKSIGNER" verify --verbose "$APK" >/dev/null || fail "APK signature verification failed"
check "APK signature verification"

# 7. The published SHA-256 sidecar agrees with the exact delivered bytes.
SIDE_CAR="${APK}.sha256"
test -f "$SIDE_CAR" || fail "Checksum sidecar is missing"
sidecar_rel="${SIDE_CAR#$ROOT/}"
(
  cd "$ROOT"
  sha256sum -c "$sidecar_rel" >/dev/null
) || fail "Checksum sidecar does not match APK"
check "SHA-256 delivery checksum"

# 8. The catalogue is exactly 100 skins made from 25 motif families, four layouts each.
family_count="$(grep -Ec '^[[:space:]]*add\(skins,' "$SKIN")"
test "$family_count" -eq 25 || fail "Expected 25 motif families, got $family_count"
grep -F 'EXPECTED_SKIN_COUNT = 100' "$SKIN" >/dev/null || fail "Expected skin count constant is not 100"
grep -F 'if (skins.size() != EXPECTED_SKIN_COUNT)' "$SKIN" >/dev/null || fail "Runtime skin-count guard is missing"
check "100-skin catalogue and family-count guard"

# 9. Overlay rendering clears to transparency and never writes a label into the overlay Canvas.
grep -F 'canvas.drawColor(Color.TRANSPARENT, PorterDuff.Mode.CLEAR)' "$VIEW" >/dev/null || fail "Transparent canvas clear is missing"
! grep -F 'drawText(' "$VIEW" >/dev/null || fail "Overlay must not draw text labels"
check "Transparent, label-free overlay renderer"

# 10. All required gestures are wired: drag, pinch resize, and long press → settings.
grep -F 'ScaleGestureDetector' "$VIEW" >/dev/null || fail "Pinch detector is missing"
grep -F 'dragCallback.onResize' "$VIEW" >/dev/null || fail "Resize callback is missing"
grep -F 'postDelayed(longPress' "$VIEW" >/dev/null || fail "Long press scheduling is missing"
grep -F 'dragCallback.onOpenSettings' "$VIEW" >/dev/null || fail "Long press settings callback is missing"
grep -F 'resizeOverlay(scaleFactor)' "$SERVICE" >/dev/null || fail "Service resize handling is missing"
grep -F 'openSettings();' "$SERVICE" >/dev/null || fail "Service settings opening is missing"
check "Drag, pinch-resize and long-press settings gestures"

printf '\nAll 10 release checks passed.\n'
