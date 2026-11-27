"""Avis laissés depuis WhatsApp (étape 7 WhatsApp).

`bot_reviews.client_telegram_id` n'est plus obligatoire : un client WhatsApp
n'a pas de Telegram. L'auteur d'un avis reste toujours connu, par une
contrainte : son compte Nexis (`client_account_id`) ou, pour les avis
d'avant les comptes, son Telegram.

Retour arrière refusé tant qu'un avis n'a pas de Telegram (avis d'un client
WhatsApp) : on ne remplit jamais un faux identifiant.

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
Create Date: 2026-11-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d2e3f4a5b6c7"
down_revision: Union[str, Sequence[str], None] = "c1d2e3f4a5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("bot_reviews") as batch:
        batch.alter_column("client_telegram_id", existing_type=sa.BigInteger(), nullable=True)
        batch.create_check_constraint(
            "ck_bot_reviews_client_known", "client_telegram_id IS NOT NULL OR client_account_id IS NOT NULL"
        )


def downgrade() -> None:
    without_telegram = op.get_bind().execute(sa.text("SELECT count(*) FROM bot_reviews WHERE client_telegram_id IS NULL")).scalar()
    if without_telegram:
        raise RuntimeError(
            f"{without_telegram} avis de clients sans Telegram (WhatsApp) : retour arrière impossible sans les perdre."
        )
    with op.batch_alter_table("bot_reviews") as batch:
        batch.drop_constraint("ck_bot_reviews_client_known", type_="check")
        batch.alter_column("client_telegram_id", existing_type=sa.BigInteger(), nullable=False)
