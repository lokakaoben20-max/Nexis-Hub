from datetime import datetime, timedelta

from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app import app_auth, ledger
from backend.app.models import (
    BotMission,
    BotProvider,
    BotQuote,
    BotReview,
    BotServiceRequest,
    BotUser,
    MissionAlert,
    MissionMedia,
    NexisAccount,
)

MODULE_B_SERVICES = {"service_plomberie", "service_electricite", "service_climatisation"}
BADGE_SCORES = {"partner": 30, "expert": 20, "premium": 10, "verified": 5, "pending": 0}
SERVICE_REQUEST_STATUSES = {"pending", "accepted", "rejected"}

# Nombre de missions terminées à partir duquel le taux de succès devient un
# signal exploitable dans le matching (en dessous, il n'est pas représentatif).
MIN_MISSIONS_FOR_SUCCESS_BONUS = 3


def _compute_module(services: list[str]) -> str:
    return "B" if any(service in MODULE_B_SERVICES for service in services) else "A"


def _touch_status(mission: BotMission) -> None:
    """Marque le moment du changement de statut d'une mission.

    Sert de référence pour les tâches Celery de la Phase 2 : auto-libération
    d'escrow après 24h passées en `awaiting_confirmation`, relances quand une
    mission reste sans devis. Appeler juste après toute assignation de
    `mission.status`.
    """
    mission.status_changed_at = datetime.utcnow()


def _sync_account_role(db: Session, telegram_id: int, role: str, language: str) -> NexisAccount:
    """Synchronise le rôle et la langue commune du compte à chaque écriture
    de profil Telegram. Les profils restent des vues métier historiques ;
    l'identité canonique réside dans `accounts` + `channel_identities`."""
    account_id = ledger.account_id_for(db, ledger.TELEGRAM, telegram_id, create=True)
    account = db.get(NexisAccount, account_id, with_for_update=True)
    if account is None:  # défense contre une identité orpheline en base
        raise RuntimeError(f"Compte Nexis introuvable pour l'identité Telegram {telegram_id}")
    roles = set(account.roles or [])
    roles.add(role)
    account.roles = sorted(roles)
    account.language = language
    return account


def _record_proven_phone(db: Session, account_id: int, phone_number: str | None, phone_verified: bool) -> None:
    """Numéro prouvé par le canal (bouton « Partager mon numéro » de
    Telegram, contact de l'expéditeur) : enregistré sur le compte Nexis. Un
    numéro tapé, ou illisible, n'est jamais enregistré comme prouvé. Un numéro
    déjà prouvé sur un autre compte reste où il est (`app_auth.prove_phone`)."""
    if not phone_verified or not phone_number:
        return
    try:
        app_auth.prove_phone(db, account_id, phone_number)
    except app_auth.AuthError:
        return


def _account_id_for_telegram(db: Session, telegram_id: int) -> int:
    """Compte canonique d'une identité Telegram vérifiée par le canal."""
    return ledger.account_id_for(db, ledger.TELEGRAM, telegram_id, create=True)


def upsert_user(
    db: Session,
    telegram_id: int,
    first_name: str | None,
    phone_number: str | None,
    language: str = "fr",
    phone_verified: bool = False,
) -> BotUser:
    user = db.get(BotUser, telegram_id)
    if user is None:
        user = BotUser(telegram_id=telegram_id)
        db.add(user)
    user.first_name = first_name or "Client"
    user.phone_number = phone_number
    user.language = language
    account = _sync_account_role(db, telegram_id, "client", language)
    _record_proven_phone(db, account.id, phone_number, phone_verified)
    db.commit()
    db.refresh(user)
    return user


