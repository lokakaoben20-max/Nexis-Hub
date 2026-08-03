from datetime import datetime

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database import Base


class BotUser(Base):
    __tablename__ = "bot_users"

    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    language: Mapped[str] = mapped_column(String(5), default="fr")
    wallet_balance_usd: Mapped[float] = mapped_column(Float, default=0.0)
    wallet_balance_cdf: Mapped[float] = mapped_column(Float, default=0.0)
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
    wallet_balance_usd: Mapped[float] = mapped_column(Float, default=0.0)
    wallet_balance_cdf: Mapped[float] = mapped_column(Float, default=0.0)


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


class BotQuote(Base):
    __tablename__ = "bot_quotes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mission_id: Mapped[int] = mapped_column(ForeignKey("bot_missions.mission_id"), index=True)
    provider_telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    delay_hours: Mapped[int] = mapped_column(Integer)
    message: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="pending")


class BotTransaction(Base):
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
