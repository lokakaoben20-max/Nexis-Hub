"""Profils de test : créés par les règles de `profils`, comme en vrai.

Une base créée par `create_all` seul n'a pas de catalogue : il est rempli ici
au besoin, avec le contenu de la migration (`catalogue_initial`)."""

from sqlalchemy import text

from backend.app import catalogue_initial, ledger, profils


def ensure_catalogue(db) -> None:
    if not db.execute(text("SELECT COUNT(*) FROM services")).scalar_one():
        catalogue_initial.remplir(db.connection())
        db.flush()


def client(db, telegram_id: int, first_name: str = "Client", language: str = "fr") -> int:
    """Profil client d'une personne connue par Telegram. Renvoie son compte."""
    account_id = ledger.account_id_for(db, ledger.TELEGRAM, telegram_id, create=True)
    profils.save_client_profile(db, account_id, first_name=first_name)
    profils.set_language(db, account_id, language)
    db.commit()
    return account_id


def provider(
    db,
    telegram_id: int,
    full_name: str = "Prestataire",
    *,
    services=("service_plomberie",),
    communes=("Gombe",),
    verified: bool = True,
    language: str = "fr",
    **stats,
):
    """Profil prestataire (vérifié par défaut, donc disponible). `stats` :
    colonnes à fixer ensuite (note, missions, badge...)."""
    ensure_catalogue(db)
    account_id = ledger.account_id_for(db, ledger.TELEGRAM, telegram_id, create=True)
    profile, _ = profils.register_provider(
        db, account_id, full_name=full_name, phone_number=None, services=list(services), communes=list(communes)
    )
    profils.set_language(db, account_id, language)
    if verified:
        profile = profils.verify_provider(db, account_id)
    for name, value in stats.items():
        setattr(profile, name, value)
    db.commit()
    return profile


def admin(db, telegram_id: int):
    from backend.app import admins

    return admins.grant(db, telegram_id, "Admin de test")


def provider_of(db, telegram_id: int):
    return profils.provider_profile(db, ledger.account_id_for(db, ledger.TELEGRAM, telegram_id))


def client_of(db, telegram_id: int):
    return profils.client_profile(db, ledger.account_id_for(db, ledger.TELEGRAM, telegram_id))
