import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://nexis_user:nexis_password@localhost:5432/nexis_hub",
)

_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=_connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    """Crée toutes les tables d'un coup, avec le catalogue initial (comme la
    migration qui le crée) : réservé aux bases jetables des tests. Une vraie
    base passe par Alembic (`alembic upgrade head`)."""
    from backend.app import catalogue_initial

    Base.metadata.create_all(bind=engine)
    with engine.begin() as connection:
        from sqlalchemy import text

        if connection.execute(text("SELECT COUNT(*) FROM services")).scalar_one() == 0:
            catalogue_initial.remplir(connection)
