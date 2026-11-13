from datetime import datetime

from decimal import Decimal

from sqlalchemy import JSON, BigInteger, Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database import Base


class BotMission(Base):
    __tablename__ = "bot_missions"
    __table_args__ = (
        # Une demande de création rejouée (réseau coupé, double clic) retrouve
        # la mission déjà créée au lieu d'en créer une seconde.
        UniqueConstraint("client_account_id", "creation_key", name="uq_bot_missions_client_creation_key"),
        # Lieu exact : les trois champs ensemble, ou aucun (missions créées
        # avant le lieu exact).
        CheckConstraint(
            "(destination_latitude IS NULL AND destination_longitude IS NULL AND destination_landmark IS NULL)"
            " OR (destination_latitude IS NOT NULL AND destination_longitude IS NOT NULL AND destination_landmark IS NOT NULL)",
            name="ck_bot_missions_destination_complete",
        ),
    )

    # Numéro attribué par le backend, seule mémoire des missions : aucun canal
    # ne choisit le numéro d'une mission.
    mission_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    provider_telegram_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    service: Mapped[str] = mapped_column(String(255))
    commune: Mapped[str] = mapped_column(String(255))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    description: Mapped[str] = mapped_column(Text, default="")
    # Lieu exact où le service est rendu, et repère écrit par le client. Jamais
    # renvoyé avec la mission : route à part, réservée au client, à l'admin et
    # au prestataire d'une mission payée (crud.destination_access).
    destination_latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    destination_longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    destination_landmark: Mapped[str | None] = mapped_column(String(300), nullable=True)
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
    # Dernière alerte admin « litige sans décision après le délai de réponse »
    # (tâche `litiges-en-retard`) : une alerte, puis une relance par jour.
    dispute_overdue_alerted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Échéance de la libération automatique, fixée quand le prestataire déclare
    # la mission terminée (`ledger.finish_mission`) : la règle annoncée au
    # client à ce moment-là ne change plus, même si le délai change ensuite.
    release_after: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    # Devis accepté (bot_quotes.id) sur lequel la mission a été payée.
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
    # Clé choisie par le canal pour une demande de création (idempotence).
    creation_key: Mapped[str | None] = mapped_column(String(64), nullable=True)


class MissionMedia(Base):
    """Photo ou note vocale jointe à une mission. L'identifiant n'a de sens que
    pour son canal (un identifiant de fichier Telegram ne sert qu'au bot
    Telegram) : il est toujours rangé avec ce canal."""

    __tablename__ = "mission_media"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mission_id: Mapped[int] = mapped_column(ForeignKey("bot_missions.mission_id"), index=True)
    channel: Mapped[str] = mapped_column(String(20))
    kind: Mapped[str] = mapped_column(String(10))
    external_id: Mapped[str] = mapped_column(String(255))
    position: Mapped[int] = mapped_column(Integer)


