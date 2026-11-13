"""Profils au backend : profils rangés par compte Nexis, catalogue en base.

Chantier « profils au backend », étape 1 (plan
`profils/plan-profils-backend-2026-11-12.md`).

Crée :
- `services` et `communes` : le catalogue, rempli ici (`catalogue_initial`) ;
- `client_profiles`, `provider_profiles` : un profil par compte Nexis ;
- `provider_services`, `provider_communes` : ce que propose un prestataire,
  avec clés étrangères vers le catalogue (plus de listes JSON) ;
- `provider_service_requests` : demandes de nouveau service.

Recopie dans la même transaction les lignes de `bot_users`, `bot_providers`,
`bot_service_requests` et le nom WhatsApp (`accounts.display_name`), puis
supprime ces tables et cette colonne. Règles de reprise :
- l'identifiant Telegram est rattaché à son compte Nexis (créé s'il n'existe
  pas encore, comme le fait le backend à la première écriture) ;
- un prestataire non vérifié ne garde jamais un statut de prestataire vérifié :
  `rejected` reste `rejected`, tout le reste devient `pending_verification` ;
- un prestataire vérifié garde `available`, `offline` ou `paused` ; tout autre
  statut (ancienne suspension notée `paused`, valeur inconnue) devient
  `offline` : il se remettra disponible lui-même ;
- la suspension reste un drapeau, indépendant du statut ;
- un service ou une commune absent du catalogue fait **échouer** la migration,
  avec la liste de ce qui manque : rien n'est perdu en silence.

Le retour arrière recrée les anciennes tables et y recopie les profils. Il
refuse un profil prestataire sans identité Telegram (il n'aurait pas de place
dans `bot_providers`).

Revision ID: e0f1a2b3c4d5
Revises: d9e0f1a2b3c4
Create Date: 2026-11-12
"""

import json
import logging
from datetime import datetime
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from backend.app import catalogue_initial

revision: str = "e0f1a2b3c4d5"
down_revision: Union[str, Sequence[str], None] = "d9e0f1a2b3c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger("alembic.runtime.migration")

PROVIDER_STATUSES = ("pending_verification", "rejected", "available", "offline", "paused")
VERIFIED_STATUSES = ("available", "offline", "paused")
BADGES = ("pending", "verified", "premium", "expert", "partner")


def _in(values) -> str:
    return "(" + ", ".join(f"'{value}'" for value in values) + ")"


def _json_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, str):
        value = json.loads(value)
    return list(value)


def _roles_with(roles, role) -> str:
    return json.dumps(sorted(set(_json_list(roles)) | {role}))


