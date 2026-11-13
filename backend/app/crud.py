import math
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app import app_auth, ledger, profils
from backend.app.models import (
    SERVICE_REQUEST_STATUSES,
    BotMission,
    BotQuote,
    DisputeSettlementOffer,
    BotReview,
    DisputeDecision,
    MissionAlert,
    MissionMedia,
    NexisAccount,
    ProviderProfile,
    ProviderServiceRequest,
)


def _touch_status(mission: BotMission) -> None:
    """Marque le moment du changement de statut d'une mission.

    Sert de référence aux relances quand une mission reste sans devis.
    L'auto-libération ne s'en sert pas : elle suit l'échéance `release_after`
    fixée par `ledger.finish_mission`. Appeler juste après toute assignation
    de `mission.status`.
    """
    mission.status_changed_at = datetime.utcnow()


def _account_id_for_telegram(db: Session, telegram_id: int) -> int:
    """Compte canonique d'une identité Telegram vérifiée par le canal."""
    return ledger.account_id_for(db, ledger.TELEGRAM, telegram_id, create=True)


CLIENT_LANGUAGES = profils.LANGUAGES
MAX_DISPLAY_NAME_LENGTH = profils.MAX_NAME_LENGTH


class ClientRefused(ValueError):
    """Refus d'inscription d'un client : code stable pour le canal."""

    def __init__(self, code: str, http_status: int = 409):
        super().__init__(code)
        self.code = code
        self.http_status = http_status


def register_whatsapp_client(
    db: Session, *, bsuid: str, display_name: str, language: str, phone: str | None
) -> tuple[NexisAccount, bool]:
    """Inscrit (ou met à jour) le client qui écrit depuis WhatsApp.

    `bsuid` : identité WhatsApp de l'expéditeur, garantie par Meta (le service
    WhatsApp ne la lit que dans un webhook signé). `phone` : le numéro que
    Meta donne avec le message (`wa_id`), absent si l'utilisateur a masqué son
    numéro derrière un nom d'utilisateur. Il est prouvé par WhatsApp.

    Règles (docs/ARCHITECTURE_WHATSAPP.md, « Règles de liaison ») :

    - identité inconnue, numéro libre ou absent : nouveau compte client, son
      identité `whatsapp` vérifiée, et le numéro prouvé s'il y en a un ;
    - identité inconnue, numéro déjà prouvé sur un autre compte : **refus**
      (`phone_owned_by_account`), rien n'est créé. Le numéro seul ne rattache
      jamais un compte existant ni son argent : la liaison passera par un code
      envoyé sur l'autre canal (étape 9) ;
    - identité connue : nom et langue mis à jour. Le compte reçoit le rôle
      client, jamais le rôle prestataire (aucun parcours prestataire sur
      WhatsApp).

    Ne valide pas : l'appelant valide une seule fois, avec la clé
    d'idempotence (backend/app/idempotency.py). Un refus annule tout ce que la
    demande a écrit. Renvoie (compte, créé)."""
    if language not in CLIENT_LANGUAGES:
        raise ClientRefused("invalid_language", 400)
    display_name = (display_name or "").strip()
    if not display_name or len(display_name) > MAX_DISPLAY_NAME_LENGTH:
        raise ClientRefused("invalid_name", 400)
    try:
        normalized_phone = app_auth.normalize_phone(phone) if phone else None
    except app_auth.AuthError as error:
        raise ClientRefused("invalid_phone", 400) from error

    try:
        account_id = ledger.account_id_for(db, ledger.WHATSAPP, bsuid)
        created = account_id is None
        if created:
            if normalized_phone and app_auth.account_with_proven_phone(db, normalized_phone) is not None:
                _refuse_whatsapp_phone_conflict(db, normalized_phone)
            account_id = ledger.account_id_for(db, ledger.WHATSAPP, bsuid, create=True)
        account = db.get(NexisAccount, account_id, with_for_update=True)
        if account is None:  # défense contre une identité orpheline en base
            raise RuntimeError("Compte Nexis introuvable pour une identité WhatsApp")
        # Rôle client seulement : aucun parcours prestataire sur WhatsApp.
        profils.save_client_profile(db, account_id, first_name=display_name)
        account.language = language
        if normalized_phone and not app_auth.prove_phone(db, account_id, normalized_phone):
            if created:
                # Numéro prouvé par un autre compte entre la première lecture
                # et maintenant : même refus, rien n'est créé.
                _refuse_whatsapp_phone_conflict(db, normalized_phone)
            # Compte déjà connu, mais ce numéro est le numéro prouvé d'un autre
            # compte : on ne déplace rien (événement journalisé par prove_phone).
        db.flush()
        return account, created
    except IntegrityError:
        # Course : même numéro prouvé au même instant par un autre compte
        # (index unique des numéros prouvés).
        _refuse_whatsapp_phone_conflict(db, normalized_phone)