def upsert_provider(
    db: Session,
    telegram_id: int,
    full_name: str,
    phone_number: str | None,
    services: list[str],
    communes: list[str],
    language: str = "fr",
    id_document_file_id: str | None = None,
    selfie_file_id: str | None = None,
    portfolio_file_ids: list[str] | None = None,
    phone_verified: bool = False,
) -> BotProvider:
    provider = db.get(BotProvider, telegram_id)
    is_new = provider is None
    if provider is None:
        provider = BotProvider(telegram_id=telegram_id)
        db.add(provider)
    provider.full_name = full_name
    provider.phone_number = phone_number
    provider.services = services
    provider.communes = communes
    provider.language = language
    provider.module = _compute_module(services)
    account = _sync_account_role(db, telegram_id, "provider", language)
    _record_proven_phone(db, account.id, phone_number, phone_verified)
    # None = pas fourni sur cet appel (ex. mise à jour de profil) : ne pas écraser
    # des documents déjà soumis avec du vide.
    if id_document_file_id is not None:
        provider.id_document_file_id = id_document_file_id
    if selfie_file_id is not None:
        provider.selfie_file_id = selfie_file_id
    if portfolio_file_ids is not None:
        provider.portfolio_file_ids = portfolio_file_ids
    if not is_new:
        provider.status = "available"
    db.commit()
    db.refresh(provider)
    return provider


def update_user_language(db: Session, telegram_id: int, language: str) -> BotUser | None:
    user = db.get(BotUser, telegram_id)
    if user is None:
        return None
    user.language = language
    _sync_account_role(db, telegram_id, "client", language)
    db.commit()
    db.refresh(user)
    return user


def update_user_name(db: Session, telegram_id: int, first_name: str) -> BotUser | None:
    user = db.get(BotUser, telegram_id)
    if user is None:
        return None
    user.first_name = first_name
    db.commit()
    db.refresh(user)
    return user


def update_provider_language(db: Session, telegram_id: int, language: str) -> BotProvider | None:
    provider = db.get(BotProvider, telegram_id)
    if provider is None:
        return None
    provider.language = language
    _sync_account_role(db, telegram_id, "provider", language)
    db.commit()
    db.refresh(provider)
    return provider


def update_provider_services(db: Session, telegram_id: int, services: list[str]) -> BotProvider | None:
    provider = db.get(BotProvider, telegram_id)
    if provider is None:
        return None
    provider.services = services
    provider.module = _compute_module(services)
    db.commit()
    db.refresh(provider)
    return provider


def update_provider_status(db: Session, telegram_id: int, status: str) -> BotProvider | None:
    provider = db.get(BotProvider, telegram_id)
    if provider is None:
        return None
    provider.status = status
    db.commit()
    db.refresh(provider)
    return provider


def set_provider_verified(db: Session, telegram_id: int, is_verified: bool = True) -> BotProvider | None:
    provider = db.get(BotProvider, telegram_id)
    if provider is None:
        return None
    provider.is_verified = is_verified
    provider.badge = "verified" if is_verified else "pending"
    db.commit()
    db.refresh(provider)
    return provider


def set_provider_suspended(db: Session, telegram_id: int, is_suspended: bool = True) -> BotProvider | None:
    provider = db.get(BotProvider, telegram_id)
    if provider is None:
        return None
    provider.is_suspended = is_suspended
    provider.status = "paused" if is_suspended else "available"
    db.commit()
    db.refresh(provider)
    return provider


def update_consecutive_ignored(db: Session, telegram_id: int) -> BotProvider | None:
    provider = db.get(BotProvider, telegram_id)
    if provider is None:
        return None
    provider.consecutive_ignored += 1
    if provider.consecutive_ignored >= 3:
        provider.status = "paused"
    db.commit()
    db.refresh(provider)
    return provider


def reset_consecutive_ignored(db: Session, telegram_id: int) -> BotProvider | None:
    provider = db.get(BotProvider, telegram_id)
    if provider is None:
        return None
    provider.consecutive_ignored = 0
    db.commit()
    db.refresh(provider)
    return provider


