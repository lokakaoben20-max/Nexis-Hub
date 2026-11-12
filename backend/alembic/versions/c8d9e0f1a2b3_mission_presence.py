"""Arrivée confirmée du prestataire

- `mission_presence` : une ligne par mission, créée au premier événement
  d'arrivée. Présence confirmée par l'appui du client ou par le code de
  présence du client tapé par le prestataire (`confirmed_by`), cinq mauvais
  codes au plus (`failed_code_attempts`, `code_locked_at`), signalement
  « ce n'est pas lui » (`wrong_person_reported_at`, qui ouvre un litige).

Le code de présence n'est jamais enregistré : il est recalculé par le backend
(backend.app.presence.presence_code). Aucune table d'argent n'est touchée.

Conception : localisation/confirmation-arrivee-et-devis-sur-place-2026-11-08.md.

Revision ID: c8d9e0f1a2b3
Revises: b7c8d9e0f1a2
Create Date: 2026-11-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c8d9e0f1a2b3"
down_revision: Union[str, Sequence[str], None] = "b7c8d9e0f1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "mission_presence",
        sa.Column("mission_id", sa.Integer(), sa.ForeignKey("bot_missions.mission_id"), primary_key=True),
        sa.Column("arrival_declared_at", sa.DateTime(), nullable=True),
        sa.Column("client_asked_at", sa.DateTime(), nullable=True),
        sa.Column("not_yet_at", sa.DateTime(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
        sa.Column("confirmed_by", sa.String(length=20), nullable=True),
        sa.Column("failed_code_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("code_locked_at", sa.DateTime(), nullable=True),
        sa.Column("wrong_person_reported_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "confirmed_by IS NULL OR confirmed_by IN ('client', 'presence_code')", name="ck_mission_presence_confirmed_by"
        ),
        sa.CheckConstraint(
            "(confirmed_at IS NULL AND confirmed_by IS NULL) OR (confirmed_at IS NOT NULL AND confirmed_by IS NOT NULL)",
            name="ck_mission_presence_confirmation_complete",
        ),
        sa.CheckConstraint("failed_code_attempts >= 0 AND failed_code_attempts <= 5", name="ck_mission_presence_attempts"),
        sa.CheckConstraint(
            "(code_locked_at IS NULL AND failed_code_attempts < 5) OR (code_locked_at IS NOT NULL AND failed_code_attempts = 5)",
            name="ck_mission_presence_code_lock",
        ),
    )


def downgrade() -> None:
    op.drop_table("mission_presence")