def _refuse_whatsapp_phone_conflict(db: Session, phone: str | None):
    """Annule tout ce que la demande a écrit, journalise le conflit (sans le
    numéro, seulement le compte qui le détient) et refuse."""
    db.rollback()
    holder = app_auth.account_with_proven_phone(db, phone) if phone else None
    app_auth.record_event(db, "whatsapp_phone_conflict", "refused", account_id=holder.id if holder else None)
    db.commit()
    raise ClientRefused("phone_owned_by_account")


MEDIA_KINDS = ("photo", "voice", "video_note")  # 10 caractères au plus (mission_media.kind)
# Une mission reçoit des devis tant qu'aucun n'est accepté.
QUOTABLE_STATUSES = {"pending", "quoted"}
MAX_MISSION_MEDIA = 20
# Prestataires prévenus d'une nouvelle mission : les mieux classés parmi les
# vérifiés, disponibles et non suspendus qui font ce service dans cette commune.
ALERTS_PER_MISSION = 3

# Lieu exact de la mission (CONCEPTION_MISSIONS.md, « Lieu exact de la mission »).
# Rectangle large autour de la ville-province de Kinshasa, seule zone servie :
# il écarte un point manifestement faux (0,0, une autre ville du pays), il ne
# vérifie pas la commune choisie.
SERVICE_AREA = {"min_latitude": -5.2, "max_latitude": -3.4, "min_longitude": 15.0, "max_longitude": 16.7}
DESTINATION_DECIMALS = 6  # environ 11 cm : au-delà, la précision est fictive
MIN_LANDMARK_LENGTH = 3
MAX_LANDMARK_LENGTH = 300
# Le prestataire lit le lieu seulement une fois la mission payée et tant qu'il
# doit s'y rendre ou y travailler.
DESTINATION_PROVIDER_STATUSES = {"confirmed", "in_progress"}


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
    destination_latitude: float | None = None,
    destination_longitude: float | None = None,
    destination_landmark: str | None = None,
) -> tuple[BotMission, bool]:
    """Crée une mission : le backend lui donne son numéro, le client est la
    personne pour qui le canal agit. Mission, médias et prestataires prévenus
    sont écrits dans une seule transaction.

    Le backend choisit seul qui est prévenu (`ALERTS_PER_MISSION` au plus) :
    les prestataires vérifiés, disponibles, non suspendus, qui font ce service
    dans cette commune, du mieux classé au moins bien classé
    (`profils.eligible_providers`). Le canal ne propose personne.

    Le lieu exact (point et repère) est obligatoire : sans lui, le prestataire
    ne sait pas où aller (`invalid_destination` sinon).

    Idempotent : la même `creation_key` pour le même client renvoie la mission
    déjà créée (second élément `False`), ou un refus si la demande diffère.
    Le client n'est jamais prévenu de sa propre mission comme prestataire."""
    media = list(media or [])
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
    if service not in {item.key for item in profils.active_services(db)} or commune not in profils.communes(db):
        raise MissionRefused("invalid_mission", 400)
    latitude, longitude, landmark = checked_destination(destination_latitude, destination_longitude, destination_landmark)

    client_account_id = ledger.account_id_for(db, channel, client_external_id, create=True)
    request = {
        "service": service,
        "commune": commune,
        "currency": currency,
        "description": description,
        "urgent": bool(urgent),
        "destination": (latitude, longitude, landmark),
    }

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
            "destination": (existing.destination_latitude, existing.destination_longitude, existing.destination_landmark),
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
        destination_latitude=latitude,
        destination_longitude=longitude,
        destination_landmark=landmark,
        status="pending",
    )
    db.add(mission)
    db.flush()
    for position, (kind, external_id) in enumerate(media):
        db.add(MissionMedia(mission_id=mission.mission_id, channel=channel, kind=kind, external_id=external_id, position=position))
    alerted = 0
    for provider in profils.eligible_providers(db, service, commune, exclude_account_id=client_account_id):
        if alerted == ALERTS_PER_MISSION:
            break
        # Un prestataire est prévenu sur Telegram (seul canal des prestataires
        # aujourd'hui) : sans identité Telegram, personne ne le préviendrait.
        if ledger.telegram_id_of(db, provider.account_id) is None:
            continue
        db.add(MissionAlert(mission_id=mission.mission_id, provider_account_id=provider.account_id))
        alerted += 1
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