def find_matching_providers(db: Session, service: str, commune: str) -> list[BotProvider]:
    providers = (
        db.query(BotProvider)
        .filter(BotProvider.is_active.is_(True))
        .filter(BotProvider.is_suspended.is_(False))
        .filter(BotProvider.status == "available")
        .all()
    )

    matches = []
    for provider in providers:
        if service in (provider.services or []) and commune in (provider.communes or []):
            matches.append((_matching_score(provider), provider))

    matches.sort(key=lambda item: item[0], reverse=True)
    return [provider for _, provider in matches[:3]]


def _matching_score(provider: BotProvider) -> float:
    score = BADGE_SCORES.get(provider.badge, 0)
    # `average_rating` (moyenne réelle des avis) et non l'ancien champ
    # `rating`, qui n'a jamais été alimenté et vaut 0 partout : la note
    # d'un prestataire ne pesait donc rien dans le classement.
    score += provider.average_rating * 10
    score += min(provider.total_missions, 50) * 0.2
    # Le bonus de fiabilité demande un minimum d'historique : sans lui,
    # un prestataire sans aucune mission (success_rate initialisé à
    # 100 %) partait à égalité avec un vétéran irréprochable.
    if provider.total_missions >= MIN_MISSIONS_FOR_SUCCESS_BONUS:
        if provider.success_rate == 100:
            score += 15
        elif provider.success_rate >= 90:
            score += 8
    return score


def rank_providers(db: Session, telegram_ids: list[int]) -> list[int]:
    """Classe des prestataires déjà choisis par l'appelant, au score de
    matching seul : ni disponibilité, ni service, ni commune ne sont filtrés
    ici (le bot les lit dans db.py, que la Mini App met à jour sans le
    backend). Les inconnus du backend sont omis ; à égalité, l'ordre reçu."""
    providers = db.query(BotProvider).filter(BotProvider.telegram_id.in_(telegram_ids)).all()
    position = {telegram_id: index for index, telegram_id in enumerate(telegram_ids)}
    providers.sort(key=lambda provider: (-_matching_score(provider), position[provider.telegram_id]))
    return [provider.telegram_id for provider in providers]


MEDIA_KINDS = ("photo", "voice", "video_note")  # 10 caractères au plus (mission_media.kind)
# Une mission reçoit des devis tant qu'aucun n'est accepté.
QUOTABLE_STATUSES = {"pending", "quoted"}
MAX_MISSION_MEDIA = 20
MAX_ALERTED_PROVIDERS = 20


class MissionRefused(ValueError):
    """Refus métier d'une demande sur une mission : code stable pour le canal."""

    def __init__(self, code: str, http_status: int = 409):
        super().__init__(code)
        self.code = code
        self.http_status = http_status


