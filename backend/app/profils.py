"""Profils clients et prestataires : seule source des règles.

Le backend est la seule mémoire des profils (chantier « profils au backend »).
Tout se range par compte Nexis (`accounts.id`) : un profil client et un
profil prestataire au plus par compte, quel que soit le canal. Les fonctions
ci-dessous écrivent dans la session sans la valider : l'appelant (une route)
fait `commit()` une fois toute la demande appliquée, ou `rollback()` sur un
refus. Un refus est toujours un `ProfileRefused`, avec un code stable que les
canaux traduisent.

Statuts d'un prestataire (contrainte `ck_provider_profiles_verified_status`) :

    (inscription) ──> pending_verification ──admin──> available (vérifié)
                              │  ^                       ↕ la personne
                         admin│  │réinscription        offline
                              v  │                       │
                           rejected            available ──3 refus──> paused
                                               paused ──la personne──> available / offline

La suspension par l'admin est un drapeau à part : elle ne change pas le
statut, qui est retrouvé tel quel au rétablissement. Une réinscription ou une
modification de profil ne change jamais le statut d'un prestataire vérifié.

Éligible à une mission = vérifié, `available`, non suspendu, qui propose ce
service dans cette commune, et qui n'est pas le client lui-même.
"""

from datetime import datetime

from sqlalchemy import case, select, update
from sqlalchemy.orm import Session

from backend.app import app_auth
from backend.app.models import (
    ClientProfile,
    Commune,
    NexisAccount,
    ProviderCommune,
    ProviderProfile,
    ProviderService,
    Service,
)

LANGUAGES = ("fr", "ln", "en")
MAX_NAME_LENGTH = 100
MAX_PHONE_LENGTH = 50
MAX_FILE_ID_LENGTH = 255
MAX_PORTFOLIO_FILES = 20

# Statuts qu'un prestataire vérifié se donne lui-même.
SELF_STATUSES = ("available", "offline")
# Au 3e refus de mission d'affilée, le prestataire disponible passe en pause.
MAX_CONSECUTIVE_DECLINES = 3

# Classement des prestataires éligibles.
BADGE_SCORES = {"partner": 30, "expert": 20, "premium": 10, "verified": 5, "pending": 0}
# Nombre de missions terminées à partir duquel le taux de succès devient un
# signal exploitable (en dessous, il n'est pas représentatif).
MIN_MISSIONS_FOR_SUCCESS_BONUS = 3


class ProfileRefused(ValueError):
    """Refus métier sur un profil : code stable pour le canal."""

    def __init__(self, code: str, http_status: int = 409):
        super().__init__(code)
        self.code = code
        self.http_status = http_status


def _now() -> datetime:
    return datetime.utcnow()


# --- Catalogue ---------------------------------------------------------------


def active_services(db: Session) -> list[Service]:
    return db.query(Service).filter(Service.is_active.is_(True)).order_by(Service.position).all()


def service_label(service: Service, language: str) -> str:
    return {"fr": service.name_fr, "ln": service.name_ln, "en": service.name_en}.get(language, service.name_fr)


def communes(db: Session) -> list[str]:
    return [commune.name for commune in db.query(Commune).order_by(Commune.position).all()]


def _checked_services(db: Session, service_keys) -> list[str]:
    keys = _unique_strings(service_keys, "invalid_services")
    if not keys:
        raise ProfileRefused("services_required", 400)
    known = {service.key for service in active_services(db)}
    if any(key not in known for key in keys):
        raise ProfileRefused("unknown_service", 400)
    return keys


def _checked_communes(db: Session, commune_names) -> list[str]:
    names = _unique_strings(commune_names, "invalid_communes")
    if not names:
        raise ProfileRefused("communes_required", 400)
    known = set(communes(db))
    if any(name not in known for name in names):
        raise ProfileRefused("unknown_commune", 400)
    return names


def _unique_strings(values, refusal: str) -> list[str]:
    if not isinstance(values, (list, tuple)) or any(not isinstance(value, str) for value in values):
        raise ProfileRefused(refusal, 400)
    unique = []
    for value in values:
        if value not in unique:
            unique.append(value)
    return unique


def _checked_name(name) -> str:
    name = " ".join(str(name or "").split())
    if not name or len(name) > MAX_NAME_LENGTH:
        raise ProfileRefused("invalid_name", 400)
    return name


def _checked_phone(phone) -> str | None:
    if phone is None:
        return None
    phone = str(phone).strip()
    if not phone:
        return None
    if len(phone) > MAX_PHONE_LENGTH:
        raise ProfileRefused("invalid_phone", 400)
    return phone


def _checked_language(language) -> str:
    if language not in LANGUAGES:
        raise ProfileRefused("invalid_language", 400)
    return language


