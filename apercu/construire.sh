#!/usr/bin/env bash
# Construit l'aperçu publié par Cloudflare (wrangler « build ») :
#   apercu/public/        = la Mini App (mini_app/static), données fictives
#   apercu/public/app/    = l'application mobile Flutter, version web
# Rien de ce dossier n'est versionné : il est refait à chaque publication.
set -euo pipefail

FLUTTER_VERSION="3.47.9"
racine="$(cd "$(dirname "$0")/.." && pwd)"
sortie="$racine/apercu/public"

if ! command -v flutter >/dev/null 2>&1; then
  sdk="${FLUTTER_HOME:-$HOME/.cache/flutter-$FLUTTER_VERSION}"
  if [ ! -x "$sdk/flutter/bin/flutter" ]; then
    echo "Installation de Flutter $FLUTTER_VERSION…"
    mkdir -p "$sdk"
    curl -sSfL "https://storage.googleapis.com/flutter_infra_release/releases/stable/linux/flutter_linux_${FLUTTER_VERSION}-stable.tar.xz" | tar -xJ -C "$sdk"
    git config --global --add safe.directory "$sdk/flutter" || true
  fi
  export PATH="$sdk/flutter/bin:$PATH"
fi
flutter config --no-analytics >/dev/null 2>&1 || true

rm -rf "$sortie"
mkdir -p "$sortie"
cp -R "$racine/mini_app/static/." "$sortie/"

cd "$racine/app_mobile"
flutter pub get
flutter build web --release --base-href /app/ --no-web-resources-cdn --dart-define=NEXIS_APERCU=true
cp -R build/web "$sortie/app"
echo "Aperçu construit dans $sortie"