def create_mission(
    db: Session,
    *,
    channel: str,
    client_external_id: str,
    creation_key: str,
    service: str,
    commune: str,
    currency: str = "USD",
    description: str = "",
    urgent: bool = False,
    media: list[tuple[str, str]] | None = None,
    alert_provider_telegram_ids: list[int] | None = None,
) -> tuple[BotMission, bool]:
    """Crée une mission : le backend lui donne son numéro, le client est la
    personne pour qui le canal agit. Mission, médias et prestataires prévenus
    sont écrits dans une seule transaction.

    Idempotent : la même `creation_key` pour le même client renvoie la mission
    déjà créée (second élément `False`), ou un refus si la demande diffère.
    Le client n'est jamais prévenu de sa propre mission comme prestataire."""
    media = list(media or [])
    alert_ids = list(dict.fromkeys(alert_provider_telegram_ids or []))
    if not creation_key or len(creation_key) > 64:
        raise MissionRefused("invalid_creation_key", 400)
    if not service or not commune:
        raise MissionRefused("invalid_mission", 400)
    if currency not in ledger.CURRENCIES:
        raise MissionRefused("invalid_currency", 400)
    if len(media) > MAX_MISSION_MEDIA:
        raise MissionRefused("too_many_media", 400)
    if any(kind not in MEDIA_KINDS or not external_id for kind, external_id in media):
        raise MissionRefused("invalid_media", 400)
    if len(alert_ids) > MAX_ALERTED_PROVIDERS:
        raise MissionRefused("too_many_alerts", 400)

    client_account_id = ledger.account_id_for(db, channel, client_external_id, create=True)
    request = {"service": service, "commune": commune, "currency": currency, "description": description, "urgent": bool(urgent)}

    def already_created() -> BotMission | None:
        existing = (
            db.query(BotMission)
            .filter(BotMission.client_account_id == client_account_id, BotMission.creation_key == creation_key)
            .one_or_none()
        )
        if existing is None:
            return None
        same_request = {
            "service": existing.service,
            "commune": existing.commune,
            "currency": existing.currency,
            "description": existing.description,
            "urgent": bool(existing.urgent),
        } == request and [(item.kind, item.external_id) for item in mission_media(db, existing.mission_id)] == media
        if not same_request:
            raise MissionRefused("creation_key_reused")
        return existing

    existing = already_created()
    if existing is not None:
        return existing, False

    client_telegram_id = ledger.telegram_id_of(db, client_account_id)
    if client_telegram_id is None:
        # `bot_missions.telegram_id` reste obligatoire tant que seul Telegram
        # crée des missions (étape 1 de docs/ARCHITECTURE_WHATSAPP.md).
        raise MissionRefused("channel_identity_missing", 400)

    mission = BotMission(
        telegram_id=client_telegram_id,
        client_account_id=client_account_id,
        creation_key=creation_key,
        service=service,
        commune=commune,
        currency=currency,
        description=description,
        urgent=bool(urgent),
        status="pending",
    )
    db.add(mission)
    db.flush()
    for position, (kind, external_id) in enumerate(media):
        db.add(MissionMedia(mission_id=mission.mission_id, channel=channel, kind=kind, external_id=external_id, position=position))
    for provider_telegram_id in alert_ids:
        provider_account_id = ledger.account_id_for(db, ledger.TELEGRAM, provider_telegram_id, create=True)
        if provider_account_id == client_account_id:
            continue
        db.add(MissionAlert(mission_id=mission.mission_id, provider_account_id=provider_account_id))
    user = db.get(BotUser, client_telegram_id)
    if user is not None:
        user.total_missions += 1
    try:
        db.commit()
    except IntegrityError:
        # La même demande, arrivée au même instant, a été écrite la première :
        # c'est elle qui fait foi (même réponse qu'un rejeu).
        db.rollback()
        existing = already_created()
        if existing is None:
            raise
        return existing, False
    db.refresh(mission)
    return mission, True


def mission_media(db: Session, mission_id: int) -> list[MissionMedia]:
    return (
        db.query(MissionMedia).filter(MissionMedia.mission_id == mission_id).order_by(MissionMedia.position).all()
    )


def alerted_provider_account_ids(db: Session, mission_id: int) -> list[int]:
    rows = db.query(MissionAlert.provider_account_id).filter(MissionAlert.mission_id == mission_id).order_by(MissionAlert.id)
    return [account_id for (account_id,) in rows]


def was_alerted(db: Session, mission_id: int, provider_account_id: int) -> bool:
    return (
        db.query(MissionAlert.id)
        .filter(MissionAlert.mission_id == mission_id, MissionAlert.provider_account_id == provider_account_id)
        .first()
        is not None
    )


def mission_viewer_role(db: Session, mission: BotMission, account_id: int | None) -> str | None:
    """Ce que la personne est pour cette mission : `client`, `provider` (choisi,
    ou auteur d'un devis), `alerted` (prévenu, peut répondre), sinon `None`
    (elle ne lit pas la mission)."""
    if account_id is None:
        return None
    if mission.client_account_id == account_id:
        return "client"
    if mission.provider_account_id == account_id:
        return "provider"
    quoted = (
        db.query(BotQuote.id)
        .filter(BotQuote.mission_id == mission.mission_id, BotQuote.provider_account_id == account_id)
        .first()
    )
    if quoted is not None:
        return "provider"
    if was_alerted(db, mission.mission_id, account_id):
        return "alerted"
    return None