def _checked_file_id(file_id) -> str:
    if not isinstance(file_id, str) or not file_id or len(file_id) > MAX_FILE_ID_LENGTH:
        raise ProfileRefused("invalid_document", 400)
    return file_id


# --- Compte ------------------------------------------------------------------


def _locked_account(db: Session, account_id: int) -> NexisAccount:
    account = db.get(NexisAccount, account_id, with_for_update=True)
    if account is None:
        raise ProfileRefused("account_not_found", 404)
    return account


def _add_role(account: NexisAccount, role: str) -> None:
    account.roles = sorted(set(account.roles or []) | {role})


def language_of(db: Session, account_id: int | None) -> str:
    """Langue de la personne ; « fr » pour un compte inconnu."""
    account = db.get(NexisAccount, account_id) if account_id is not None else None
    return account.language if account is not None and account.language in LANGUAGES else "fr"


def set_language(db: Session, account_id: int, language: str) -> NexisAccount:
    """Une seule langue par personne, pour tous ses rôles et canaux."""
    account = _locked_account(db, account_id)
    account.language = _checked_language(language)
    return account


def record_proven_phone(db: Session, account_id: int, phone_number: str | None) -> None:
    """Numéro prouvé par le canal (contact de l'expéditeur sur Telegram) :
    enregistré sur le compte. Un numéro déjà prouvé sur un autre compte reste
    où il est (`app_auth.prove_phone`, qui journalise le conflit)."""
    if not phone_number:
        return
    try:
        app_auth.prove_phone(db, account_id, phone_number)
    except app_auth.AuthError:
        return


# --- Client ------------------------------------------------------------------


def client_profile(db: Session, account_id: int | None) -> ClientProfile | None:
    return db.get(ClientProfile, account_id) if account_id is not None else None


def save_client_profile(db: Session, account_id: int, *, first_name, phone_number=None) -> tuple[ClientProfile, bool]:
    """Crée ou met à jour le profil client. Renvoie (profil, créé)."""
    account = _locked_account(db, account_id)
    first_name = _checked_name(first_name)
    phone_number = _checked_phone(phone_number)
    profile = db.get(ClientProfile, account_id)
    created = profile is None
    if created:
        profile = ClientProfile(account_id=account_id, created_at=_now())
        db.add(profile)
    profile.first_name = first_name
    if phone_number is not None:
        profile.phone_number = phone_number
    profile.updated_at = _now()
    _add_role(account, "client")
    db.flush()
    return profile, created


def rename_client(db: Session, account_id: int, first_name) -> ClientProfile:
    profile = db.get(ClientProfile, account_id, with_for_update=True)
    if profile is None:
        raise ProfileRefused("client_not_found", 404)
    profile.first_name = _checked_name(first_name)
    profile.updated_at = _now()
    db.flush()
    return profile


# --- Prestataire : lecture ---------------------------------------------------


def provider_profile(db: Session, account_id: int | None) -> ProviderProfile | None:
    return db.get(ProviderProfile, account_id) if account_id is not None else None


def _locked_provider(db: Session, account_id: int | None) -> ProviderProfile:
    provider = db.get(ProviderProfile, account_id, with_for_update=True) if account_id is not None else None
    if provider is None:
        raise ProfileRefused("provider_not_found", 404)
    return provider


def provider_services(db: Session, account_id: int) -> list[str]:
    return list(
        db.scalars(
            select(ProviderService.service_key)
            .join(Service, Service.key == ProviderService.service_key)
            .where(ProviderService.account_id == account_id)
            .order_by(Service.position)
        )
    )


def provider_communes(db: Session, account_id: int) -> list[str]:
    return list(
        db.scalars(
            select(ProviderCommune.commune)
            .join(Commune, Commune.name == ProviderCommune.commune)
            .where(ProviderCommune.account_id == account_id)
            .order_by(Commune.position)
        )
    )


def provider_module(db: Session, account_id: int) -> str:
    """Module B si le prestataire propose au moins un service à visite."""
    module_b = db.scalar(
        select(Service.key)
        .join(ProviderService, ProviderService.service_key == Service.key)
        .where(ProviderService.account_id == account_id, Service.module == "B")
        .limit(1)
    )
    return "B" if module_b is not None else "A"


def is_verified(provider: ProviderProfile) -> bool:
    return provider.verified_at is not None


# --- Prestataire : inscription et profil -------------------------------------