class MissionAlert(Base):
    """Prestataire prévenu d'une mission. Seul un prestataire prévenu peut lire
    la mission et y répondre par un devis."""

    __tablename__ = "mission_alerts"
    __table_args__ = (UniqueConstraint("mission_id", "provider_account_id", name="uq_mission_alerts_mission_provider"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mission_id: Mapped[int] = mapped_column(ForeignKey("bot_missions.mission_id"), index=True)
    provider_account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    alerted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class MissionPresence(Base):
    """Arrivée du prestataire chez le client (CONCEPTION_MISSIONS.md,
    « Arrivée confirmée »). La présence n'est confirmée que par l'appui du
    client (« Oui, il est là ») ou par le code de présence du client, tapé par
    le prestataire : le « je suis arrivé » du prestataire seul ne vaut rien.
    Le code n'est jamais enregistré (backend.app.presence.presence_code).
    Une ligne par mission, créée au premier événement."""

    __tablename__ = "mission_presence"
    __table_args__ = (
        CheckConstraint("confirmed_by IS NULL OR confirmed_by IN ('client', 'presence_code')", name="ck_mission_presence_confirmed_by"),
        CheckConstraint(
            "(confirmed_at IS NULL AND confirmed_by IS NULL) OR (confirmed_at IS NOT NULL AND confirmed_by IS NOT NULL)",
            name="ck_mission_presence_confirmation_complete",
        ),
        CheckConstraint("failed_code_attempts >= 0 AND failed_code_attempts <= 5", name="ck_mission_presence_attempts"),
        CheckConstraint(
            "(code_locked_at IS NULL AND failed_code_attempts < 5) OR (code_locked_at IS NOT NULL AND failed_code_attempts = 5)",
            name="ck_mission_presence_code_lock",
        ),
    )

    mission_id: Mapped[int] = mapped_column(ForeignKey("bot_missions.mission_id"), primary_key=True)
    # Premier « je suis arrivé » du prestataire.
    arrival_declared_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Dernière question « votre prestataire est-il arrivé ? » envoyée au client.
    client_asked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Dernier « pas encore » du client.
    not_yet_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    confirmed_by: Mapped[str | None] = mapped_column(String(20), nullable=True)
    failed_code_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Cinq mauvais codes : seul l'appui du client peut encore confirmer.
    code_locked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # « Ce n'est pas lui » : litige ouvert, fonds gelés jusqu'à l'admin.
    wrong_person_reported_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class BotQuote(Base):
    __tablename__ = "bot_quotes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mission_id: Mapped[int] = mapped_column(ForeignKey("bot_missions.mission_id"), index=True)
    provider_telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    provider_account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"), nullable=True, index=True)
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
    client_account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"), nullable=True, index=True)
    provider_account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"), nullable=True, index=True)
    rating: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


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
    # Seule langue de la personne, quel que soit son rôle ou son canal.
    language: Mapped[str] = mapped_column(String(5), default="fr")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AdminRole(Base):
    """Personne de Nexis Hub autorisée à agir comme admin (litiges, retraits,
    vérification des prestataires). Plusieurs personnes peuvent l'être : une
    décision de litige contestée doit être revue par une autre personne que
    celle qui l'a prise.

    Le rôle est donné et retiré par `python -m backend.app.admins`, jamais par
    l'API. Une ligne n'est jamais effacée : un retrait remplit `revoked_at`.
    Au plus un rôle actif par compte."""

    __tablename__ = "admin_roles"
    __table_args__ = (
        Index(
            "uq_admin_roles_active_account",
            "account_id",
            unique=True,
            postgresql_where=text("revoked_at IS NULL"),
            sqlite_where=text("revoked_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    granted_at: Mapped[datetime] = mapped_column(DateTime)
    granted_reason: Mapped[str] = mapped_column(Text)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revoked_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class ChannelIdentity(Base):
    """Rattache un identifiant de canal (`telegram` + telegram_id,
    `whatsapp` + BSUID) à un compte Nexis. Un même canal + identifiant ne
    désigne qu'un seul compte."""

    __tablename__ = "channel_identities"
    __table_args__ = (
        UniqueConstraint("channel", "external_id", name="uq_channel_identities_channel_external_id"),
        UniqueConstraint("account_id", "channel", name="uq_channel_identities_account_channel"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    channel: Mapped[str] = mapped_column(String(20))
    # Telegram : l'identifiant numérique. WhatsApp : le BSUID de Meta (code
    # pays de 2 lettres, un point, puis jusqu'à 128 caractères).
    external_id: Mapped[str] = mapped_column(String(160))
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
    # Qui a déclenché l'opération : son compte Nexis, et l'identifiant Telegram
    # quand l'action vient de Telegram (admin compris). Vides pour une
    # opération automatique.
    actor_account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"), nullable=True, index=True)
    actor_telegram_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    reference: Mapped[str | None] = mapped_column(String(64), nullable=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DisputeDecision(Base):
    """Décision de Nexis Hub sur un litige, en deux temps (règles du
    8 novembre 2026, CONCEPTION_ARGENT.md). Écrite uniquement par
    backend/app/ledger.py ; une ligne n'est jamais effacée.

    - Tour 1 : décision de l'admin. Les montants sont calculés et figés ici,
      l'argent reste gelé, et la décision n'est exécutée qu'à `execute_after`
      (3 jours plus tard), sauf si le client ou le prestataire la conteste.
    - Tour 2 : révision d'une décision contestée, par une autre personne de
      Nexis Hub que celle du tour 1. Elle est finale et exécutée tout de suite.

    `executed_operation_id` pointe vers le règlement du registre : une
    décision exécutée l'est exactement une fois (règlement unique par
    mission dans `money_operations`)."""

    __tablename__ = "dispute_decisions"
    __table_args__ = (
        UniqueConstraint("mission_id", "round", name="uq_dispute_decisions_mission_round"),
        CheckConstraint("round IN (1, 2)", name="ck_dispute_decisions_round"),
        CheckConstraint("decision IN ('refund', 'release', 'split')", name="ck_dispute_decisions_decision"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mission_id: Mapped[int] = mapped_column(ForeignKey("bot_missions.mission_id"), index=True)
    round: Mapped[int] = mapped_column(Integer)
    decision: Mapped[str] = mapped_column(String(20))
    # Pourcentage versé au prestataire (partage seulement), au centième.
    provider_percentage: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3))
    provider_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    client_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    platform_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    decided_by_account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    decided_by_telegram_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    decided_at: Mapped[datetime] = mapped_column(DateTime)
    execute_after: Mapped[datetime] = mapped_column(DateTime, index=True)
    contested_by_account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"), nullable=True)
    # `client` ou `provider` : qui a contesté, tel que montré aux parties.
    contested_by_role: Mapped[str | None] = mapped_column(String(20), nullable=True)
    contested_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    contest_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    executed_operation_id: Mapped[int | None] = mapped_column(ForeignKey("money_operations.id"), nullable=True, unique=True)


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


class PaymentIntent(Base):
    """Demande de paiement Mobile Money d'une mission (CONCEPTION_MOBILE_MONEY.md).

    N'est pas de l'argent : seul l'agrégateur, en confirmant, fait payer la
    mission dans le registre. Une seule intention ouverte (`created` ou
    `pending`) par mission, garanti par l'index partiel ci-dessous."""

    __tablename__ = "payment_intents"
    __table_args__ = (
        Index(
            "uq_payment_intents_open_per_mission",
            "mission_id",
            unique=True,
            postgresql_where=text("status IN ('created', 'pending')"),
            sqlite_where=text("status IN ('created', 'pending')"),
        ),
        UniqueConstraint("gateway", "gateway_reference", name="uq_payment_intents_gateway_reference"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mission_id: Mapped[int] = mapped_column(ForeignKey("bot_missions.mission_id"), index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    gateway: Mapped[str] = mapped_column(String(30))
    gateway_reference: Mapped[str | None] = mapped_column(String(64), nullable=True)
    operator: Mapped[str] = mapped_column(String(20))
    phone: Mapped[str] = mapped_column(String(32))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3))
    # Tout ce que `ledger.fund_mission` doit recevoir quand l'argent arrive.
    funding_request: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="created", index=True)
    failure_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Montant reçu par l'agrégateur quand il diffère de la demande (statut
    # `mismatch`), puis décision de l'admin (`mobile_money.resolve_mismatch`).
    received_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    received_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    resolved_by_telegram_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Payout(Base):
    """Retrait d'un wallet vers le Mobile Money (CONCEPTION_MOBILE_MONEY.md).

    Le montant est bloqué dans le registre (compte `payout_pending`) dès la
    demande ; il n'en sort que vers l'extérieur (versement confirmé) ou vers
    le wallet (refus ou échec)."""

    __tablename__ = "payouts"
    __table_args__ = (UniqueConstraint("gateway", "gateway_reference", name="uq_payouts_gateway_reference"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    # Identité Telegram du demandeur (audit, messages) ; vide pour un autre canal.
    requested_by_telegram_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    gateway: Mapped[str] = mapped_column(String(30))
    gateway_reference: Mapped[str | None] = mapped_column(String(64), nullable=True)
    operator: Mapped[str] = mapped_column(String(20))
    phone: Mapped[str] = mapped_column(String(32))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    fee: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3))
    status: Mapped[str] = mapped_column(String(20), default="awaiting_approval", index=True)
    needs_review_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    decided_by_telegram_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ---------------------------------------------------------------------------
# Application mobile : appareils, sessions, codes de connexion
# (plan : app-mobile/plan-etape1-connexion-api-2026-11-07.md, section 4).
#
# Aucun secret n'est stocké en clair : jetons et codes sont hachés, seule la
# clé publique d'un appareil est connue (la clé privée ne quitte jamais le
# coffre matériel du téléphone). Les contraintes de base de données, et non le
# seul code, garantissent les états impossibles.
# ---------------------------------------------------------------------------

DEVICE_PLATFORMS = ("android", "ios")
# `verified` : Google (attestation de clé + Play Integrity) ou Apple (App
# Attest) a confirmé l'app et le téléphone. `unverified` : lecture permise,
# aucune action d'argent sortante (décision de Ben, 2026-11-07).
DEVICE_ATTESTATIONS = ("verified", "unverified")
LOGIN_PURPOSES = ("signup", "login")
LOGIN_DELIVERIES = ("whatsapp", "telegram")
MAX_CODE_ATTEMPTS = 5


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(value) for value in values)})"


class Device(Base):
    """Un téléphone relié à un compte Nexis par l'application.

    Un appareil coupé (`revoked_at`) ne revit jamais : une reconnexion crée un
    nouvel appareil, avec une nouvelle clé. `money_unlocked_at` porte le délai
    de sécurité avant toute action d'argent sortante (72 h pour un appareil
    ajouté à un compte existant)."""

    __tablename__ = "devices"
    __table_args__ = (
        CheckConstraint(_in("platform", DEVICE_PLATFORMS), name="ck_devices_platform"),
        CheckConstraint(_in("attestation", DEVICE_ATTESTATIONS), name="ck_devices_attestation"),
        CheckConstraint(
            "(revoked_at IS NULL AND revoked_reason IS NULL) OR (revoked_at IS NOT NULL AND revoked_reason IS NOT NULL)",
            name="ck_devices_revocation_reason",
        ),
        CheckConstraint("money_unlocked_at >= created_at", name="ck_devices_money_unlock_after_creation"),
        UniqueConstraint("key_thumbprint", name="uq_devices_key_thumbprint"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    platform: Mapped[str] = mapped_column(String(10))
    # Clé publique P-256 (SubjectPublicKeyInfo, DER en base64) et son empreinte
    # SHA-256 en hexadécimal, par laquelle l'appareil est retrouvé.
    public_key: Mapped[str] = mapped_column(Text)
    key_thumbprint: Mapped[str] = mapped_column(String(64))
    attestation: Mapped[str] = mapped_column(String(12))
    label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    app_version: Mapped[str] = mapped_column(String(20))
    money_unlocked_at: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revoked_reason: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # Alerte « Nouvel appareil » (boîte d'envoi) : `alert_due_at` est posé dans
    # la même transaction que la création du téléphone, puis la tâche planifiée
    # `alertes-nouvel-appareil` l'envoie et réessaie en cas d'échec. NULL : rien
    # à envoyer (premier téléphone d'un compte neuf, alerte envoyée ou abandonnée).
    alert_due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    alert_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    alert_attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class AppSession(Base):
    """Jetons d'une session d'appareil, hachés (SHA-256). Chaque renouvellement
    crée une nouvelle ligne de la même famille et pointe l'ancienne vers elle
    (`replaced_by_id`) : un ancien jeton présenté à nouveau trahit un vol, et
    toute la famille est coupée."""

    __tablename__ = "app_sessions"
    __table_args__ = (
        CheckConstraint("access_expires_at > created_at", name="ck_app_sessions_access_expiry"),
        CheckConstraint("refresh_expires_at >= access_expires_at", name="ck_app_sessions_refresh_expiry"),
        CheckConstraint(
            "(revoked_at IS NULL AND revoked_reason IS NULL) OR (revoked_at IS NOT NULL AND revoked_reason IS NOT NULL)",
            name="ck_app_sessions_revocation_reason",
        ),
        UniqueConstraint("access_hash", name="uq_app_sessions_access_hash"),
        UniqueConstraint("refresh_hash", name="uq_app_sessions_refresh_hash"),
        UniqueConstraint("replaced_by_id", name="uq_app_sessions_replaced_by_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), index=True)
    family_id: Mapped[str] = mapped_column(String(32), index=True)
    access_hash: Mapped[str] = mapped_column(String(64))
    access_expires_at: Mapped[datetime] = mapped_column(DateTime)
    refresh_hash: Mapped[str] = mapped_column(String(64))
    refresh_expires_at: Mapped[datetime] = mapped_column(DateTime)
    replaced_by_id: Mapped[int | None] = mapped_column(ForeignKey("app_sessions.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revoked_reason: Mapped[str | None] = mapped_column(String(30), nullable=True)


class LoginChallenge(Base):
    """Une demande de code de connexion, liée à la clé de l'appareil qui l'a
    faite : le code ne vaut que pour ce téléphone.

    `public_id` est le seul identifiant montré à l'app (aléatoire, pour qu'on
    ne puisse pas parcourir les demandes). `code_hash` (HMAC avec une clé
    serveur) est vide tant que le code n'est pas parti, par exemple avant que
    la personne ait partagé son numéro au bot Telegram. `telegram_start_hash`
    est l'empreinte du lien de démarrage du bot, à usage unique."""

    __tablename__ = "login_challenges"
    __table_args__ = (
        CheckConstraint(_in("purpose", LOGIN_PURPOSES), name="ck_login_challenges_purpose"),
        CheckConstraint(_in("delivery", LOGIN_DELIVERIES), name="ck_login_challenges_delivery"),
        CheckConstraint(f"attempts >= 0 AND attempts <= {MAX_CODE_ATTEMPTS}", name="ck_login_challenges_attempts"),
        CheckConstraint("expires_at > created_at", name="ck_login_challenges_expiry"),
        CheckConstraint("consumed_at IS NULL OR code_hash IS NOT NULL", name="ck_login_challenges_consumed_needs_code"),
        Index("ix_login_challenges_phone_created", "phone_e164", "created_at"),
        Index("ix_login_challenges_device_created", "device_key_thumbprint", "created_at"),
        UniqueConstraint("public_id", name="uq_login_challenges_public_id"),
        UniqueConstraint("telegram_start_hash", name="uq_login_challenges_telegram_start_hash"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(String(32))
    phone_e164: Mapped[str] = mapped_column(String(32))
    purpose: Mapped[str] = mapped_column(String(10))
    delivery: Mapped[str] = mapped_column(String(10))
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"), nullable=True, index=True)
    device_key_thumbprint: Mapped[str] = mapped_column(String(64))
    code_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    telegram_start_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class RequestNonce(Base):
    """Nonce d'une demande signée par un appareil : la base refuse de voir
    deux fois le même, même sous demandes simultanées (anti-rejeu)."""

    __tablename__ = "request_nonces"
    __table_args__ = (UniqueConstraint("device_id", "nonce", name="uq_request_nonces_device_nonce"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"))
    nonce: Mapped[str] = mapped_column(String(64))
    seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class AuthEvent(Base):
    """Journal d'audit des connexions, en ajout seul : aucune fonction du
    backend ne le modifie ni ne l'efface. Ni numéro en clair, ni code, ni
    jeton : seulement le compte, l'appareil, le type, le résultat et une
    empreinte de l'adresse réseau."""

    __tablename__ = "auth_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"), nullable=True, index=True)
    device_id: Mapped[int | None] = mapped_column(ForeignKey("devices.id"), nullable=True, index=True)
    type: Mapped[str] = mapped_column(String(40))
    result: Mapped[str] = mapped_column(String(20))
    ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


# --- Profils (chantier « profils au backend ») ----------------------------
#
# Le backend est la seule mémoire des profils : un profil client et un profil
# prestataire au plus par compte Nexis, quel que soit le canal. L'identifiant
# Telegram ou WhatsApp ne vit que dans `channel_identities`. Les règles (qui
# change quoi, qui est éligible) sont dans `backend/app/profils.py` ; les
# contraintes ci-dessous rendent impossibles, dans la base elle-même, les états
# que ces règles interdisent.

SERVICE_MODULES = ("A", "B")
PROVIDER_STATUSES = ("pending_verification", "rejected", "available", "offline", "paused")
# Statuts d'un prestataire vérifié, et d'eux seuls : un prestataire non
# vérifié ne peut jamais être disponible, donc jamais recevoir une mission.
PROVIDER_VERIFIED_STATUSES = ("available", "offline", "paused")
PROVIDER_BADGES = ("pending", "verified", "premium", "expert", "partner")
SERVICE_REQUEST_STATUSES = ("pending", "accepted", "rejected")


def _sql_in(values) -> str:
    return "(" + ", ".join(f"'{value}'" for value in values) + ")"


class Service(Base):
    """Catalogue des services. Rempli et modifié par migration seulement :
    les frais de visite (module B) sont une règle d'argent, à un seul endroit."""

    __tablename__ = "services"
    __table_args__ = (
        CheckConstraint(f"module IN {_sql_in(SERVICE_MODULES)}", name="ck_services_module"),
        # Module B = visite payante avant devis ; module A = ni visite ni frais.
        CheckConstraint(
            "(module = 'B' AND requires_inspection AND visit_fee_usd > 0)"
            " OR (module = 'A' AND NOT requires_inspection AND visit_fee_usd = 0)",
            name="ck_services_visit_fee",
        ),
        UniqueConstraint("position", name="uq_services_position"),
    )

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    name_fr: Mapped[str] = mapped_column(String(100))
    name_ln: Mapped[str] = mapped_column(String(100))
    name_en: Mapped[str] = mapped_column(String(100))
    category: Mapped[str] = mapped_column(String(50))
    icon_emoji: Mapped[str] = mapped_column(String(16))
    module: Mapped[str] = mapped_column(String(1))
    requires_inspection: Mapped[bool] = mapped_column(Boolean)
    visit_fee_usd: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    position: Mapped[int] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Commune(Base):
    """Communes servies, telles que les canaux les proposent. Remplies par
    migration seulement."""

    __tablename__ = "communes"
    __table_args__ = (UniqueConstraint("position", name="uq_communes_position"),)

    name: Mapped[str] = mapped_column(String(64), primary_key=True)
    position: Mapped[int] = mapped_column(Integer)


class ClientProfile(Base):
    """Profil client d'un compte Nexis (Telegram, WhatsApp ou l'app)."""

    __tablename__ = "client_profiles"

    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), primary_key=True, autoincrement=False)
    first_name: Mapped[str] = mapped_column(String(255))
    # Numéro donné par la personne, pour la contacter. Seul le numéro prouvé
    # du compte (`accounts.phone_e164`) sert à l'identifier.
    phone_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ProviderProfile(Base):
    """Profil prestataire d'un compte Nexis. Services et communes : tables
    `provider_services` et `provider_communes`."""

    __tablename__ = "provider_profiles"
    __table_args__ = (
        CheckConstraint(f"status IN {_sql_in(PROVIDER_STATUSES)}", name="ck_provider_profiles_status"),
        # Vérifié <=> statut de prestataire vérifié. Un prestataire en attente
        # ou refusé ne peut pas être disponible, même par erreur de code.
        CheckConstraint(
            f"(verified_at IS NOT NULL AND status IN {_sql_in(PROVIDER_VERIFIED_STATUSES)})"
            f" OR (verified_at IS NULL AND status NOT IN {_sql_in(PROVIDER_VERIFIED_STATUSES)})",
            name="ck_provider_profiles_verified_status",
        ),
        CheckConstraint(
            "(is_suspended AND suspended_at IS NOT NULL) OR (NOT is_suspended AND suspended_at IS NULL)",
            name="ck_provider_profiles_suspension",
        ),
        CheckConstraint(f"badge IN {_sql_in(PROVIDER_BADGES)}", name="ck_provider_profiles_badge"),
        CheckConstraint("consecutive_ignored >= 0", name="ck_provider_profiles_ignored"),
        Index("ix_provider_profiles_status", "status"),
    )

    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), primary_key=True, autoincrement=False)
    full_name: Mapped[str] = mapped_column(String(255))
    phone_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="pending_verification")
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Suspension par l'admin : indépendante du statut, qui est retrouvé tel
    # quel au rétablissement.
    is_suspended: Mapped[bool] = mapped_column(Boolean, default=False)
    suspended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    badge: Mapped[str] = mapped_column(String(20), default="pending")
    # Statistiques recalculées depuis les missions et les avis
    # (crud._recompute_provider_stats), jamais saisies.
    average_rating: Mapped[float] = mapped_column(Float, default=0.0)
    total_reviews: Mapped[int] = mapped_column(Integer, default=0)
    total_missions: Mapped[int] = mapped_column(Integer, default=0)
    success_rate: Mapped[float] = mapped_column(Float, default=0.0)
    consecutive_ignored: Mapped[int] = mapped_column(Integer, default=0)
    # Vérification à l'inscription : identifiants de fichiers Telegram. Leur
    # stockage chiffré relève du chantier « vérification des prestataires ».
    id_document_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    selfie_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    portfolio_file_ids: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ProviderService(Base):
    __tablename__ = "provider_services"

    account_id: Mapped[int] = mapped_column(
        ForeignKey("provider_profiles.account_id", ondelete="CASCADE"), primary_key=True, autoincrement=False
    )
    service_key: Mapped[str] = mapped_column(ForeignKey("services.key"), primary_key=True, index=True)


class ProviderCommune(Base):
    __tablename__ = "provider_communes"

    account_id: Mapped[int] = mapped_column(
        ForeignKey("provider_profiles.account_id", ondelete="CASCADE"), primary_key=True, autoincrement=False
    )
    commune: Mapped[str] = mapped_column(ForeignKey("communes.name"), primary_key=True, index=True)


class ProviderServiceRequest(Base):
    """Demande d'un prestataire pour un service absent du catalogue."""

    __tablename__ = "provider_service_requests"
    __table_args__ = (
        CheckConstraint(f"status IN {_sql_in(SERVICE_REQUEST_STATUSES)}", name="ck_provider_service_requests_status"),
        CheckConstraint(
            "(status = 'pending' AND reviewed_at IS NULL) OR (status <> 'pending' AND reviewed_at IS NOT NULL)",
            name="ck_provider_service_requests_reviewed",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider_account_id: Mapped[int] = mapped_column(ForeignKey("provider_profiles.account_id"), index=True)
    service_name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    admin_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