def client_missions(db: Session, client_account_id: int, limit: int = 20) -> list[BotMission]:
    return (
        db.query(BotMission)
        .filter(BotMission.client_account_id == client_account_id)
        .order_by(BotMission.mission_id.desc())
        .limit(limit)
        .all()
    )


def provider_missions(db: Session, provider_account_id: int, limit: int = 20) -> list[BotMission]:
    """Missions confiées à ce prestataire (devis accepté)."""
    return (
        db.query(BotMission)
        .filter(BotMission.provider_account_id == provider_account_id)
        .order_by(BotMission.mission_id.desc())
        .limit(limit)
        .all()
    )


def admin_missions(db: Session, status: str | None = None, limit: int = 10) -> list[BotMission]:
    query = db.query(BotMission)
    if status is not None:
        query = query.filter(BotMission.status == status)
    return query.order_by(BotMission.mission_id.desc()).limit(limit).all()


def mission_stats(db: Session) -> dict:
    return {
        "missions": db.query(func.count(BotMission.mission_id)).scalar() or 0,
        "disputes": db.query(func.count(BotMission.mission_id)).filter(BotMission.status == "disputed").scalar() or 0,
    }


def create_quote(
    db: Session,
    mission_id: int,
    provider_telegram_id: int,
    amount: float,
    currency: str,
    delay_hours: int,
    message: str = "",
) -> BotQuote | None:
    mission = db.get(BotMission, mission_id, with_for_update=True)
    if mission is None:
        return None
    if mission.status not in QUOTABLE_STATUSES:
        # Devis accepté ou mission payée : plus de nouveau devis.
        raise MissionRefused("mission_not_open")
    provider_account_id = _account_id_for_telegram(db, provider_telegram_id)
    client_account_id = mission.client_account_id or _account_id_for_telegram(db, mission.telegram_id)
    if client_account_id == provider_account_id:
        # Un prestataire peut commander comme client, jamais chiffrer sa
        # propre mission (le paiement le refuserait aussi : ledger).
        raise ValueError("provider_is_client")
    if not was_alerted(db, mission_id, provider_account_id):
        # Seul un prestataire prévenu de la mission y répond.
        raise MissionRefused("provider_not_alerted", 403)
    quote = BotQuote(
        mission_id=mission_id,
        provider_telegram_id=provider_telegram_id,
        provider_account_id=provider_account_id,
        amount=amount,
        currency=currency,
        delay_hours=delay_hours,
        message=message,
    )
    db.add(quote)
    mission.status = "quoted"
    _touch_status(mission)
    db.commit()
    db.refresh(quote)
    return quote


def _require_quote_client(db: Session, quote: BotQuote, client_account_id: int) -> None:
    """Seul le client de la mission accepte ou refuse ses devis."""
    mission = db.get(BotMission, quote.mission_id)
    if mission is None or mission.client_account_id is None:
        raise ValueError("mission_account_missing")
    if mission.client_account_id != client_account_id:
        raise ValueError("not_mission_client")


def accept_quote(db: Session, quote_id: int, client_account_id: int) -> BotQuote | None:
    """Un seul devis accepté par mission, et seulement tant qu'aucun ne l'est :
    c'est ce devis, et lui seul, que le paiement relira."""
    quote = db.get(BotQuote, quote_id)
    if quote is None:
        return None
    _require_quote_client(db, quote, client_account_id)
    mission = db.get(BotMission, quote.mission_id, with_for_update=True)
    db.refresh(quote)
    if quote.status == "accepted":
        return quote  # rejeu de la même acceptation
    if quote.status != "pending" or mission.status not in QUOTABLE_STATUSES:
        raise MissionRefused("quote_not_open")

    quote.status = "accepted"
    other_quotes = (
        db.query(BotQuote)
        .filter(BotQuote.mission_id == quote.mission_id, BotQuote.id != quote_id)
        .all()
    )
    for other in other_quotes:
        other.status = "rejected"

    mission = db.get(BotMission, quote.mission_id)
    if mission is not None:
        mission.status = "confirmed"
        _touch_status(mission)
        mission.provider_telegram_id = quote.provider_telegram_id
        mission.provider_account_id = quote.provider_account_id or _account_id_for_telegram(db, quote.provider_telegram_id)

    db.commit()
    db.refresh(quote)
    return quote