def _create_catalogue_and_profiles() -> None:
    op.create_table(
        "services",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("name_fr", sa.String(length=100), nullable=False),
        sa.Column("name_ln", sa.String(length=100), nullable=False),
        sa.Column("name_en", sa.String(length=100), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("icon_emoji", sa.String(length=16), nullable=False),
        sa.Column("module", sa.String(length=1), nullable=False),
        sa.Column("requires_inspection", sa.Boolean(), nullable=False),
        sa.Column("visit_fee_usd", sa.Numeric(10, 2), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("key"),
        sa.UniqueConstraint("position", name="uq_services_position"),
        sa.CheckConstraint("module IN ('A', 'B')", name="ck_services_module"),
        sa.CheckConstraint(
            "(module = 'B' AND requires_inspection AND visit_fee_usd > 0)"
            " OR (module = 'A' AND NOT requires_inspection AND visit_fee_usd = 0)",
            name="ck_services_visit_fee",
        ),
    )
    op.create_table(
        "communes",
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("name"),
        sa.UniqueConstraint("position", name="uq_communes_position"),
    )
    op.create_table(
        "client_profiles",
        sa.Column("account_id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("first_name", sa.String(length=255), nullable=False),
        sa.Column("phone_number", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], name="fk_client_profiles_account_id_accounts"),
        sa.PrimaryKeyConstraint("account_id"),
    )
    op.create_table(
        "provider_profiles",
        sa.Column("account_id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("phone_number", sa.String(length=50), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("verified_at", sa.DateTime(), nullable=True),
        sa.Column("is_suspended", sa.Boolean(), nullable=False),
        sa.Column("suspended_at", sa.DateTime(), nullable=True),
        sa.Column("badge", sa.String(length=20), nullable=False),
        sa.Column("average_rating", sa.Float(), nullable=False),
        sa.Column("total_reviews", sa.Integer(), nullable=False),
        sa.Column("total_missions", sa.Integer(), nullable=False),
        sa.Column("success_rate", sa.Float(), nullable=False),
        sa.Column("consecutive_ignored", sa.Integer(), nullable=False),
        sa.Column("id_document_file_id", sa.String(length=255), nullable=True),
        sa.Column("selfie_file_id", sa.String(length=255), nullable=True),
        sa.Column("portfolio_file_ids", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], name="fk_provider_profiles_account_id_accounts"),
        sa.PrimaryKeyConstraint("account_id"),
        sa.CheckConstraint(f"status IN {_in(PROVIDER_STATUSES)}", name="ck_provider_profiles_status"),
        sa.CheckConstraint(
            f"(verified_at IS NOT NULL AND status IN {_in(VERIFIED_STATUSES)})"
            f" OR (verified_at IS NULL AND status NOT IN {_in(VERIFIED_STATUSES)})",
            name="ck_provider_profiles_verified_status",
        ),
        sa.CheckConstraint(
            "(is_suspended AND suspended_at IS NOT NULL) OR (NOT is_suspended AND suspended_at IS NULL)",
            name="ck_provider_profiles_suspension",
        ),
        sa.CheckConstraint(f"badge IN {_in(BADGES)}", name="ck_provider_profiles_badge"),
        sa.CheckConstraint("consecutive_ignored >= 0", name="ck_provider_profiles_ignored"),
    )
    op.create_index("ix_provider_profiles_status", "provider_profiles", ["status"])
    op.create_table(
        "provider_services",
        sa.Column("account_id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("service_key", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(
            ["account_id"], ["provider_profiles.account_id"], ondelete="CASCADE",
            name="fk_provider_services_account_id_provider_profiles",
        ),
        sa.ForeignKeyConstraint(["service_key"], ["services.key"], name="fk_provider_services_service_key_services"),
        sa.PrimaryKeyConstraint("account_id", "service_key"),
    )
    op.create_index("ix_provider_services_service_key", "provider_services", ["service_key"])
    op.create_table(
        "provider_communes",
        sa.Column("account_id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("commune", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(
            ["account_id"], ["provider_profiles.account_id"], ondelete="CASCADE",
            name="fk_provider_communes_account_id_provider_profiles",
        ),
        sa.ForeignKeyConstraint(["commune"], ["communes.name"], name="fk_provider_communes_commune_communes"),
        sa.PrimaryKeyConstraint("account_id", "commune"),
    )
    op.create_index("ix_provider_communes_commune", "provider_communes", ["commune"])
    op.create_table(
        "provider_service_requests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("provider_account_id", sa.Integer(), nullable=False),
        sa.Column("service_name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("admin_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["provider_account_id"], ["provider_profiles.account_id"],
            name="fk_provider_service_requests_provider_account_id_provider_profiles",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("status IN ('pending', 'accepted', 'rejected')", name="ck_provider_service_requests_status"),
        sa.CheckConstraint(
            "(status = 'pending' AND reviewed_at IS NULL) OR (status <> 'pending' AND reviewed_at IS NOT NULL)",
            name="ck_provider_service_requests_reviewed",
        ),
    )
    op.create_index("ix_provider_service_requests_provider_account_id", "provider_service_requests", ["provider_account_id"])
    op.create_index("ix_provider_service_requests_status", "provider_service_requests", ["status"])


def _account_for_telegram(bind, telegram_id: int, language: str, now: datetime) -> int:
    account_id = bind.execute(
        sa.text("SELECT account_id FROM channel_identities WHERE channel = 'telegram' AND external_id = :external_id"),
        {"external_id": str(telegram_id)},
    ).scalar_one_or_none()
    if account_id is not None:
        return account_id
    account_id = bind.execute(
        sa.text("INSERT INTO accounts (created_at, roles, language) VALUES (:now, '[]', :language) RETURNING id"),
        {"now": now, "language": language if language in ("fr", "ln", "en") else "fr"},
    ).scalar_one()
    bind.execute(
        sa.text(
            "INSERT INTO channel_identities (account_id, channel, external_id, verified_at, created_at)"
            " VALUES (:account_id, 'telegram', :external_id, :now, :now)"
        ),
        {"account_id": account_id, "external_id": str(telegram_id), "now": now},
    )
    return account_id


def _add_role(bind, account_id: int, role: str) -> None:
    roles = bind.execute(sa.text("SELECT roles FROM accounts WHERE id = :id"), {"id": account_id}).scalar_one()
    bind.execute(
        sa.text("UPDATE accounts SET roles = :roles WHERE id = :id"),
        {"roles": _roles_with(roles, role), "id": account_id},
    )


def _provider_status(status: str, verified: bool) -> str:
    if verified:
        return status if status in VERIFIED_STATUSES else "offline"
    return "rejected" if status == "rejected" else "pending_verification"


def _copy_profiles(bind) -> None:
    now = datetime.utcnow()
    known_services = {row[0] for row in catalogue_initial.SERVICES}
    known_communes = set(catalogue_initial.COMMUNES)

    providers = bind.execute(sa.text("SELECT * FROM bot_providers ORDER BY telegram_id")).mappings().all()
    unknown = []
    for provider in providers:
        for service in _json_list(provider["services"]):
            if service not in known_services:
                unknown.append(f"prestataire {provider['telegram_id']} : service {service!r}")
        for commune in _json_list(provider["communes"]):
            if commune not in known_communes:
                unknown.append(f"prestataire {provider['telegram_id']} : commune {commune!r}")
    if unknown:
        raise RuntimeError(
            "Services ou communes absents du catalogue, migration arrêtée sans rien changer : " + "; ".join(unknown)
        )

    users = bind.execute(sa.text("SELECT * FROM bot_users ORDER BY telegram_id")).mappings().all()
    for user in users:
        account_id = _account_for_telegram(bind, user["telegram_id"], user["language"], now)
        bind.execute(
            sa.text(
                "INSERT INTO client_profiles (account_id, first_name, phone_number, created_at, updated_at)"
                " VALUES (:account_id, :first_name, :phone_number, :now, :now)"
            ),
            {
                "account_id": account_id,
                "first_name": (user["first_name"] or "").strip() or "Client",
                "phone_number": user["phone_number"],
                "now": now,
            },
        )
        _add_role(bind, account_id, "client")

    # Clients WhatsApp : leur nom était sur le compte.
    named = bind.execute(
        sa.text("SELECT id, display_name FROM accounts WHERE display_name IS NOT NULL ORDER BY id")
    ).all()
    for account_id, display_name in named:
        existing = bind.execute(
            sa.text("SELECT first_name FROM client_profiles WHERE account_id = :id"), {"id": account_id}
        ).scalar_one_or_none()
        if existing is not None:
            if existing != display_name:
                raise RuntimeError(
                    f"Le compte {account_id} a deux noms de client différents (Telegram et WhatsApp) : "
                    "migration arrêtée sans rien changer"
                )
            continue
        bind.execute(
            sa.text(
                "INSERT INTO client_profiles (account_id, first_name, phone_number, created_at, updated_at)"
                " VALUES (:account_id, :first_name, NULL, :now, :now)"
            ),
            {"account_id": account_id, "first_name": display_name, "now": now},
        )
        _add_role(bind, account_id, "client")

    demoted = 0
    service_position = {row[0]: index for index, row in enumerate(catalogue_initial.SERVICES)}
    commune_position = {name: index for index, name in enumerate(catalogue_initial.COMMUNES)}
    for provider in providers:
        account_id = _account_for_telegram(bind, provider["telegram_id"], provider["language"], now)
        verified = bool(provider["is_verified"])
        status = _provider_status(provider["status"], verified)
        if status != provider["status"]:
            demoted += 1
        badge = provider["badge"] if provider["badge"] in BADGES else ("verified" if verified else "pending")
        if not verified:
            badge = "pending"
        suspended = bool(provider["is_suspended"])
        bind.execute(
            sa.text(
                "INSERT INTO provider_profiles (account_id, full_name, phone_number, status, verified_at,"
                " is_suspended, suspended_at, badge, average_rating, total_reviews, total_missions, success_rate,"
                " consecutive_ignored, id_document_file_id, selfie_file_id, portfolio_file_ids, created_at, updated_at)"
                " VALUES (:account_id, :full_name, :phone_number, :status, :verified_at, :is_suspended, :suspended_at,"
                " :badge, :average_rating, :total_reviews, :total_missions, :success_rate, :consecutive_ignored,"
                " :id_document_file_id, :selfie_file_id, :portfolio_file_ids, :now, :now)"
            ),
            {
                "account_id": account_id,
                "full_name": (provider["full_name"] or "").strip() or "Prestataire",
                "phone_number": provider["phone_number"],
                "status": status,
                "verified_at": now if verified else None,
                "is_suspended": suspended,
                "suspended_at": now if suspended else None,
                "badge": badge,
                "average_rating": provider["average_rating"] or 0.0,
                "total_reviews": provider["total_reviews"] or 0,
                "total_missions": provider["total_missions"] or 0,
                "success_rate": provider["success_rate"] or 0.0,
                "consecutive_ignored": max(provider["consecutive_ignored"] or 0, 0),
                "id_document_file_id": provider["id_document_file_id"],
                "selfie_file_id": provider["selfie_file_id"],
                "portfolio_file_ids": json.dumps(_json_list(provider["portfolio_file_ids"])),
                "now": now,
            },
        )
        for service in sorted(set(_json_list(provider["services"])), key=service_position.get):
            bind.execute(
                sa.text("INSERT INTO provider_services (account_id, service_key) VALUES (:account_id, :key)"),
                {"account_id": account_id, "key": service},
            )
        for commune in sorted(set(_json_list(provider["communes"])), key=commune_position.get):
            bind.execute(
                sa.text("INSERT INTO provider_communes (account_id, commune) VALUES (:account_id, :commune)"),
                {"account_id": account_id, "commune": commune},
            )
        _add_role(bind, account_id, "provider")

    requests = bind.execute(sa.text("SELECT * FROM bot_service_requests ORDER BY id")).mappings().all()
    for request in requests:
        account_id = _account_for_telegram(bind, request["provider_telegram_id"], "fr", now)
        status = request["status"] if request["status"] in ("pending", "accepted", "rejected") else "rejected"
        reviewed_at = None if status == "pending" else (request["reviewed_at"] or request["created_at"] or now)
        bind.execute(
            sa.text(
                "INSERT INTO provider_service_requests (id, provider_account_id, service_name, description, status,"
                " admin_note, created_at, reviewed_at)"
                " VALUES (:id, :account_id, :service_name, :description, :status, :admin_note, :created_at, :reviewed_at)"
            ),
            {
                "id": request["id"],
                "account_id": account_id,
                "service_name": request["service_name"],
                "description": request["description"] or "",
                "status": status,
                "admin_note": request["admin_note"],
                "created_at": request["created_at"] or now,
                "reviewed_at": reviewed_at,
            },
        )
    if requests and bind.dialect.name == "postgresql":
        bind.execute(
            sa.text(
                "SELECT setval(pg_get_serial_sequence('provider_service_requests', 'id'),"
                " (SELECT MAX(id) FROM provider_service_requests))"
            )
        )

    logger.info(
        "Profils repris : %s client(s), %s client(s) WhatsApp, %s prestataire(s) dont %s au statut corrigé, "
        "%s demande(s) de service",
        len(users), len(named), len(providers), demoted, len(requests),
    )


def upgrade() -> None:
    bind = op.get_bind()
    _create_catalogue_and_profiles()
    catalogue_initial.remplir(bind)
    _copy_profiles(bind)
    op.drop_index("ix_bot_service_requests_status", table_name="bot_service_requests")
    op.drop_index("ix_bot_service_requests_provider_telegram_id", table_name="bot_service_requests")
    op.drop_index("ix_bot_service_requests_provider_account_id", table_name="bot_service_requests")
    op.drop_table("bot_service_requests")
    op.drop_table("bot_providers")
    op.drop_table("bot_users")
    op.drop_column("accounts", "display_name")


# --- Retour arrière -----------------------------------------------------------


def downgrade() -> None:
    bind = op.get_bind()
    orphan = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM provider_profiles p WHERE NOT EXISTS ("
            " SELECT 1 FROM channel_identities i WHERE i.account_id = p.account_id AND i.channel = 'telegram')"
        )
    ).scalar_one()
    if orphan:
        raise RuntimeError(
            f"{orphan} prestataire(s) sans identité Telegram : retour arrière refusé, ils n'auraient pas de place"
        )

    op.add_column("accounts", sa.Column("display_name", sa.String(length=100), nullable=True))
    op.create_table(
        "bot_users",
        sa.Column("telegram_id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("first_name", sa.String(length=255), nullable=True),
        sa.Column("phone_number", sa.String(length=50), nullable=True),
        sa.Column("language", sa.String(length=5), nullable=False),
        sa.Column("total_missions", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("telegram_id"),
    )
    op.create_table(
        "bot_providers",
        sa.Column("telegram_id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("phone_number", sa.String(length=50), nullable=True),
        sa.Column("services", sa.JSON(), nullable=False),
        sa.Column("communes", sa.JSON(), nullable=False),
        sa.Column("language", sa.String(length=5), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("module", sa.String(length=1), nullable=False),
        sa.Column("badge", sa.String(length=20), nullable=False),
        sa.Column("rating", sa.Float(), nullable=False),
        sa.Column("total_missions", sa.Integer(), nullable=False),
        sa.Column("success_rate", sa.Float(), nullable=False),
        sa.Column("is_verified", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_suspended", sa.Boolean(), nullable=False),
        sa.Column("consecutive_ignored", sa.Integer(), nullable=False),
        sa.Column("average_rating", sa.Float(), server_default="0", nullable=False),
        sa.Column("total_reviews", sa.Integer(), server_default="0", nullable=False),
        sa.Column("id_document_file_id", sa.String(length=255), nullable=True),
        sa.Column("selfie_file_id", sa.String(length=255), nullable=True),
        sa.Column("portfolio_file_ids", sa.JSON(), server_default="[]", nullable=False),
        sa.PrimaryKeyConstraint("telegram_id"),
    )
    op.create_table(
        "bot_service_requests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("provider_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("service_name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("admin_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("provider_account_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["provider_telegram_id"], ["bot_providers.telegram_id"]),
        sa.ForeignKeyConstraint(
            ["provider_account_id"], ["accounts.id"], name="fk_bot_service_requests_provider_account_id_accounts"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bot_service_requests_provider_account_id", "bot_service_requests", ["provider_account_id"])
    op.create_index("ix_bot_service_requests_provider_telegram_id", "bot_service_requests", ["provider_telegram_id"])
    op.create_index("ix_bot_service_requests_status", "bot_service_requests", ["status"])

    telegram_of = (
        "(SELECT CAST(i.external_id AS BIGINT) FROM channel_identities i"
        " WHERE i.account_id = {account} AND i.channel = 'telegram')"
    )
    clients = bind.execute(
        sa.text(
            "SELECT c.account_id, c.first_name, c.phone_number, a.language, "
            + telegram_of.format(account="c.account_id")
            + " AS telegram_id FROM client_profiles c JOIN accounts a ON a.id = c.account_id ORDER BY c.account_id"
        )
    ).mappings().all()
    for client in clients:
        if client["telegram_id"] is None:
            bind.execute(
                sa.text("UPDATE accounts SET display_name = :name WHERE id = :id"),
                {"name": client["first_name"][:100], "id": client["account_id"]},
            )
            continue
        missions = bind.execute(
            sa.text("SELECT COUNT(*) FROM bot_missions WHERE client_account_id = :id"), {"id": client["account_id"]}
        ).scalar_one()
        bind.execute(
            sa.text(
                "INSERT INTO bot_users (telegram_id, first_name, phone_number, language, total_missions)"
                " VALUES (:telegram_id, :first_name, :phone_number, :language, :total_missions)"
            ),
            {**client, "total_missions": missions},
        )

    providers = bind.execute(
        sa.text(
            "SELECT p.*, a.language, "
            + telegram_of.format(account="p.account_id")
            + " AS telegram_id FROM provider_profiles p JOIN accounts a ON a.id = p.account_id ORDER BY p.account_id"
        )
    ).mappings().all()
    for provider in providers:
        services = list(
            bind.execute(
                sa.text(
                    "SELECT ps.service_key FROM provider_services ps JOIN services s ON s.key = ps.service_key"
                    " WHERE ps.account_id = :id ORDER BY s.position"
                ),
                {"id": provider["account_id"]},
            ).scalars()
        )
        communes = list(
            bind.execute(
                sa.text(
                    "SELECT pc.commune FROM provider_communes pc JOIN communes c ON c.name = pc.commune"
                    " WHERE pc.account_id = :id ORDER BY c.position"
                ),
                {"id": provider["account_id"]},
            ).scalars()
        )
        module_b = bind.execute(
            sa.text(
                "SELECT COUNT(*) FROM provider_services ps JOIN services s ON s.key = ps.service_key"
                " WHERE ps.account_id = :id AND s.module = 'B'"
            ),
            {"id": provider["account_id"]},
        ).scalar_one()
        bind.execute(
            sa.text(
                "INSERT INTO bot_providers (telegram_id, full_name, phone_number, services, communes, language, status,"
                " module, badge, rating, total_missions, success_rate, is_verified, is_active, is_suspended,"
                " consecutive_ignored, average_rating, total_reviews, id_document_file_id, selfie_file_id,"
                " portfolio_file_ids) VALUES (:telegram_id, :full_name, :phone_number, :services, :communes, :language,"
                " :status, :module, :badge, 0, :total_missions, :success_rate, :is_verified, TRUE, :is_suspended,"
                " :consecutive_ignored, :average_rating, :total_reviews, :id_document_file_id, :selfie_file_id,"
                " :portfolio_file_ids)"
            ),
            {
                "telegram_id": provider["telegram_id"],
                "full_name": provider["full_name"],
                "phone_number": provider["phone_number"],
                "services": json.dumps(services),
                "communes": json.dumps(communes),
                "language": provider["language"],
                "status": provider["status"],
                "module": "B" if module_b else "A",
                "badge": provider["badge"],
                "total_missions": provider["total_missions"],
                "success_rate": provider["success_rate"],
                "is_verified": provider["verified_at"] is not None,
                "is_suspended": provider["is_suspended"],
                "consecutive_ignored": provider["consecutive_ignored"],
                "average_rating": provider["average_rating"],
                "total_reviews": provider["total_reviews"],
                "id_document_file_id": provider["id_document_file_id"],
                "selfie_file_id": provider["selfie_file_id"],
                "portfolio_file_ids": json.dumps(_json_list(provider["portfolio_file_ids"])),
            },
        )

    requests = bind.execute(
        sa.text(
            "SELECT r.*, "
            + telegram_of.format(account="r.provider_account_id")
            + " AS telegram_id FROM provider_service_requests r ORDER BY r.id"
        )
    ).mappings().all()
    for request in requests:
        bind.execute(
            sa.text(
                "INSERT INTO bot_service_requests (id, provider_telegram_id, service_name, description, status,"
                " admin_note, created_at, reviewed_at, provider_account_id) VALUES (:id, :telegram_id, :service_name,"
                " :description, :status, :admin_note, :created_at, :reviewed_at, :provider_account_id)"
            ),
            dict(request),
        )
    if requests and bind.dialect.name == "postgresql":
        bind.execute(
            sa.text(
                "SELECT setval(pg_get_serial_sequence('bot_service_requests', 'id'),"
                " (SELECT MAX(id) FROM bot_service_requests))"
            )
        )

    op.drop_index("ix_provider_service_requests_status", table_name="provider_service_requests")
    op.drop_index("ix_provider_service_requests_provider_account_id", table_name="provider_service_requests")
    op.drop_table("provider_service_requests")
    op.drop_index("ix_provider_communes_commune", table_name="provider_communes")
    op.drop_table("provider_communes")
    op.drop_index("ix_provider_services_service_key", table_name="provider_services")
    op.drop_table("provider_services")
    op.drop_index("ix_provider_profiles_status", table_name="provider_profiles")
    op.drop_table("provider_profiles")
    op.drop_table("client_profiles")
    op.drop_table("communes")
    op.drop_table("services")
