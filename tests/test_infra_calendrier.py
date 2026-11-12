"""Le calendrier lu par Terraform (infra/calendrier.json, Cloud Scheduler) est
la copie de CALENDRIER dans backend/app/taches.py. Ce test échoue dès qu'une
des deux change sans l'autre : une tâche qui n'est pas planifiée ne tourne
jamais en production, sans aucune erreur visible."""

import json
from pathlib import Path

from backend.app.taches import CALENDRIER

CALENDRIER_TERRAFORM = Path(__file__).resolve().parents[1] / "infra" / "calendrier.json"


def test_terraform_schedules_exactly_the_code_calendar():
    attendu = {nom: tache.frequence.cron for nom, tache in CALENDRIER.items()}

    assert json.loads(CALENDRIER_TERRAFORM.read_text(encoding="utf-8")) == attendu
