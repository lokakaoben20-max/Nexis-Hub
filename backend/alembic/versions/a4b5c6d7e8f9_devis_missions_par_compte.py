"""Devis, missions et avis rattachés aux comptes NexisHub, plus à Telegram.

Préalable des comptes entreprises : un prestataire (une entreprise, un
utilisateur de l'app) peut ne pas avoir de Telegram. Le devis, la mission et
l'avis désignent donc toujours des comptes ; les colonnes Telegram ne servent
plus qu'à l'affichage du bot Telegram.

- `bot_quotes.provider_account_id` devient obligatoire ;
  `bot_quotes.provider_telegram_id` devient facultatif.
- `bot_reviews.client_account_id` et `bot_reviews.provider_account_id`
  deviennent obligatoires ; `bot_reviews.provider_telegram_id` devient
  facultatif. La contrainte `ck_bot_reviews_client_known` n'a plus d'objet.
- `bot_missions.client_account_id` devient obligatoire (la contrainte
  `ck_bot_missions_client_known` n'a plus d'objet), et un prestataire nommé
  par son Telegram a toujours son compte (`ck_bot_missions_provider_account`).

Les lignes encore sans compte sont rattachées par l'identité Telegram déjà
enregistrée. Aucun compte n'est fabriqué : une ligne qui ne peut pas être
rattachée arrête la migration et est nommée, pour être corrigée à la main.

Retour arrière refusé tant qu'un devis ou un avis désigne un prestataire sans
Telegram : on ne remplit jamais un faux identifiant.

Revision ID: a4b5c6d7e8f9
Revises: e3f4a5b6c7d8
Create Date: 2026-11-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a4b5c6d7e8f9"
down_revision: Union[str, Sequence[str], None] = "e3f4a5b6c7d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (table, colonne du compte, colonne Telegram correspondante)
LINKS = (
    ("bot_missions", "client_account_id", "telegram_id"),
    ("bot_missions", "provider_account_id", "provider_telegram_id"),
    ("bot_quotes", "provider_account_id", "provider_telegram_id"),
    ("bot_reviews", "client_account_id", "client_telegram_id"),
    ("bot_reviews", "provider_account_id", "provider_telegram_id"),
)

# Lignes qui doivent avoir leur compte après la migration :
# (table, clé, colonne du compte, condition qui exige le compte)
REQUIRED = (
    ("bot_missions", "mission_id", "client_account_id", "TRUE"),
    ("bot_missions", "mission_id", "provider_account_id", "provider_telegram_id IS NOT NULL"),
    ("bot_quotes", "id", "provider_account_id", "TRUE"),
    ("bot_reviews", "id", "client_account_id", "TRUE"),
    ("bot_reviews", "id", "provider_account_id", "TRUE"),
)

SHOWN = 20


def _link_by_telegram(bind) -> None:
    for table, account_col, telegram_col in LINKS:
        bind.execute(
            sa.text(f"""
                UPDATE {table}
                   SET {account_col} = (
                       SELECT identity.account_id
                         FROM channel_identities AS identity
                        WHERE identity.channel = 'telegram'
                          AND identity.external_id = CAST({table}.{telegram_col} AS VARCHAR)
                   )
                 WHERE {account_col} IS NULL
                   AND {telegram_col} IS NOT NULL
            """)
        )


def _refuse_unlinked(bind) -> None:
    problems = []
    for table, key, account_col, required_when in REQUIRED:
        keys = [
            row[0]
            for row in bind.execute(
                sa.text(f"SELECT {key} FROM {table} WHERE {account_col} IS NULL AND ({required_when}) ORDER BY {key}")
            ).fetchall()
        ]
        if keys:
            shown = ", ".join(str(value) for value in keys[:SHOWN])
            more = f" (et {len(keys) - SHOWN} autres)" if len(keys) > SHOWN else ""
            problems.append(f"{table}.{account_col} manquant, {key} : {shown}{more}")
    if problems:
        raise RuntimeError(
            "Lignes sans compte NexisHub ni identité Telegram connue : à rattacher à la main avant la migration. "
            + " ; ".join(problems)
        )


def upgrade() -> None:
    bind = op.get_bind()
    _link_by_telegram(bind)
    _refuse_unlinked(bind)

    with op.batch_alter_table("bot_missions") as batch:
        batch.drop_constraint("ck_bot_missions_client_known", type_="check")
        batch.alter_column("client_account_id", existing_type=sa.Integer(), nullable=False)
        batch.create_check_constraint(
            "ck_bot_missions_provider_account", "provider_telegram_id IS NULL OR provider_account_id IS NOT NULL"
        )
    with op.batch_alter_table("bot_quotes") as batch:
        batch.alter_column("provider_telegram_id", existing_type=sa.BigInteger(), nullable=True)
        batch.alter_column("provider_account_id", existing_type=sa.Integer(), nullable=False)
    with op.batch_alter_table("bot_reviews") as batch:
        batch.drop_constraint("ck_bot_reviews_client_known", type_="check")
        batch.alter_column("provider_telegram_id", existing_type=sa.BigInteger(), nullable=True)
        batch.alter_column("client_account_id", existing_type=sa.Integer(), nullable=False)
        batch.alter_column("provider_account_id", existing_type=sa.Integer(), nullable=False)


def downgrade() -> None:
    bind = op.get_bind()
    for table in ("bot_quotes", "bot_reviews"):
        without_telegram = bind.execute(
            sa.text(f"SELECT count(*) FROM {table} WHERE provider_telegram_id IS NULL")
        ).scalar()
        if without_telegram:
            raise RuntimeError(
                f"{without_telegram} ligne(s) de {table} pour un prestataire sans Telegram : "
                "retour arrière impossible sans les perdre."
            )

    with op.batch_alter_table("bot_reviews") as batch:
        batch.alter_column("provider_account_id", existing_type=sa.Integer(), nullable=True)
        batch.alter_column("client_account_id", existing_type=sa.Integer(), nullable=True)
        batch.alter_column("provider_telegram_id", existing_type=sa.BigInteger(), nullable=False)
        batch.create_check_constraint(
            "ck_bot_reviews_client_known", "client_telegram_id IS NOT NULL OR client_account_id IS NOT NULL"
        )
    with op.batch_alter_table("bot_quotes") as batch:
        batch.alter_column("provider_account_id", existing_type=sa.Integer(), nullable=True)
        batch.alter_column("provider_telegram_id", existing_type=sa.BigInteger(), nullable=False)
    with op.batch_alter_table("bot_missions") as batch:
        batch.drop_constraint("ck_bot_missions_provider_account", type_="check")
        batch.alter_column("client_account_id", existing_type=sa.Integer(), nullable=True)
        batch.create_check_constraint(
            "ck_bot_missions_client_known", "telegram_id IS NOT NULL OR client_account_id IS NOT NULL"
        )
