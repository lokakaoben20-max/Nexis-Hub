from datetime import datetime

from decimal import Decimal

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Float, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database import Base


class BotUser(Base):
    __tablename__ = "bot_users"

    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    language: Mapped[str] = mapped_column(String(5), default="fr")
    total_missions: Mapped[int] = mapped_column(Integer, default=0)


class BotProvider(Base):
    __tablename__ = "bot_providers"

    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    full_name: Mapped[str] = mapped_column(String(255))
    phone_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    services: Mapped[list] = mapped_column(JSON, default=list)
    communes: Mapped[list] = mapped_column(JSON, default=list)
    language: Mapped[str] = mapped_column(String(5), default="fr")
    status: Mapped[str] = mapped_column(String(20), default="available")
    module: Mapped[str] = mapped_column(String(1), default="A")
    badge: Mapped[str] = mapped_column(String(20), default="pending")
    rating: Mapped[float] = mapped_column(Float, default=0.0)
    total_missions: Mapped[int] = mapped_column(Integer, default=0)
    success_rate: Mapped[float] = mapped_column(Float, default=0.0)
    average_rating: Mapped[float] = mapped_column(Float, default=0.0)
    total_reviews: Mapped[int] = mapped_column(Integer, default=0)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_suspended: Mapped[bool] = mapped_column(Boolean, default=False)
    consecutive_ignored: Mapped[int] = mapped_column(Integer, default=0)
    # Vérification obligatoire à l'inscription (voir V5_MIGRATION_PLAN.md) : file_id
    # Telegram, pas d'URL — aucun hébergement de fichier nécessaire.
    id_document_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    selfie_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    portfolio_file_ids: Mapped[list] = mapped_column(JSON, default=list)


class BotMission(Base):
    __tablename__ = "bot_missions"

    mission_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    provider_telegram_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    service: Mapped[str] = mapped_column(String(255))
    commune: Mapped[str] = mapped_column(String(255))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    description: Mapped[str] = mapped_column(Text, default="")
    urgent: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    payment_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    commission_amount: Mapped[float] = mapped_column(Float, default=0.0)
    tola_fee: Mapped[float] = mapped_column(Float, default=0.0)
    aggregator_fee: Mapped[float] = mapped_column(Float, default=0.0)
    total_client: Mapped[float] = mapped_column(Float, default=0.0)
    net_provider: Mapped[float] = mapped_column(Float, default=0.0)
    dispute_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    dispute_opened_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    dispute_deadline: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Id du devis accepté côté bot (db.py), reçu avec la demande de paiement :
    # trace d'audit, les devis backend ont leur propre séquence.
    accepted_quote_ref: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Comptes Nexis (indépendants du canal) du client et du prestataire, fixés
    # au paiement : le règlement crédite ces comptes, quel que soit le canal
    # (Telegram aujourd'hui, WhatsApp ou l'app demain).
    client_account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"), nullable=True)
    provider_account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    # Mise à jour à chaque changement de `status` (voir crud._touch_status) — sert
    # à mesurer "en attente de confirmation depuis quand" (auto-libération) et
    # "sans devis depuis quand" (relances), sans dupliquer un timestamp par statut.
    status_changed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    reminder_sent_10min: Mapped[bool] = mapped_column(Boolean, default=False)
    reminder_sent_20min: Mapped[bool] = mapped_column(Boolean, default=False)


class BotQuote(Base):
    __tablename__ = "bot_quotes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mission_id: Mapped[int] = mapped_column(ForeignKey("bot_missions.mission_id"), index=True)
    provider_telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    delay_hours: Mapped[int] = mapped_column(Integer)
    message: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BotTransaction(Base):
    """Historique d'avant le registre (ledger) : conservé en lecture seule,
    plus jamais écrit. Voir CONCEPTION_ARGENT.md."""

    __tablename__ = "bot_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mission_id: Mapped[int] = mapped_column(ForeignKey("bot_missions.mission_id"), index=True)
    quote_id: Mapped[int | None] = mapped_column(ForeignKey("bot_quotes.id"), nullable=True)
    type: Mapped[str] = mapped_column(String(20))
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    commission_amount: Mapped[float] = mapped_column(Float, default=0.0)
    tola_fee: Mapped[float] = mapped_column(Float, default=0.0)
    aggregator_fee: Mapped[float] = mapped_column(Float, default=0.0)
    net_provider: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    mobile_money_ref: Mapped[str | None] = mapped_column(String(50), nullable=True)
    operator: Mapped[str | None] = mapped_column(String(50), nullable=True)


