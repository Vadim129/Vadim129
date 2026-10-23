#!/usr/bin/env bash
set -euo pipefail
# The old public APK, NOT its private signing key, is all an upgrade test needs.
git fetch --no-tags origin 63186fe15fedfef705c73d9e6733c5f366b2d9c0
git show 63186fe:payload/mastr-studio.apk > runtime/publish/previous.apk
adb install runtime/publish/previous.apk
adb shell am start -W -S -n app.mastr.studio/.MainActivity
adb install -r payload/mastr-studio.apk
expected=$(sed -n 's/.*versionCode = \([0-9]*\).*/\1/p' mastering-app/app/build.gradle.kts)
adb shell dumpsys package app.mastr.studio | grep "versionCode=$expected "
adb logcat -c
adb shell am start -W -S -n app.mastr.studio/.MainActivity --ez demo true
sleep 4
adb logcat -d -s AndroidRuntime:E > runtime/publish/launch.txt
if grep -q 'Process: app.mastr.studio' runtime/publish/launch.txt; then cat runtime/publish/launch.txt; exit 1; fi
adb exec-out screencap -p > payload/mastr-installed.png
