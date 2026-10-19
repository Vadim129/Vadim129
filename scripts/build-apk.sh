#!/usr/bin/env bash
# Builds a signed, installable debug APK without Gradle/Android Studio.
# Downloads are intentionally restricted to GitHub and npm (the Arena build environment's allowed hosts).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOOLS="$ROOT/.tools/android-build"
BUILD="$ROOT/.apk-build"
RELEASE="$ROOT/release"
JDK="$TOOLS/jdk"
ANDROID_JAR="$TOOLS/android-35.jar"
AAPT2="$TOOLS/aapt2"
D8="$TOOLS/d8.jar"
SIGNER="$TOOLS/uber-apk-signer.jar"

mkdir -p "$TOOLS/downloads" "$BUILD" "$RELEASE"

note() { printf '\n\033[1;36m› %s\033[0m\n' "$*"; }

if [[ ! -x "$JDK/bin/java" ]]; then
  note "Downloading Temurin JDK 17"
  archive="$TOOLS/downloads/OpenJDK17U-jdk_x64_linux_hotspot_17.0.20.1_1.tar.gz"
  if [[ ! -f "$archive" ]]; then
    curl --fail --location --retry 3 --retry-delay 2 \
      -o "$archive" \
      'https://github.com/adoptium/temurin17-binaries/releases/download/jdk-17.0.20.1%2B1/OpenJDK17U-jdk_x64_linux_hotspot_17.0.20.1_1.tar.gz'
  fi
  rm -rf "$JDK" "$TOOLS"/jdk-17.0.20.1+1
  tar -xzf "$archive" -C "$TOOLS"
  extracted="$(find "$TOOLS" -maxdepth 1 -type d -name 'jdk-17*' | head -n 1)"
  mv "$extracted" "$JDK"
fi

if [[ ! -f "$ANDROID_JAR" ]]; then
  note "Fetching Android API 35 stubs from a GitHub sparse checkout"
  platform_repo="$TOOLS/android-platforms"
  rm -rf "$platform_repo"
  GIT_TERMINAL_PROMPT=0 git clone --depth 1 --filter=blob:none --sparse \
    https://github.com/Sable/android-platforms.git "$platform_repo"
  git -C "$platform_repo" sparse-checkout set android-35
  cp "$platform_repo/android-35/android.jar" "$ANDROID_JAR"
  rm -rf "$platform_repo"
fi

if [[ ! -x "$AAPT2" || ! -f "$D8" ]]; then
  note "Fetching aapt2 and D8 from npm packages"
  package_dir="$TOOLS/npm-unpack"
  rm -rf "$package_dir"
  mkdir -p "$package_dir"
  (
    cd "$TOOLS/downloads"
    npm pack aaptjs3@2.0.2 d8-termux@1.0.0 >/dev/null
  )
  aapt_archive="$(find "$TOOLS/downloads" -maxdepth 1 -name 'aaptjs3-*.tgz' | sort | tail -n 1)"
  d8_archive="$(find "$TOOLS/downloads" -maxdepth 1 -name 'd8-termux-*.tgz' | sort | tail -n 1)"
  mkdir -p "$package_dir/aapt" "$package_dir/d8"
  tar -xzf "$aapt_archive" -C "$package_dir/aapt"
  tar -xzf "$d8_archive" -C "$package_dir/d8"
  cp "$package_dir/aapt/package/bin/x64/linux/aapt2" "$AAPT2"
  chmod +x "$AAPT2"
  cp "$package_dir/d8/package/d8.jar" "$D8"
  rm -rf "$package_dir"
fi

if [[ ! -f "$SIGNER" ]]; then
  note "Fetching Uber APK Signer"
  curl --fail --location --retry 3 --retry-delay 2 \
    -o "$SIGNER" \
    'https://github.com/patrickfav/uber-apk-signer/releases/download/v1.3.0/uber-apk-signer-1.3.0.jar'
fi

JAVA="$JDK/bin/java"
JAVAC="$JDK/bin/javac"

note "Compiling Java sources"
rm -rf "$BUILD"
mkdir -p "$BUILD/classes" "$BUILD/dex" "$BUILD/generated"
mapfile -t sources < <(find "$ROOT/app/src/main/java" -name '*.java' -print | sort)
"$JAVAC" --release 8 -encoding UTF-8 -classpath "$ANDROID_JAR" -d "$BUILD/classes" "${sources[@]}"

note "Packaging resources"
"$AAPT2" compile --dir "$ROOT/app/src/main/res" -o "$BUILD/resources.zip"
"$AAPT2" link \
  -I "$ANDROID_JAR" \
  --manifest "$ROOT/app/src/main/AndroidManifest.xml" \
  --min-sdk-version 26 \
  --target-sdk-version 35 \
  --version-code 1 \
  --version-name 1.0.0 \
  --auto-add-overlay \
  -R "$BUILD/resources.zip" \
  --java "$BUILD/generated" \
  -o "$BUILD/unsigned.apk"

note "Converting bytecode to DEX"
mapfile -t classes < <(find "$BUILD/classes" -name '*.class' -print | sort)
"$JAVA" -cp "$D8" com.android.tools.r8.D8 \
  --min-api 26 \
  --lib "$ANDROID_JAR" \
  --output "$BUILD/dex" \
  "${classes[@]}"
(
  cd "$BUILD/dex"
  zip -q "$BUILD/unsigned.apk" classes.dex
)

note "Signing and zip-aligning the APK"
rm -f "$RELEASE"/*.apk "$RELEASE"/*.sha256
"$JAVA" -jar "$SIGNER" --apks "$BUILD/unsigned.apk" --out "$RELEASE" --overwrite >/dev/null
signed="$(find "$RELEASE" -maxdepth 1 -name '*-aligned-*.apk' -o -name '*signed*.apk' | head -n 1)"
if [[ -z "$signed" || ! -f "$signed" ]]; then
  echo "APK signer did not emit an APK" >&2
  exit 1
fi
final="$RELEASE/RhythmOverlay-v1.0.1.apk"
mv -f "$signed" "$final"
sha256sum "$final" | tee "$RELEASE/RhythmOverlay-v1.0.1.apk.sha256"
"$AAPT2" dump badging "$final" | sed -n '1,2p'
unzip -tq "$final" >/dev/null
echo
printf 'Ready: %s\n' "$final"