def checked_destination(latitude, longitude, landmark) -> tuple[float, float, str]:
    """Lieu exact d'une nouvelle mission, vérifié : point réel dans la zone
    servie, repère écrit. Refus `invalid_destination` (400) sinon."""
    try:
        latitude = float(latitude)
        longitude = float(longitude)
    except (TypeError, ValueError):
        raise MissionRefused("invalid_destination", 400) from None
    if not (math.isfinite(latitude) and math.isfinite(longitude)):
        raise MissionRefused("invalid_destination", 400)
    area = SERVICE_AREA
    if not (area["min_latitude"] <= latitude <= area["max_latitude"] and area["min_longitude"] <= longitude <= area["max_longitude"]):
        raise MissionRefused("destination_outside_service_area", 400)
    landmark = " ".join((landmark or "").split())
    if not MIN_LANDMARK_LENGTH <= len(landmark) <= MAX_LANDMARK_LENGTH:
        raise MissionRefused("invalid_destination", 400)
    return round(latitude, DESTINATION_DECIMALS), round(longitude, DESTINATION_DECIMALS), landmark


def destination_access(db: Session, mission: BotMission, account_id: int | None, *, is_admin: bool = False) -> str:
    """Qui lit le lieu exact d'une mission.

    - `granted` : l'admin ; le client ; le prestataire choisi d'une mission
      payée (`paid_escrow`) tant qu'elle est `confirmed` ou `in_progress`.
    - `not_yet` : la personne lit la mission mais pas encore son lieu
      (prestataire prévenu, auteur d'un devis, mission pas encore payée,
      terminée ou en litige). Elle garde la commune.
    - `hidden` : la personne ne lit pas la mission (même réponse qu'un numéro
      inconnu)."""
    if is_admin:
        return "granted"
    role = mission_viewer_role(db, mission, account_id)
    if role is None:
        return "hidden"
    if role == "client":
        return "granted"
    if (
        mission.provider_account_id == account_id
        and mission.payment_status == "paid_escrow"
        and mission.status in DESTINATION_PROVIDER_STATUSES
    ):
        return "granted"
    return "not_yet"


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


def pending_service_request_count(db: Session) -> int:
    return db.query(func.count(ProviderServiceRequest.id)).filter(ProviderServiceRequest.status == "pending").scalar() or 0


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
    if profils.provider_profile(db, provider_account_id) is not None:
        # Il a répondu à une mission : ses refus d'affilée repartent de zéro,
        # dans la même transaction que le devis.
        profils.reset_declined_alerts(db, provider_account_id)
    db.commit()
    db.refresh(quote)
    return quote