def reject_quote(db: Session, quote_id: int, client_account_id: int) -> BotQuote | None:
    quote = db.get(BotQuote, quote_id)
    if quote is None:
        return None
    _require_quote_client(db, quote, client_account_id)
    if quote.status == "rejected":
        return quote  # rejeu
    if quote.status != "pending":
        # Un devis accepté ne se refuse plus : c'est celui que le paiement relit.
        raise MissionRefused("quote_not_open")
    quote.status = "rejected"
    db.commit()
    db.refresh(quote)
    return quote


def expire_stale_quotes(db: Session, older_than_hours: int = 24) -> list[BotQuote]:
    """Marque `expired` les devis `pending` plus vieux que `older_than_hours`.

    Si un devis expiré était le dernier devis actif d'une mission `quoted`, la
    mission repasse à `pending` pour rester matchable — sinon elle resterait
    coincée sur `quoted` sans plus aucun devis vivant.
    """
    cutoff = datetime.utcnow() - timedelta(hours=older_than_hours)
    stale_quotes = (
        db.query(BotQuote)
        .filter(BotQuote.status == "pending", BotQuote.created_at < cutoff)
        .all()
    )

    for quote in stale_quotes:
        quote.status = "expired"
        mission = db.get(BotMission, quote.mission_id)
        if mission is not None and mission.status == "quoted":
            remaining = (
                db.query(BotQuote)
                .filter(
                    BotQuote.mission_id == mission.mission_id,
                    BotQuote.status == "pending",
                    BotQuote.id != quote.id,
                )
                .count()
            )
            if remaining == 0:
                mission.status = "pending"
                _touch_status(mission)

    db.commit()
    for quote in stale_quotes:
        db.refresh(quote)
    return stale_quotes


# L'argent (paiement, démarrage, fin, libération, litige) vit dans
# backend/app/ledger.py, seule source de vérité : voir CONCEPTION_ARGENT.md.


# Tiers de badge mérités, du plus exigeant au moins exigeant. Le premier dont
# tous les critères sont remplis gagne. En dessous, le prestataire retombe sur
# le badge administratif (`verified` / `pending`).
BADGE_TIERS = (
    ("partner", {"min_missions": 50, "min_rating": 4.7, "min_success_rate": 95.0}),
    ("expert", {"min_missions": 20, "min_rating": 4.5, "min_success_rate": 0.0}),
    ("premium", {"min_missions": 5, "min_rating": 4.0, "min_success_rate": 0.0}),
)

# Statuts de mission qui comptent dans le taux de succès.
_SUCCESS_STATUS = "completed"
_FAILURE_STATUSES = ("disputed", "cancelled")


def _earned_badge(provider: BotProvider) -> str:
    """Badge dérivé des statistiques, ou badge administratif si aucun tier atteint.

    Entièrement recalculé plutôt que cumulatif : un prestataire qui repasse sous
    un seuil (note qui baisse, litige) perd son tier au lieu de le garder à vie.
    """
    for badge, rules in BADGE_TIERS:
        if (
            provider.total_missions >= rules["min_missions"]
            and provider.average_rating >= rules["min_rating"]
            and provider.success_rate >= rules["min_success_rate"]
        ):
            return badge
    return "verified" if provider.is_verified else "pending"


