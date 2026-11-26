"""Missions créées depuis WhatsApp (étape 5 WhatsApp).

`bot_missions.telegram_id` n'est plus obligatoire : un client WhatsApp n'a
pas de Telegram. Le client d'une mission reste toujours connu, par une
contrainte : son compte Nexis (`client_account_id`) ou, pour les missions
d'avant les comptes, son Telegram.

Retour arrière refusé tant qu'une mission n'a pas de Telegram (mission d'un
client WhatsApp) : on ne remplit jamais un faux identifiant.

Revision ID: c1d2e3f4a5b6
Revises: b0c1d2e3f4a5
Create Date: 2026-11-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, Sequence[str], None] = "b0c1d2e3f4a5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("bot_missions") as batch:
        batch.alter_column("telegram_id", existing_type=sa.BigInteger(), nullable=True)
        batch.create_check_constraint(
            "ck_bot_missions_client_known", "telegram_id IS NOT NULL OR client_account_id IS NOT NULL"
        )


def downgrade() -> None:
    without_telegram = op.get_bind().execute(sa.text("SELECT count(*) FROM bot_missions WHERE telegram_id IS NULL")).scalar()
    if without_telegram:
        raise RuntimeError(
            f"{without_telegram} mission(s) de clients sans Telegram (WhatsApp) : retour arrière impossible sans les perdre."
        )
    with op.batch_alter_table("bot_missions") as batch:
        batch.drop_constraint("ck_bot_missions_client_known", type_="check")
        batch.alter_column("telegram_id", existing_type=sa.BigInteger(), nullable=False)
