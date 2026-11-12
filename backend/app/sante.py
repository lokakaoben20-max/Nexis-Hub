"""Santé du backend, lue par la supervision et par Cloud Run.

- vivant (`/health/live`) : le processus répond. Un échec fait redémarrer
  l'instance ;
- prêt (`/health/ready`) : la base répond ET son schéma est à la dernière
  migration du code. Tant que ce n'est pas le cas, l'instance ne reçoit pas
  de trafic : un nouveau code ne sert jamais sur une base pas encore migrée.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

RACINE = Path(__file__).resolve().parents[2]


@lru_cache(maxsize=1)
def revision_attendue() -> str:
    """Dernière migration connue du code (une seule tête, vérifié par la CI)."""
    config = Config(str(RACINE / "alembic.ini"))
    return ScriptDirectory.from_config(config).get_current_head()


def problemes_base(session) -> list[str]:
    try:
        session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return ["base injoignable"]
    try:
        revision = session.execute(text("SELECT version_num FROM alembic_version")).scalar()
    except SQLAlchemyError:
        session.rollback()
        return ["base jamais migrée (alembic upgrade head)"]
    if revision != revision_attendue():
        return ["base pas à la dernière migration (alembic upgrade head)"]
    return []