def _recompute_provider_stats(db: Session, provider_telegram_id: int, provider_account_id: int | None = None) -> None:
    """Recalcule note, volume, taux de succès et badge d'un prestataire.

    Tout est recalculé depuis les tables sources (bot_reviews, bot_missions)
    plutôt qu'incrémenté : le résultat ne peut pas dériver si une mission ou un
    avis est corrigé après coup.
    """
    provider = db.get(BotProvider, provider_telegram_id)
    if provider is None:
        return

    provider_account_id = provider_account_id or _account_id_for_telegram(db, provider_telegram_id)

    avg_rating, total_reviews = (
        db.query(func.avg(BotReview.rating), func.count(BotReview.id))
        .filter(or_(BotReview.provider_account_id == provider_account_id, BotReview.provider_telegram_id == provider_telegram_id))
        .one()
    )
    provider.average_rating = round(float(avg_rating), 1) if avg_rating is not None else 0.0
    provider.total_reviews = total_reviews or 0

    status_counts = dict(
        db.query(BotMission.status, func.count(BotMission.mission_id))
        .filter(or_(BotMission.provider_account_id == provider_account_id, BotMission.provider_telegram_id == provider_telegram_id))
        .group_by(BotMission.status)
        .all()
    )
    completed = status_counts.get(_SUCCESS_STATUS, 0)
    failed = sum(status_counts.get(status, 0) for status in _FAILURE_STATUSES)

    provider.total_missions = completed
    # Aucune mission conclue : on n'a rien à reprocher au prestataire, mais rien
    # à porter à son crédit non plus. Voir la note sur le matching dans
    # V5_MIGRATION_PLAN.md — 100 % ici vaut "aucun échec", pas "excellent".
    provider.success_rate = round(completed / (completed + failed) * 100, 2) if (completed + failed) else 100.0

    provider.badge = _earned_badge(provider)

    db.commit()
    db.refresh(provider)


def create_review(
    db: Session,
    mission_id: int,
    client_telegram_id: int,
    rating: int,
    comment: str | None = None,
) -> BotReview:
    mission = db.get(BotMission, mission_id)
    if mission is None:
        raise ValueError("Mission introuvable")
    client_account_id = _account_id_for_telegram(db, client_telegram_id)
    mission_client_account_id = mission.client_account_id or _account_id_for_telegram(db, mission.telegram_id)
    if mission_client_account_id != client_account_id:
        raise ValueError("Ce client n'est pas associé à cette mission")
    if mission.provider_telegram_id is None:
        raise ValueError("Aucun prestataire associé à cette mission")
    if rating < 1 or rating > 5:
        raise ValueError("La note doit être comprise entre 1 et 5")

    existing = db.query(BotReview).filter(BotReview.mission_id == mission_id).first()
    if existing is not None:
        raise ValueError("Cette mission a déjà été évaluée")

    review = BotReview(
        mission_id=mission_id,
        client_telegram_id=client_telegram_id,
        provider_telegram_id=mission.provider_telegram_id,
        client_account_id=client_account_id,
        provider_account_id=mission.provider_account_id or _account_id_for_telegram(db, mission.provider_telegram_id),
        rating=rating,
        comment=comment or None,
    )
    db.add(review)
    db.commit()
    db.refresh(review)

    _recompute_provider_stats(db, mission.provider_telegram_id, review.provider_account_id)
    return review


def find_missions_awaiting_confirmation_since(db: Session, older_than_hours: int = 24) -> list[BotMission]:
    """Missions en `awaiting_confirmation` depuis plus de `older_than_hours`.

    Base pour l'auto-libération d'escrow (Phase 2) : le client n'a ni confirmé
    ni contesté, on libère automatiquement au bout du délai.
    """
    cutoff = datetime.utcnow() - timedelta(hours=older_than_hours)
    return (
        db.query(BotMission)
        .filter(BotMission.status == "awaiting_confirmation", BotMission.status_changed_at < cutoff)
        .all()
    )