def decline_alert(db: Session, mission_id: int, provider_account_id: int | None) -> tuple[ProviderProfile, bool]:
    """« Pas disponible » sur une alerte de mission. Le refus compte une seule
    fois par alerte (rejoué, il ne recompte pas : second élément `False`) et
    le compteur de refus d'affilée est tenu par `profils` (pause au 3e).

    Refus : `provider_not_alerted` (403) si cette personne n'a pas été
    prévenue de cette mission, `already_quoted` si elle y a déjà répondu
    par un devis, `mission_not_open` si la mission n'attend plus de devis."""
    alert = (
        db.query(MissionAlert)
        .filter(MissionAlert.mission_id == mission_id, MissionAlert.provider_account_id == provider_account_id)
        .with_for_update()
        .one_or_none()
    )
    if alert is None or profils.provider_profile(db, provider_account_id) is None:
        raise MissionRefused("provider_not_alerted", 403)
    if alert.declined_at is not None:
        return profils.provider_profile(db, provider_account_id), False
    already_quoted = (
        db.query(BotQuote.id)
        .filter(BotQuote.mission_id == mission_id, BotQuote.provider_account_id == provider_account_id)
        .first()
    )
    if already_quoted is not None:
        raise MissionRefused("already_quoted")
    if db.get(BotMission, mission_id).status not in QUOTABLE_STATUSES:
        # Mission déjà attribuée ou close : ce n'est plus un refus de travail.
        raise MissionRefused("mission_not_open")
    alert.declined_at = datetime.utcnow()
    provider = profils.record_declined_alert(db, provider_account_id)
    db.commit()
    return provider, True


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


def _earned_badge(provider: ProviderProfile) -> str:
    """Badge dérivé des statistiques, ou badge administratif si aucun tier atteint.

    Entièrement recalculé plutôt que cumulatif : un prestataire qui repasse sous
    un seuil (note qui baisse, litige) perd son tier au lieu de le garder à vie.
    """
    if not profils.is_verified(provider):
        return "pending"
    for badge, rules in BADGE_TIERS:
        if (
            provider.total_missions >= rules["min_missions"]
            and provider.average_rating >= rules["min_rating"]
            and provider.success_rate >= rules["min_success_rate"]
        ):
            return badge
    return "verified"