class BotReview(Base):
    __tablename__ = "bot_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mission_id: Mapped[int] = mapped_column(ForeignKey("bot_missions.mission_id"), unique=True, index=True)
    client_telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    provider_telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    rating: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BotServiceRequest(Base):
    __tablename__ = "bot_service_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider_telegram_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("bot_providers.telegram_id"), index=True)
    service_name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="pending")
    admin_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class NexisAccount(Base):
    """Une personne pour Nexis Hub, indépendamment du canal (architecture du
    canal WhatsApp : table `accounts`). Elle peut être cliente, prestataire,
    ou les deux, avec un seul wallet dans le registre, rattaché à cet
    identifiant et jamais à un identifiant Telegram ou WhatsApp. Les autres
    attributs du compte (rôles, numéro vérifié, langue) arrivent avec le
    chantier d'identité multicanal."""

    __tablename__ = "accounts"
    __table_args__ = (
        Index(
            "uq_accounts_verified_phone_e164",
            "phone_e164",
            unique=True,
            postgresql_where=text("phone_verified_at IS NOT NULL"),
            sqlite_where=text("phone_verified_at IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    roles: Mapped[list[str]] = mapped_column(JSON, default=list)
    # Les numéros saisis avant la vérification multicanal restent sur les
    # profils legacy. Seul un numéro dont la preuve a été vérifiée remplit
    # ces colonnes et participe à l'unicité.
    phone_e164: Mapped[str | None] = mapped_column(String(32), nullable=True)
    phone_verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    language: Mapped[str] = mapped_column(String(5), default="fr")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ChannelIdentity(Base):
    """Rattache un identifiant de canal (`telegram` + telegram_id, plus tard
    `whatsapp` + numéro) à un compte Nexis. Un même canal + identifiant ne
    désigne qu'un seul compte."""

    __tablename__ = "channel_identities"
    __table_args__ = (
        UniqueConstraint("channel", "external_id", name="uq_channel_identities_channel_external_id"),
        UniqueConstraint("account_id", "channel", name="uq_channel_identities_account_channel"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    channel: Mapped[str] = mapped_column(String(20))
    external_id: Mapped[str] = mapped_column(String(64))
    # Telegram et WhatsApp garantissent eux-mêmes l'identifiant de
    # l'expéditeur : une identité créée depuis un message reçu est vérifiée.
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class MoneyOperation(Base):
    """Une opération d'argent (paiement, libération, remboursement, partage,
    solde d'ouverture). Écrite uniquement par backend/app/ledger.py.

    (mission_id, phase) est unique : au plus un paiement (`funding`) et un
    règlement (`settlement`) par mission. C'est la base elle-même qui empêche
    de payer ou de régler deux fois, même sous requêtes simultanées.
    """

    __tablename__ = "money_operations"
    __table_args__ = (UniqueConstraint("mission_id", "phase", name="uq_money_operations_mission_phase"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(30))
    mission_id: Mapped[int | None] = mapped_column(ForeignKey("bot_missions.mission_id"), nullable=True, index=True)
    phase: Mapped[str | None] = mapped_column(String(20), nullable=True)
    actor_telegram_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    reference: Mapped[str | None] = mapped_column(String(64), nullable=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class LedgerEntry(Base):
    """Un mouvement d'un compte. La somme des mouvements d'une opération vaut
    toujours 0 ; le solde d'un compte est la somme de ses mouvements.
    `account_id` : id `accounts` pour `wallet`, id de mission pour `escrow`,
    vide pour `platform`/`external`."""

    __tablename__ = "ledger_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    operation_id: Mapped[int] = mapped_column(ForeignKey("money_operations.id"), index=True)
    account_type: Mapped[str] = mapped_column(String(20), index=True)
    account_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    currency: Mapped[str] = mapped_column(String(3))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