def find_missions_needing_reminder(db: Session) -> dict[str, list[BotMission]]:
    """Missions encore `pending` (aucun devis) depuis 10 ou 20 minutes.

    Marque le palier comme envoyé (`reminder_sent_10min`/`reminder_sent_20min`)
    avant de retourner les listes, pour qu'un appel répété de la tâche
    périodique ne relance pas deux fois la même mission dans la même fenêtre.
    """
    now = datetime.utcnow()
    first_tier_cutoff = now - timedelta(minutes=10)
    second_tier_cutoff = now - timedelta(minutes=20)

    first_tier = (
        db.query(BotMission)
        .filter(
            BotMission.status == "pending",
            BotMission.created_at < first_tier_cutoff,
            BotMission.reminder_sent_10min.is_(False),
        )
        .all()
    )
    for mission in first_tier:
        mission.reminder_sent_10min = True

    second_tier = (
        db.query(BotMission)
        .filter(
            BotMission.status == "pending",
            BotMission.created_at < second_tier_cutoff,
            BotMission.reminder_sent_20min.is_(False),
        )
        .all()
    )
    for mission in second_tier:
        mission.reminder_sent_20min = True

    db.commit()
    return {"first": first_tier, "second": second_tier}


def _service_request_to_dict(req: BotServiceRequest, provider: BotProvider | None = None) -> dict:
    data = {
        "id": req.id,
        "provider_telegram_id": req.provider_telegram_id,
        "provider_account_id": req.provider_account_id,
        "service_name": req.service_name,
        "description": req.description,
        "status": req.status,
        "admin_note": req.admin_note,
        "created_at": req.created_at.isoformat() if req.created_at else None,
        "reviewed_at": req.reviewed_at.isoformat() if req.reviewed_at else None,
    }
    if provider is not None:
        data["provider_name"] = provider.full_name
    return data


def create_service_request(
    db: Session,
    provider_telegram_id: int,
    service_name: str,
    description: str = "",
) -> BotServiceRequest:
    provider = db.get(BotProvider, provider_telegram_id)
    if provider is None:
        raise ValueError("Prestataire introuvable")
    req = BotServiceRequest(
        provider_telegram_id=provider_telegram_id,
        provider_account_id=_account_id_for_telegram(db, provider_telegram_id),
        service_name=service_name,
        description=description,
        status="pending",
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


def get_provider_service_requests(db: Session, provider_telegram_id: int) -> list[BotServiceRequest]:
    return (
        db.query(BotServiceRequest)
        .filter(BotServiceRequest.provider_telegram_id == provider_telegram_id)
        .order_by(BotServiceRequest.id.desc())
        .limit(10)
        .all()
    )


def get_pending_service_requests(db: Session, limit: int = 10) -> list[tuple[BotServiceRequest, BotProvider]]:
    return (
        db.query(BotServiceRequest, BotProvider)
        .join(BotProvider, BotProvider.telegram_id == BotServiceRequest.provider_telegram_id)
        .filter(BotServiceRequest.status == "pending")
        .order_by(BotServiceRequest.id.asc())
        .limit(limit)
        .all()
    )


def get_service_request_by_id(db: Session, request_id: int) -> tuple[BotServiceRequest, BotProvider] | None:
    return (
        db.query(BotServiceRequest, BotProvider)
        .join(BotProvider, BotProvider.telegram_id == BotServiceRequest.provider_telegram_id)
        .filter(BotServiceRequest.id == request_id)
        .first()
    )


def update_service_request_status(
    db: Session,
    request_id: int,
    status: str,
    admin_note: str = "",
) -> BotServiceRequest | None:
    if status not in SERVICE_REQUEST_STATUSES:
        raise ValueError("Statut de proposition invalide")
    # UPDATE conditionnel atomique plutôt que SELECT puis check Python : en
    # Postgres, deux PATCH simultanés pouvaient tous les deux lire "pending"
    # avant le commit de l'autre et écraser le résultat sans erreur
    # (ponytail : pas de verrou distribué, une seule colonne à protéger).
    updated = (
        db.query(BotServiceRequest)
        .filter(BotServiceRequest.id == request_id, BotServiceRequest.status == "pending")
        .update({"status": status, "admin_note": admin_note, "reviewed_at": datetime.utcnow()})
    )
    db.commit()
    if updated == 0:
        if db.get(BotServiceRequest, request_id) is None:
            return None
        raise ValueError("Cette proposition a déjà été traitée")
    return db.get(BotServiceRequest, request_id)