def register_provider(
    db: Session,
    account_id: int,
    *,
    full_name,
    phone_number,
    services,
    communes,
    id_document_file_id=None,
    selfie_file_id=None,
    portfolio_file_ids=None,
) -> tuple[ProviderProfile, bool]:
    """Inscription, ou nouvelle inscription, d'un prestataire.

    - nouveau : `pending_verification`, invisible du matching jusqu'à la
      validation de l'admin ;
    - refusé qui se réinscrit : repasse `pending_verification` (nouvelle
      demande de vérification) ;
    - en attente ou vérifié : nom, numéro, services, communes et documents
      mis à jour, **statut inchangé**.

    Documents absents (None) : ceux déjà fournis sont gardés. Renvoie
    (profil, créé)."""
    account = _locked_account(db, account_id)
    full_name = _checked_name(full_name)
    phone_number = _checked_phone(phone_number)
    service_keys = _checked_services(db, services)
    commune_names = _checked_communes(db, communes)
    if id_document_file_id is not None:
        id_document_file_id = _checked_file_id(id_document_file_id)
    if selfie_file_id is not None:
        selfie_file_id = _checked_file_id(selfie_file_id)
    if portfolio_file_ids is not None:
        if not isinstance(portfolio_file_ids, (list, tuple)) or len(portfolio_file_ids) > MAX_PORTFOLIO_FILES:
            raise ProfileRefused("invalid_document", 400)
        portfolio_file_ids = [_checked_file_id(file_id) for file_id in portfolio_file_ids]

    provider = db.get(ProviderProfile, account_id, with_for_update=True)
    created = provider is None
    if created:
        provider = ProviderProfile(
            account_id=account_id,
            status="pending_verification",
            verified_at=None,
            is_suspended=False,
            suspended_at=None,
            badge="pending",
            average_rating=0.0,
            total_reviews=0,
            total_missions=0,
            success_rate=0.0,
            consecutive_ignored=0,
            portfolio_file_ids=[],
            created_at=_now(),
        )
        db.add(provider)
    elif provider.status == "rejected":
        provider.status = "pending_verification"
    provider.full_name = full_name
    if phone_number is not None:
        provider.phone_number = phone_number
    if id_document_file_id is not None:
        provider.id_document_file_id = id_document_file_id
    if selfie_file_id is not None:
        provider.selfie_file_id = selfie_file_id
    if portfolio_file_ids is not None:
        provider.portfolio_file_ids = portfolio_file_ids
    provider.updated_at = _now()
    _add_role(account, "provider")
    db.flush()
    _replace_services(db, account_id, service_keys)
    _replace_communes(db, account_id, commune_names)
    return provider, created


def set_provider_services(db: Session, account_id: int, services) -> ProviderProfile:
    provider = _locked_provider(db, account_id)
    _replace_services(db, account_id, _checked_services(db, services))
    provider.updated_at = _now()
    db.flush()
    return provider


def set_provider_communes(db: Session, account_id: int, communes) -> ProviderProfile:
    provider = _locked_provider(db, account_id)
    _replace_communes(db, account_id, _checked_communes(db, communes))
    provider.updated_at = _now()
    db.flush()
    return provider


def _replace_services(db: Session, account_id: int, service_keys: list[str]) -> None:
    db.query(ProviderService).filter(ProviderService.account_id == account_id).delete(synchronize_session=False)
    db.add_all(ProviderService(account_id=account_id, service_key=key) for key in service_keys)
    db.flush()


def _replace_communes(db: Session, account_id: int, commune_names: list[str]) -> None:
    db.query(ProviderCommune).filter(ProviderCommune.account_id == account_id).delete(synchronize_session=False)
    db.add_all(ProviderCommune(account_id=account_id, commune=name) for name in commune_names)
    db.flush()


# --- Prestataire : statuts ---------------------------------------------------


def set_own_availability(db: Session, account_id: int, status: str) -> ProviderProfile:
    """Le prestataire se met disponible ou hors ligne. Seulement s'il est
    vérifié et non suspendu. Quitter la pause (3 refus) remet le compteur de
    refus à zéro : sinon un seul refus de plus le remettrait en pause."""
    if status not in SELF_STATUSES:
        raise ProfileRefused("status_not_allowed", 400)
    provider = _locked_provider(db, account_id)
    if not is_verified(provider):
        raise ProfileRefused("provider_not_verified")
    if provider.is_suspended:
        raise ProfileRefused("provider_suspended")
    if provider.status == "paused":
        provider.consecutive_ignored = 0
    provider.status = status
    provider.updated_at = _now()
    db.flush()
    return provider


def verify_provider(db: Session, account_id: int) -> ProviderProfile:
    """Validation par l'admin : le prestataire devient vérifié et disponible.
    Déjà vérifié : rien ne change (même réponse). Refusé : il doit d'abord se
    réinscrire (nouvelle demande)."""
    provider = _locked_provider(db, account_id)
    if is_verified(provider):
        return provider
    if provider.status != "pending_verification":
        raise ProfileRefused("provider_not_pending")
    provider.verified_at = _now()
    provider.status = "available"
    if provider.badge == "pending":
        provider.badge = "verified"
    provider.updated_at = _now()
    db.flush()
    return provider


