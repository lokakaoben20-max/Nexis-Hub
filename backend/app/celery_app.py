import os

from celery import Celery
from celery.schedules import crontab
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery("nexis_hub", broker=REDIS_URL, backend=REDIS_URL)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
)

# Phase 2 du plan de migration (V5_MIGRATION_PLAN.md) : seules les 4 tâches
# explicitement identifiées y sont portées, aux fréquences déjà documentées
# dans le fichier source (nexis-hub-v5/backend/app/celery_app.py).
celery_app.conf.beat_schedule = {
    "send-provider-reminders": {
        "task": "backend.app.tasks.send_provider_reminders",
        "schedule": crontab(minute="*/10"),
    },
    "check-expired-quotes": {
        "task": "backend.app.tasks.check_expired_quotes",
        "schedule": crontab(minute=0),
    },
    "release-auto-confirmed-missions": {
        "task": "backend.app.tasks.release_auto_confirmed_missions",
        "schedule": crontab(minute=0),
    },
    "send-daily-analytics": {
        "task": "backend.app.tasks.send_daily_analytics",
        "schedule": crontab(hour=8, minute=0),
    },
}

# Importé en dernier pour enregistrer les tâches sur cette instance Celery
# sans créer d'import circulaire (tasks.py importe `celery_app` depuis ce
# module pour le décorateur `@celery_app.task`).
from backend.app import tasks  # noqa: F401,E402
