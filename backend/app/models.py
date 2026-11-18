"""Initial PostgreSQL domain models (opt-in, not wired to live API).

IDs and relationships mirror SQLite. Provider identity remains independent from
User until the cross-channel identity reconciliation is designed.
"""
from decimal import Decimal

from sqlalchemy import BigInteger, ForeignKey, Identity, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.postgres import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    phone_number: Mapped[str] = mapped_column(Text, nullable=False)
    first_name: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(10), default="fr", nullable=False)
    wallet_balance_usd: Mapped[Decimal] = mapped_column(Numeric(20, 4), default=Decimal("0"), nullable=False)
    wallet_balance_cdf: Mapped[Decimal] = mapped_column(Numeric(20, 4), default=Decimal("0"), nullable=False)
    channel: Mapped[str | None] = mapped_column(Text)
    commune: Mapped[str | None] = mapped_column(Text)
    preferred_currency: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[int | None] = mapped_column(Integer)
    total_missions: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[str | None] = mapped_column(Text)


class Provider(Base):
    __tablename__ = "providers"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    phone_number: Mapped[str] = mapped_column(Text, nullable=False)
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    services: Mapped[str] = mapped_column(Text, nullable=False)
    communes: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="available", nullable=False)
    wallet_balance_usd: Mapped[Decimal] = mapped_column(Numeric(20, 4), default=Decimal("0"), nullable=False)
    wallet_balance_cdf: Mapped[Decimal] = mapped_column(Numeric(20, 4), default=Decimal("0"), nullable=False)
    is_verified: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[int | None] = mapped_column(Integer)
    is_suspended: Mapped[int | None] = mapped_column(Integer)
    badge: Mapped[str | None] = mapped_column(Text)
    id_document_url: Mapped[str | None] = mapped_column(Text)
    portfolio_urls: Mapped[str | None] = mapped_column(Text)
    subscription: Mapped[str | None] = mapped_column(Text)
    preferred_currency: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str | None] = mapped_column(Text)


class Mission(Base):
    __tablename__ = "missions"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    provider_id: Mapped[int | None] = mapped_column(ForeignKey("providers.id"))
    service: Mapped[str] = mapped_column(Text, nullable=False)
    commune: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="pending", nullable=False)
    payment_status: Mapped[str] = mapped_column(String(40), default="unpaid", nullable=False)
    total_client: Mapped[Decimal] = mapped_column(Numeric(20, 4), default=Decimal("0"), nullable=False)
    net_provider: Mapped[Decimal] = mapped_column(Numeric(20, 4), default=Decimal("0"), nullable=False)
    channel: Mapped[str | None] = mapped_column(Text)
    service_id: Mapped[int | None] = mapped_column(BigInteger)
    address_details: Mapped[str | None] = mapped_column(Text)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    amount_usd_equiv: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    commission_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    tola_fee: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    aggregator_fee: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    payment_ref: Mapped[str | None] = mapped_column(Text)
    dispute_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str | None] = mapped_column(Text)


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    mission_id: Mapped[int] = mapped_column(ForeignKey("missions.id"), nullable=False)
    quote_id: Mapped[int | None] = mapped_column(ForeignKey("quotes.id"))
    type: Mapped[str] = mapped_column(Text, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="pending", nullable=False)
    mobile_money_ref: Mapped[str | None] = mapped_column(Text)
    amount_usd_equiv: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    commission_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    tola_fee: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    net_provider: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    aggregator_fee: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    operator: Mapped[str | None] = mapped_column(Text)
    phone_number: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str | None] = mapped_column(Text)


class Quote(Base):
    __tablename__ = "quotes"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    mission_id: Mapped[int] = mapped_column(ForeignKey("missions.id"), nullable=False)
    provider_id: Mapped[int] = mapped_column(ForeignKey("providers.id"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    currency: Mapped[str] = mapped_column(Text, nullable=False)
    delay_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    message: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str | None] = mapped_column(Text)
    amount_usd_equiv: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))


class Service(Base):
    __tablename__ = "services"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    key: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name_fr: Mapped[str] = mapped_column(Text, nullable=False)
    name_ln: Mapped[str | None] = mapped_column(Text)
    name_en: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(Text)
    icon_emoji: Mapped[str | None] = mapped_column(Text)
    module: Mapped[str] = mapped_column(Text, nullable=False)
    requires_inspection: Mapped[int | None] = mapped_column(Integer)
    visit_fee_usd: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    is_active: Mapped[int | None] = mapped_column(Integer)


class ServiceRequest(Base):
    __tablename__ = "service_requests"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    provider_id: Mapped[int] = mapped_column(ForeignKey("providers.id"), nullable=False)
    service_name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str | None] = mapped_column(Text)
    admin_note: Mapped[str | None] = mapped_column(Text)


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    mission_id: Mapped[int] = mapped_column(ForeignKey("missions.id"), unique=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    provider_id: Mapped[int] = mapped_column(ForeignKey("providers.id"), nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    was_punctual: Mapped[int | None] = mapped_column(Integer)
    was_professional: Mapped[int | None] = mapped_column(Integer)
    was_resolved: Mapped[int | None] = mapped_column(Integer)
    comment: Mapped[str | None] = mapped_column(Text)
    is_public: Mapped[int | None] = mapped_column(Integer)


class PlatformSetting(Base):
    __tablename__ = "platform_settings"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
