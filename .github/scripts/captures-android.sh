#!/usr/bin/env bash
# Captures des écrans principaux de l'app Android (données fictives).
# Lancé par .github/workflows/apps-natives.yml dans l'émulateur.
set -euo pipefail

mkdir -p captures
adb install -r app/build/outputs/apk/debug/app-debug.apk
adb shell settings put system time_12_24 24 || true

shoot() { # nom, apparence (yes = sombre), langue
  adb shell cmd uimode night "$2"
  adb shell am force-stop com.nexishub.app
  adb shell am start -W -n com.nexishub.app/.MainActivity --es capture "$1" --es language "$3" > /dev/null
  sleep 5
  adb exec-out screencap -p > "captures/android-$1-$([ "$2" = yes ] && echo dark || echo light)-$3.png"
}

for screen in welcome phone signup home missions wallet profile services; do
  shoot "$screen" no fr
done
for screen in tracking quotes pay pending confirm report dispute decision provider request job; do
  shoot "$screen" no fr
done
shoot tracking yes fr
shoot home yes fr
shoot home no ln
shoot welcome no en
ls -la captures
