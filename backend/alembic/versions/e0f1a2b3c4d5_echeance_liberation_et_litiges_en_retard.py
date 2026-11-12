"""Échéance de libération automatique et alerte des litiges en retard

Le délai pour signaler un problème passe de 24 h à 48 h (décision du
2026-11-07). L'échéance est désormais enregistrée sur la mission
(`release_after`) quand le prestataire déclare la mission terminée, au lieu
d'être recalculée depuis une constante : une mission garde la règle qui
était en vigueur quand le client a été prévenu.

Les missions déjà en attente de confirmation au moment de la migration
reçoivent l'échéance de l'ancienne règle (fin + 24 h). Les autres n'en ont
pas besoin : l'échéance ne sert qu'en `awaiting_confirmation`.

`dispute_overdue_alerted_at` note la dernière alerte admin pour un litige
sans décision après le délai de réponse de 48 h.

Revision ID: e0f1a2b3c4d5
Revises: d9e0f1a2b3c4
Create Date: 2026-11-12
"""
from datetime import timedelta
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "e0f1a2b3c4d5"
down_revision: Union[str, Sequence[str], None] = "d9e0f1a2b3c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Règle en vigueur avant cette migration, pour les missions déjà terminées.
PREVIOUS_AUTO_RELEASE_DELAY = timedelta(hours=24)


def upgrade() -> None:
    with op.batch_alter_table("bot_missions") as batch:
        batch.add_column(sa.Column("release_after", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("dispute_overdue_alerted_at", sa.DateTime(), nullable=True))
    op.create_index(op.f("ix_bot_missions_release_after"), "bot_missions", ["release_after"], unique=False)

    missions = sa.table(
        "bot_missions",
        sa.column("mission_id", sa.Integer()),
        sa.column("status", sa.String()),
        sa.column("status_changed_at", sa.DateTime()),
        sa.column("release_after", sa.DateTime()),
    )
    bind = op.get_bind()
    waiting = bind.execute(
        sa.select(missions.c.mission_id, missions.c.status_changed_at).where(
            missions.c.status == "awaiting_confirmation"
        )
    ).all()
    for mission_id, status_changed_at in waiting:
        bind.execute(
            missions.update()
            .where(missions.c.mission_id == mission_id)
            .values(release_after=status_changed_at + PREVIOUS_AUTO_RELEASE_DELAY)
        )


def downgrade() -> None:
    op.drop_index(op.f("ix_bot_missions_release_after"), table_name="bot_missions")
    with op.batch_alter_table("bot_missions") as batch:
        batch.drop_column("dispute_overdue_alerted_at")
        batch.drop_column("release_after")
