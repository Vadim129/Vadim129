#!/bin/bash
# Восстановление инструментов разработки в /tmp (они большие и не хранятся в проекте).
# Запуск: bash tools/setup-rigs.sh
set -x
RIG=/var/tmp/rig; mkdir -p $RIG/browser $RIG/libs/deb $RIG/libs/root
cd $RIG/browser && npm init -y >/dev/null 2>&1; npm i puppeteer --no-audit --no-fund 2>&1 | tail -1
cd $RIG/libs/deb && for p in libxdamage1 libasound2t64 libatk1.0-0t64 libatk-bridge2.0-0t64 libatspi2.0-0t64 libcups2t64 libnspr4 libnss3 libxkbcommon0 libavahi-common3 libavahi-client3 libglib2.0-0t64 libdbus-1-3 libsystemd0 liblzma5 libselinux1 libpcre2-8-0 libbsd0 libmd0 libkrb5support0 libkrb5-3 libk5crypto3 libcom-err2 libkeyutils1 libgssapi-krb5-2 libgraphite2-0 libharfbuzz0b libthai0 libdatrie1 libfribidi0 libpixman-1-0 libfontconfig1 libfreetype6 libpng16-16 libbrotli1 libexpat1 libxcb1 libxau6 libxdmcp6 libx11-6 libxext6 libxrender1 libxfixes3 libxi6 libxtst6 libdrm2 libwayland-client0 libwayland-server0 libffi8 libzstd1 libcairo-gobject2 libpangocairo-1.0-0 libpangoft2-1.0-0 libpango-1.0-0 libgdk-pixbuf-2.0-0 libjpeg62-turbo libtiff6 libwebp7 libxshmfence1; do apt-get download $p 2>/dev/null >/dev/null; done
for f in *.deb; do dpkg-deb -x "$f" $RIG/libs/root 2>/dev/null; done; echo LIBS_OK
cd $RIG && curl -sL -o jdk17.tar.gz "https://api.adoptium.net/v3/binary/latest/17/ga/linux/x64/jdk/hotspot/normal/eclipse" && mkdir -p jdk && tar xzf jdk17.tar.gz -C jdk --strip-components=1 && echo JDK_OK
curl -sL -o cmdtools.zip "https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip" && mkdir -p sdk/cmdline-tools && cd sdk/cmdline-tools && unzip -q ../../cmdtools.zip && mv cmdline-tools latest && cd $RIG
yes | $RIG/sdk/cmdline-tools/latest/bin/sdkmanager --sdk_root=$RIG/sdk --licenses >/dev/null 2>&1
$RIG/sdk/cmdline-tools/latest/bin/sdkmanager --sdk_root=$RIG/sdk "platform-tools" "platforms;android-34" "build-tools;34.0.0" >/dev/null 2>&1 && echo SDK_OK
# синтетический тестовый трек и тестовые картинки
python3 - <<'PY'
import wave, math, struct, os
os.makedirs('/tmp/rig/media', exist_ok=True)
w = wave.open('/tmp/rig/media/beat120.wav','w'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(22050)
n = 22050*8; data = bytearray()
for i in range(n):
    t = i/22050
    v = 0.35*math.sin(2*math.pi*220*t) + 0.25*math.sin(2*math.pi*440*t)
    beat = 1.0 if abs((t*2) % 1) < 0.06 else 0.25
    data += struct.pack('<h', int(max(-1,min(1, v*beat))*30000))
w.writeframes(bytes(data)); w.close()
print('beat120.wav готов')
PY
echo RIG_READY