def reject_provider(db: Session, account_id: int) -> ProviderProfile:
    """Refus par l'admin d'un prestataire en attente. Déjà refusé : rien ne
    change. Un prestataire vérifié ne se « refuse » pas : on le suspend."""
    provider = _locked_provider(db, account_id)
    if provider.status == "rejected":
        return provider
    if provider.status != "pending_verification":
        raise ProfileRefused("provider_not_pending")
    provider.status = "rejected"
    provider.updated_at = _now()
    db.flush()
    return provider


def set_suspended(db: Session, account_id: int, suspended: bool) -> ProviderProfile:
    """Suspension ou rétablissement par l'admin. Idempotent."""
    provider = _locked_provider(db, account_id)
    if provider.is_suspended != suspended:
        provider.is_suspended = suspended
        provider.suspended_at = _now() if suspended else None
        provider.updated_at = _now()
        db.flush()
    return provider


def record_declined_alert(db: Session, account_id: int) -> ProviderProfile:
    """Le prestataire refuse une mission dont il a été prévenu. Une seule
    instruction : deux refus simultanés comptent pour deux, et la mise en
    pause au 3e refus d'affilée ne peut pas être manquée."""
    _locked_provider(db, account_id)
    next_count = ProviderProfile.consecutive_ignored + 1
    db.execute(
        update(ProviderProfile)
        .where(ProviderProfile.account_id == account_id)
        .values(
            consecutive_ignored=next_count,
            status=case(
                (
                    (ProviderProfile.status == "available") & (next_count >= MAX_CONSECUTIVE_DECLINES),
                    "paused",
                ),
                else_=ProviderProfile.status,
            ),
            updated_at=_now(),
        )
        .execution_options(synchronize_session=False)
    )
    provider = db.get(ProviderProfile, account_id)
    db.refresh(provider)
    return provider


def reset_declined_alerts(db: Session, account_id: int) -> ProviderProfile:
    """Le prestataire a répondu à une mission (devis) : compteur à zéro."""
    provider = _locked_provider(db, account_id)
    if provider.consecutive_ignored:
        provider.consecutive_ignored = 0
        provider.updated_at = _now()
        db.flush()
    return provider


# --- Matching ----------------------------------------------------------------


def matching_score(provider: ProviderProfile) -> float:
    score = BADGE_SCORES.get(provider.badge, 0)
    score += (provider.average_rating or 0.0) * 10
    score += min(provider.total_missions or 0, 50) * 0.2
    # Le bonus de fiabilité demande un minimum d'historique : sans lui, un
    # prestataire sans aucune mission partait à égalité avec un vétéran.
    if (provider.total_missions or 0) >= MIN_MISSIONS_FOR_SUCCESS_BONUS:
        if provider.success_rate == 100:
            score += 15
        elif provider.success_rate >= 90:
            score += 8
    return score


def eligible_providers(
    db: Session, service: str, commune: str, *, exclude_account_id: int | None = None
) -> list[ProviderProfile]:
    """Prestataires à qui proposer une mission, du mieux classé au moins bien
    classé (à égalité, le plus ancien inscrit d'abord)."""
    query = (
        select(ProviderProfile)
        .join(ProviderService, ProviderService.account_id == ProviderProfile.account_id)
        .join(ProviderCommune, ProviderCommune.account_id == ProviderProfile.account_id)
        .where(
            ProviderService.service_key == service,
            ProviderCommune.commune == commune,
            ProviderProfile.status == "available",
            ProviderProfile.verified_at.is_not(None),
            ProviderProfile.is_suspended.is_(False),
        )
        .order_by(ProviderProfile.created_at, ProviderProfile.account_id)
    )
    if exclude_account_id is not None:
        query = query.where(ProviderProfile.account_id != exclude_account_id)
    providers = list(db.scalars(query))
    # Tri stable : l'ordre d'inscription départage les égalités.
    providers.sort(key=lambda provider: -matching_score(provider))
    return providers


def rank(db: Session, account_ids: list[int]) -> list[int]:
    """Classe des prestataires déjà choisis par l'appelant, au score seul.
    Les comptes sans profil prestataire sont omis ; à égalité, l'ordre reçu."""
    if not account_ids:
        return []
    providers = db.scalars(select(ProviderProfile).where(ProviderProfile.account_id.in_(account_ids))).all()
    position = {account_id: index for index, account_id in enumerate(account_ids)}
    ordered = sorted(providers, key=lambda provider: (-matching_score(provider), position[provider.account_id]))
    return [provider.account_id for provider in ordered]

