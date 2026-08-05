from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.models import BotMission, BotProvider, BotQuote, BotReview, BotTransaction, BotUser

MODULE_B_SERVICES = {"service_plomberie", "service_electricite", "service_climatisation"}
BADGE_SCORES = {"partner": 30, "expert": 20, "premium": 10, "verified": 5, "pending": 0}


def _compute_module(services: list[str]) -> str:
    return "B" if any(service in MODULE_B_SERVICES for service in services) else "A"


def upsert_user(db: Session, telegram_id: int, first_name: str | None, phone_number: str | None, language: str = "fr") -> BotUser:
    user = db.get(BotUser, telegram_id)
    if user is None:
        user = BotUser(telegram_id=telegram_id)
        db.add(user)
    user.first_name = first_name or "Client"
    user.phone_number = phone_number
    user.language = language
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
            score = BADGE_SCORES.get(provider.badge, 0)
            score += provider.rating * 10
            score += min(provider.total_missions, 50) * 0.2
            if provider.success_rate == 100:
                score += 15
            elif provider.success_rate >= 90:
                score += 8
            matches.append((score, provider))

    matches.sort(key=lambda item: item[0], reverse=True)
    return [provider for _, provider in matches[:3]]


def create_mission(
    db: Session,
    telegram_id: int,
    mission_id: int,
    service: str,
    commune: str,
    currency: str = "USD",
    description: str = "",
    urgent: bool = False,
) -> BotMission:
    mission = BotMission(
        mission_id=mission_id,
        telegram_id=telegram_id,
        service=service,
        commune=commune,
        currency=currency,
        description=description,
        urgent=urgent,
    )
    db.add(mission)
    user = db.get(BotUser, telegram_id)
    if user is not None:
        user.total_missions += 1
    db.commit()
    db.refresh(mission)
    return mission


def create_quote(
    db: Session,
    mission_id: int,
    provider_telegram_id: int,
    amount: float,
    currency: str,
    delay_hours: int,
    message: str = "",
) -> BotQuote | None:
    mission = db.get(BotMission, mission_id)
    if mission is None:
        return None
    quote = BotQuote(
        mission_id=mission_id,
        provider_telegram_id=provider_telegram_id,
        amount=amount,
        currency=currency,
        delay_hours=delay_hours,
        message=message,
    )
    db.add(quote)
    mission.status = "quoted"
    db.commit()
    db.refresh(quote)
    return quote


def accept_quote(db: Session, quote_id: int) -> BotQuote | None:
    quote = db.get(BotQuote, quote_id)
    if quote is None:
        return None

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
        mission.provider_telegram_id = quote.provider_telegram_id

    db.commit()
    db.refresh(quote)
    return quote


def reject_quote(db: Session, quote_id: int) -> BotQuote | None:
    quote = db.get(BotQuote, quote_id)
    if quote is None:
        return None
    quote.status = "rejected"
    db.commit()
    db.refresh(quote)
    return quote


def calculate_payment_amounts(amount: float, currency: str, urgent: bool = False) -> dict:
    # Miroir de db.calculate_payment_amounts : frais Tola supprimés (service
    # indisponible en RDC). Clés conservées à 0.00, les colonnes bot_missions /
    # bot_transactions existent toujours et gardent l'historique.
    commission_rate = 0.15 if urgent else 0.10
    commission_amount = round(amount * commission_rate, 2)
    total_client = round(amount, 2)
    net_provider = round(amount - commission_amount, 2)
    return {
        "commission_amount": commission_amount,
        "tola_fee": 0.00,
        "aggregator_fee": 0.00,
        "total_client": total_client,
        "net_provider": net_provider,
    }


def _apply_escrow_payment(db: Session, quote: BotQuote, mission: BotMission, total_client: float, amounts: dict, mobile_money_ref: str, operator: str) -> BotTransaction:
    transaction = BotTransaction(
        mission_id=mission.mission_id,
        quote_id=quote.id,
        type="escrow_in",
        amount=total_client,
        currency=quote.currency,
        commission_amount=amounts["commission_amount"],
        tola_fee=amounts["tola_fee"],
        aggregator_fee=amounts["aggregator_fee"],
        net_provider=amounts["net_provider"],
        status="success",
        mobile_money_ref=mobile_money_ref,
        operator=operator,
    )
    db.add(transaction)

    mission.payment_status = "paid_escrow"
    mission.commission_amount = amounts["commission_amount"]
    mission.tola_fee = amounts["tola_fee"]
    mission.aggregator_fee = amounts["aggregator_fee"]
    mission.total_client = total_client
    mission.net_provider = amounts["net_provider"]
    mission.status = "confirmed"

    db.commit()
    db.refresh(transaction)
    return transaction


