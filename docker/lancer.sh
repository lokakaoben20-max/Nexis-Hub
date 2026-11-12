#!/bin/sh
# Point d'entrée de l'image : un rôle par processus (voir Dockerfile).
# `exec` : le processus Python reçoit lui-même les signaux d'arrêt (SIGTERM
# au déploiement) et s'arrête proprement.
set -eu

role="${1:-}"
[ $# -gt 0 ] && shift
# Port donné par la plateforme (Cloud Run : PORT), sinon le port local habituel.
case "$role" in
  backend)
    exec uvicorn backend.app.main:app --host 0.0.0.0 --port "${PORT:-8000}" \
      --proxy-headers --no-server-header --timeout-graceful-shutdown 8 ;;
  miniapp)
    exec uvicorn mini_app.app:app --host 0.0.0.0 --port "${PORT:-8001}" \
      --proxy-headers --no-server-header --timeout-graceful-shutdown 8 ;;
  bot)
    export BOT_RUN_MODE=webhook WEBHOOK_LISTEN_HOST=0.0.0.0 WEBHOOK_LISTEN_PORT="${PORT:-8002}"
    exec python main.py ;;
  webhook-setup)
    exec python -m telegram_bot.webhook_setup ;;
  migration)
    exec alembic upgrade head ;;
  tache)
    exec python -m backend.app.taches lancer "$@" ;;
  planificateur)
    exec python -m backend.app.taches planificateur ;;
  calendrier)
    exec python -m backend.app.taches calendrier ;;
  controle-registre)
    exec python -m backend.app.controle_registre "$@" ;;
  *)
    echo "rôle inconnu : '$role' (backend, miniapp, bot, webhook-setup, migration, tache <nom>, planificateur, calendrier, controle-registre)" >&2
    exit 64 ;;
esac
