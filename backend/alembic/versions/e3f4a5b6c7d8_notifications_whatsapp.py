"""Notifications sur WhatsApp (étape 8 WhatsApp).

- `channel_identities.last_inbound_at` : dernier message reçu de la personne
  sur WhatsApp (fenêtre de 24 h de Meta) ;
- `notifications.template_required` : Meta a refusé le message libre (fenêtre
  fermée) ; le prochain envoi est un modèle validé.

Deux colonnes ajoutées, sans perte au retour arrière (une information de
confort d'envoi, pas une donnée métier).

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
Create Date: 2026-11-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e3f4a5b6c7d8"
down_revision: Union[str, Sequence[str], None] = "d2e3f4a5b6c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("channel_identities") as batch:
        batch.add_column(sa.Column("last_inbound_at", sa.DateTime(), nullable=True))
    with op.batch_alter_table("notifications") as batch:
        batch.add_column(sa.Column("template_required", sa.Boolean(), nullable=False, server_default=sa.text("false")))


def downgrade() -> None:
    with op.batch_alter_table("notifications") as batch:
        batch.drop_column("template_required")
    with op.batch_alter_table("channel_identities") as batch:
        batch.drop_column("last_inbound_at")