def mark_quote_paid(db: Session, quote_id: int, operator: str = "simulation") -> dict | None:
    quote = db.get(BotQuote, quote_id)
    if quote is None:
        return None
    mission = db.get(BotMission, quote.mission_id)
    if mission is None:
        return None

    amounts = calculate_payment_amounts(amount=quote.amount, currency=quote.currency, urgent=mission.urgent)
    mobile_money_ref = f"SIM-{quote_id:04d}"
    transaction = _apply_escrow_payment(db, quote, mission, amounts["total_client"], amounts, mobile_money_ref, operator)

    return {
        "transaction_id": transaction.id,
        "mobile_money_ref": mobile_money_ref,
        "operator": operator,
        "status": "success",
        **amounts,
    }


def mark_quote_paid_with_wallet(db: Session, quote_id: int, operator: str = "wallet") -> dict:
    quote = db.get(BotQuote, quote_id)
    if quote is None:
        raise ValueError("Devis introuvable")
    mission = db.get(BotMission, quote.mission_id)
    if mission is None:
        raise ValueError("Mission introuvable")
    user = db.get(BotUser, mission.telegram_id)
    if user is None:
        raise ValueError("Client introuvable")

    amounts = calculate_payment_amounts(amount=quote.amount, currency=quote.currency, urgent=mission.urgent)
    total_client = amounts["total_client"]
    wallet_balance = user.wallet_balance_usd if quote.currency == "USD" else user.wallet_balance_cdf
    if wallet_balance < total_client:
        raise ValueError("Solde insuffisant sur le wallet")

    if quote.currency == "USD":
        user.wallet_balance_usd -= total_client
    else:
        user.wallet_balance_cdf -= total_client

    mobile_money_ref = f"WLT-{quote_id:04d}"
    transaction = _apply_escrow_payment(db, quote, mission, total_client, amounts, mobile_money_ref, operator)

    return {
        "transaction_id": transaction.id,
        "mobile_money_ref": mobile_money_ref,
        "operator": operator,
        "status": "success",
        **amounts,
    }


def start_mission(db: Session, mission_id: int, provider_telegram_id: int) -> BotMission:
    mission = db.get(BotMission, mission_id)
    if mission is None:
        raise ValueError("Mission introuvable")
    if mission.provider_telegram_id != provider_telegram_id:
        raise ValueError("Ce prestataire n'est pas associé à cette mission")
    if mission.payment_status != "paid_escrow":
        raise ValueError("La mission n'est pas encore payée en escrow")

    mission.status = "in_progress"
    db.commit()
    db.refresh(mission)
    return mission


def finish_mission(db: Session, mission_id: int, provider_telegram_id: int) -> BotMission:
    mission = db.get(BotMission, mission_id)
    if mission is None:
        raise ValueError("Mission introuvable")
    if mission.provider_telegram_id != provider_telegram_id:
        raise ValueError("Ce prestataire n'est pas associé à cette mission")

    mission.status = "awaiting_confirmation"
    db.commit()
    db.refresh(mission)
    return mission


def release_payment(db: Session, mission_id: int) -> BotMission:
    mission = db.get(BotMission, mission_id)
    if mission is None:
        raise ValueError("Mission introuvable")
    if mission.payment_status != "paid_escrow":
        raise ValueError("Aucun paiement escrow à libérer")

    transaction = BotTransaction(
        mission_id=mission.mission_id,
        quote_id=None,
        type="release",
        amount=mission.net_provider,
        currency=mission.currency,
        net_provider=mission.net_provider,
        status="success",
    )
    db.add(transaction)

    if mission.provider_telegram_id is not None:
        provider = db.get(BotProvider, mission.provider_telegram_id)
        if provider is not None:
            if mission.currency == "USD":
                provider.wallet_balance_usd += mission.net_provider
            else:
                provider.wallet_balance_cdf += mission.net_provider

    mission.status = "completed"
    mission.payment_status = "released"
    db.commit()
    db.refresh(mission)
    return mission


def _recompute_provider_rating(db: Session, provider_telegram_id: int) -> None:
    provider = db.get(BotProvider, provider_telegram_id)
    if provider is None:
        return
    avg_rating, total = (
        db.query(func.avg(BotReview.rating), func.count(BotReview.id))
        .filter(BotReview.provider_telegram_id == provider_telegram_id)
        .one()
    )
    provider.average_rating = round(float(avg_rating), 1) if avg_rating is not None else 0.0
    provider.total_reviews = total or 0
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
    if mission.telegram_id != client_telegram_id:
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
        rating=rating,
        comment=comment or None,
    )
    db.add(review)
    db.commit()
    db.refresh(review)

    _recompute_provider_rating(db, mission.provider_telegram_id)
    return review