def _recompute_provider_stats(db: Session, provider_account_id: int | None) -> None:
    """Recalcule note, volume, taux de succès et badge d'un prestataire.

    Tout est recalculé depuis les tables sources (bot_reviews, bot_missions)
    plutôt qu'incrémenté : le résultat ne peut pas dériver si une mission ou un
    avis est corrigé après coup.
    """
    provider = profils.provider_profile(db, provider_account_id)
    if provider is None:
        return
    # Les lignes d'avant les comptes Nexis ne portent que l'identifiant Telegram.
    provider_telegram_id = ledger.telegram_id_of(db, provider_account_id)
    review_filter = BotReview.provider_account_id == provider_account_id
    mission_filter = BotMission.provider_account_id == provider_account_id
    if provider_telegram_id is not None:
        review_filter = or_(review_filter, BotReview.provider_telegram_id == provider_telegram_id)
        mission_filter = or_(mission_filter, BotMission.provider_telegram_id == provider_telegram_id)

    avg_rating, total_reviews = db.query(func.avg(BotReview.rating), func.count(BotReview.id)).filter(review_filter).one()
    provider.average_rating = round(float(avg_rating), 1) if avg_rating is not None else 0.0
    provider.total_reviews = total_reviews or 0

    status_counts = dict(
        db.query(BotMission.status, func.count(BotMission.mission_id))
        .filter(mission_filter)
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

    _recompute_provider_stats(db, review.provider_account_id)
    return review


def find_missions_due_for_auto_release(db: Session, now: datetime | None = None) -> list[BotMission]:
    """Missions en `awaiting_confirmation` dont l'échéance de libération
    automatique (`release_after`) est passée : le client n'a ni confirmé ni
    signalé de problème dans le délai. `ledger.auto_release` revérifie tout
    sous verrou avant de verser."""
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    return (
        db.query(BotMission)
        .filter(
            BotMission.status == "awaiting_confirmation",
            BotMission.release_after.is_not(None),
            BotMission.release_after <= now,
        )
        .order_by(BotMission.release_after)
        .all()
    )


def find_overdue_disputes(db: Session, now: datetime, realert_after: timedelta) -> list[BotMission]:
    """Litiges qui attendent une décision de Nexis Hub (aucune décision, ou
    décision contestée sans révision) dont le délai de réponse est dépassé et
    qui n'ont pas reçu d'alerte depuis `realert_after`. Une décision prise et
    non contestée n'attend plus personne : elle sera exécutée à son échéance."""
    waiting_for_execution = (
        db.query(DisputeDecision.id)
        .filter(
            DisputeDecision.mission_id == BotMission.mission_id,
            or_(DisputeDecision.contested_at.is_(None), DisputeDecision.round == ledger.REVIEW_DECISION),
        )
        .exists()
    )
    return (
        db.query(BotMission)
        .filter(
            BotMission.status == "disputed",
            BotMission.dispute_deadline.is_not(None),
            BotMission.dispute_deadline <= now,
            or_(
                BotMission.dispute_overdue_alerted_at.is_(None),
                BotMission.dispute_overdue_alerted_at <= now - realert_after,
            ),
            ~waiting_for_execution,
        )
        .order_by(BotMission.dispute_deadline)
        .all()
    )


def find_dispute_decisions_due(db: Session, now: datetime) -> list[DisputeDecision]:
    """Premières décisions de litige non contestées, pas encore exécutées, dont
    le délai de contestation de 3 jours est passé."""
    return (
        db.query(DisputeDecision)
        .filter(
            DisputeDecision.round == ledger.FIRST_DECISION,
            DisputeDecision.contested_at.is_(None),
            DisputeDecision.executed_at.is_(None),
            DisputeDecision.execute_after <= now,
        )
        .order_by(DisputeDecision.execute_after)
        .all()
    )


def find_settlement_offers_expired(db: Session, now: datetime) -> list[DisputeSettlementOffer]:
    """Propositions d'accord amiable encore notées en attente dont
    l'échéance de 48 h est passée."""
    return (
        db.query(DisputeSettlementOffer)
        .filter(DisputeSettlementOffer.status == "pending", DisputeSettlementOffer.expires_at <= now)
        .order_by(DisputeSettlementOffer.expires_at)
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


def create_service_request(
    db: Session,
    provider_account_id: int | None,
    service_name: str,
    description: str = "",
) -> ProviderServiceRequest:
    if profils.provider_profile(db, provider_account_id) is None:
        raise ValueError("Prestataire introuvable")
    req = ProviderServiceRequest(
        provider_account_id=provider_account_id,
        service_name=service_name,
        description=description,
        status="pending",
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


def get_provider_service_requests(db: Session, provider_account_id: int) -> list[ProviderServiceRequest]:
    return (
        db.query(ProviderServiceRequest)
        .filter(ProviderServiceRequest.provider_account_id == provider_account_id)
        .order_by(ProviderServiceRequest.id.desc())
        .limit(10)
        .all()
    )


def get_pending_service_requests(db: Session, limit: int = 10) -> list[tuple[ProviderServiceRequest, ProviderProfile]]:
    return (
        db.query(ProviderServiceRequest, ProviderProfile)
        .join(ProviderProfile, ProviderProfile.account_id == ProviderServiceRequest.provider_account_id)
        .filter(ProviderServiceRequest.status == "pending")
        .order_by(ProviderServiceRequest.id.asc())
        .limit(limit)
        .all()
    )


def get_service_request_by_id(db: Session, request_id: int) -> tuple[ProviderServiceRequest, ProviderProfile] | None:
    return (
        db.query(ProviderServiceRequest, ProviderProfile)
        .join(ProviderProfile, ProviderProfile.account_id == ProviderServiceRequest.provider_account_id)
        .filter(ProviderServiceRequest.id == request_id)
        .first()
    )


def update_service_request_status(
    db: Session,
    request_id: int,
    status: str,
    admin_note: str = "",
) -> ProviderServiceRequest | None:
    if status not in SERVICE_REQUEST_STATUSES:
        raise ValueError("invalid_status")
    # UPDATE conditionnel atomique plutôt que SELECT puis check Python : en
    # Postgres, deux PATCH simultanés pouvaient tous les deux lire "pending"
    # avant le commit de l'autre et écraser le résultat sans erreur
    # (ponytail : pas de verrou distribué, une seule colonne à protéger).
    updated = (
        db.query(ProviderServiceRequest)
        .filter(ProviderServiceRequest.id == request_id, ProviderServiceRequest.status == "pending")
        .update({"status": status, "admin_note": admin_note, "reviewed_at": datetime.utcnow()})
    )
    db.commit()
    if updated == 0:
        if db.get(ProviderServiceRequest, request_id) is None:
            return None
        raise ValueError("already_reviewed")
    return db.get(ProviderServiceRequest, request_id)

