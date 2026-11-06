import json
import os
import sqlite3
from pathlib import Path


DB_PATH = Path(__file__).with_name("nexis_hub.db")


def get_connection():
    return sqlite3.connect(DB_PATH)


def init_db():
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                phone_number TEXT NOT NULL,
                first_name TEXT,
                language TEXT DEFAULT 'fr',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        ensure_column(conn, "users", "channel", "TEXT DEFAULT 'telegram'")
        ensure_column(conn, "users", "commune", "TEXT")
        ensure_column(conn, "users", "preferred_currency", "TEXT DEFAULT 'USD'")
        ensure_column(conn, "users", "is_active", "INTEGER DEFAULT 1")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS providers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                phone_number TEXT NOT NULL,
                full_name TEXT NOT NULL,
                services TEXT NOT NULL,
                communes TEXT NOT NULL,
                languages_spoken TEXT DEFAULT '["fr"]',
                module TEXT DEFAULT 'A',
                badge TEXT DEFAULT 'pending',
                rating REAL DEFAULT 0.00,
                total_missions INTEGER DEFAULT 0,
                success_rate REAL DEFAULT 0.00,
                status TEXT DEFAULT 'available',
                is_verified INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                is_suspended INTEGER DEFAULT 0,
                consecutive_ignored INTEGER DEFAULT 0,
                warnings_count INTEGER DEFAULT 0,
                visit_fee_enabled INTEGER DEFAULT 0,
                latitude REAL,
                longitude REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        ensure_column(conn, "providers", "is_suspended", "INTEGER DEFAULT 0")
        ensure_column(conn, "providers", "consecutive_ignored", "INTEGER DEFAULT 0")
        ensure_column(conn, "providers", "warnings_count", "INTEGER DEFAULT 0")
        ensure_column(conn, "providers", "success_rate", "REAL DEFAULT 0.00")
        ensure_column(conn, "providers", "visit_fee_enabled", "INTEGER DEFAULT 0")
        ensure_column(conn, "providers", "latitude", "REAL")
        ensure_column(conn, "providers", "longitude", "REAL")
        ensure_column(conn, "providers", "id_document_url", "TEXT")
        ensure_column(conn, "providers", "portfolio_urls", "TEXT DEFAULT '[]'")
        ensure_column(conn, "providers", "subscription", "TEXT DEFAULT 'free'")
        ensure_column(conn, "providers", "subscription_end", "TEXT")
        ensure_column(conn, "providers", "preferred_currency", "TEXT DEFAULT 'USD'")
        ensure_column(conn, "providers", "commission_rate", "REAL DEFAULT 10.00")
        ensure_column(conn, "providers", "language", "TEXT DEFAULT 'fr'")
        ensure_column(conn, "providers", "member_since_months", "INTEGER DEFAULT 0")
        # Vérification obligatoire à l'inscription (voir V5_MIGRATION_PLAN.md) :
        # id_document_url/portfolio_urls ci-dessus existent depuis longtemps mais
        # ne sont lus/écrits nulle part (colonnes mortes, laissées telles quelles).
        # Ces trois-ci sont les vraies, utilisées par terminer_inscription_prestataire.
        # file_id Telegram, pas d'URL : aucun hébergement de fichier nécessaire.
        ensure_column(conn, "providers", "id_document_file_id", "TEXT")
        ensure_column(conn, "providers", "selfie_file_id", "TEXT")
        ensure_column(conn, "providers", "portfolio_file_ids", "TEXT DEFAULT '[]'")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS service_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider_id INTEGER NOT NULL,
                service_name TEXT NOT NULL,
                description TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                admin_note TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(provider_id) REFERENCES providers(id)
            )
            """
        )
        # Id de la même proposition côté backend V5 (étape C) : les deux bases
        # numérotent indépendamment, et la Mini App ne crée qu'en local, donc
        # NULL tant que la proposition n'a pas été recopiée au backend.
        ensure_column(conn, "service_requests", "backend_request_id", "INTEGER")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS services (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE NOT NULL,
                name_fr TEXT NOT NULL,
                name_ln TEXT,
                name_en TEXT,
                category TEXT,
                icon_emoji TEXT,
                module TEXT NOT NULL DEFAULT 'A',
                requires_inspection INTEGER DEFAULT 0,
                visit_fee_usd REAL DEFAULT 0.00,
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS platform_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                description TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        _drop_legacy_money_storage(conn)
        _drop_legacy_mission_storage(conn)
        seed_default_services(conn)
        seed_platform_settings(conn)


def _drop_legacy_money_storage(conn):
    """L'argent vit dans le registre du backend (CONCEPTION_ARGENT.md) :
    SQLite ne garde plus de soldes ni de file de rejeu.

    Une file `backend_outbox` non vide contient des mouvements d'argent que le
    backend n'a jamais reçus : les supprimer les perdrait. Le bot refuse alors
    de démarrer ; il faut d'abord la vider avec l'ancienne version (backend
    joignable), puis relancer. L'ancienne table `transactions` reste en place,
    en lecture seule (historique), plus jamais écrite.
    """
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    if "backend_outbox" in tables:
        pending = conn.execute("SELECT COUNT(*) FROM backend_outbox").fetchone()[0]
        if pending:
            raise RuntimeError(
                f"{pending} mouvement(s) d'argent encore en attente dans backend_outbox : "
                "les envoyer au backend avec la version précédente du bot avant de démarrer celle-ci."
            )
        conn.execute("DROP TABLE backend_outbox")
    for table in ("users", "providers"):
        columns = {column[1] for column in conn.execute(f"PRAGMA table_info({table})")}
        for column in ("wallet_balance_usd", "wallet_balance_cdf"):
            if column in columns:
                conn.execute(f"ALTER TABLE {table} DROP COLUMN {column}")


# Ordre de suppression : ce qui pointe vers une mission d'abord.
LEGACY_MISSION_TABLES = ("reviews", "quotes", "missions")


def mission_archive_path():
    return DB_PATH.with_name(f"{DB_PATH.stem}_anciennes_missions.json")


def _drop_legacy_mission_storage(conn):
    """Missions, devis et avis vivent dans le seul backend (CONCEPTION_MISSIONS.md) :
    SQLite n'en garde plus aucune copie.

    Les lignes des anciennes tables sont d'abord écrites dans une archive JSON
    à côté de la base (jamais écrasée : une archive existante fait refuser le
    démarrage plutôt que de la perdre). Les tables ne sont supprimées qu'une
    fois l'archive écrite sur le disque ; une erreur d'écriture laisse tout en
    place. Le nombre de missions par client, qui n'est plus tenu ici, part aussi.
    """
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    present = [table for table in LEGACY_MISSION_TABLES if table in tables]
    if present:
        archive = {}
        for table in present:
            cursor = conn.execute(f"SELECT * FROM {table}")
            names = [column[0] for column in cursor.description]
            archive[table] = [dict(zip(names, row)) for row in cursor.fetchall()]
        if any(archive.values()):
            path = mission_archive_path()
            if path.exists():
                raise RuntimeError(
                    f"{path.name} existe déjà : la déplacer avant de démarrer, pour ne pas écraser une archive."
                )
            partial = path.with_name(path.name + ".partiel")
            try:
                with open(partial, "w", encoding="utf-8") as archive_file:
                    json.dump(archive, archive_file, ensure_ascii=False, indent=1, default=str)
                    archive_file.flush()
                    os.fsync(archive_file.fileno())
                # L'archive n'apparaît qu'entière, sous son nom final.
                os.replace(partial, path)
            finally:
                partial.unlink(missing_ok=True)
        for table in present:
            conn.execute(f"DROP TABLE {table}")
    columns = {column[1] for column in conn.execute("PRAGMA table_info(users)")}
    if "total_missions" in columns:
        conn.execute("ALTER TABLE users DROP COLUMN total_missions")


def ensure_column(conn, table_name: str, column_name: str, column_type: str):
    columns = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    if any(column[1] == column_name for column in columns):
        return
    conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")


def seed_default_services(conn):
    services = [
        ("service_plomberie", "Plomberie", "Plomberie", "Plumbing", "Maison", "🔧", "B", 1, 5.00),
        ("service_electricite", "Electricité", "Electricité", "Electricity", "Maison", "⚡", "B", 1, 5.00),
        ("service_climatisation", "Climatisation", "Climatisation", "Air conditioning", "Maison", "❄️", "B", 1, 5.00),
        ("service_informatique", "Informatique", "Informatique", "IT support", "Digital", "💻", "A", 0, 0.00),
        ("service_graphisme", "Graphisme", "Graphisme", "Design", "Digital", "🎨", "A", 0, 0.00),
        ("service_coiffure", "Coiffure", "Coiffure", "Hairdressing", "Beauté", "✂️", "A", 0, 0.00),
        ("service_nettoyage", "Nettoyage", "Nettoyage", "Cleaning", "Maison", "🧹", "A", 0, 0.00),
        ("service_jardinage", "Jardinage", "Jardinage", "Gardening", "Maison", "🌿", "A", 0, 0.00),
        ("service_autre", "Autre service", "Service mosusu", "Other service", "Autre", "➕", "A", 0, 0.00),
    ]
    conn.executemany(
        """
        INSERT INTO services (
            key, name_fr, name_ln, name_en, category, icon_emoji,
            module, requires_inspection, visit_fee_usd
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
            name_fr = excluded.name_fr,
            name_ln = excluded.name_ln,
            name_en = excluded.name_en,
            category = excluded.category,
            icon_emoji = excluded.icon_emoji,
            module = excluded.module,
            requires_inspection = excluded.requires_inspection,
            visit_fee_usd = excluded.visit_fee_usd
        """,
        services,
    )


def seed_platform_settings(conn):
    settings = [
        ("commission_standard", "10.00", "Commission standard NEXIS HUB en pourcentage"),
        ("commission_urgent", "15.00", "Commission pour mission urgente en pourcentage"),
        ("commission_gold", "8.00", "Commission pour prestataire abonnement Or"),
        ("commission_b2b", "12.00", "Commission pour mission entreprise"),
        ("visit_fee_usd", "5.00", "Frais diagnostic Module B"),
        ("exchange_rate_margin", "150", "Marge CDF ajoutée au taux API"),
        ("delay_provider_response", "30", "Délai réponse prestataire en minutes"),
        ("delay_quote_after_arrive", "120", "Délai devis après arrivée en minutes"),
        ("delay_client_confirm", "1440", "Délai confirmation client en minutes"),
        ("delay_dispute_resolution", "2880", "Délai résolution litige en minutes"),
        ("delay_presence_guarantee", "15", "Délai garantie présence en minutes"),
        ("delay_quote_response", "30", "Délai réponse devis Module A en minutes"),
        ("subscriptions_active", "false", "Activation des abonnements prestataires"),
        ("subscriptions_threshold", "50", "Seuil prestataires actifs pour abonnement"),
    ]
    conn.executemany(
        """
        INSERT INTO platform_settings (key, value, description)
        VALUES (?, ?, ?)
        ON CONFLICT(key) DO NOTHING
        """,
        settings,
    )


def get_active_services(lang: str = "fr", include_icon: bool = True):
    name_column = {
        "fr": "name_fr",
        "ln": "name_ln",
        "en": "name_en",
    }.get(lang, "name_fr")
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            f"""
            SELECT key, icon_emoji, name_fr, {name_column} AS localized_name
            FROM services
            WHERE is_active = 1
            ORDER BY id ASC
            """
        ).fetchall()

    services = {}
    for row in rows:
        label = row["localized_name"] or row["name_fr"]
        services[row["key"]] = f"{row['icon_emoji']} {label}" if include_icon and row["icon_emoji"] else label
    return services


def get_user_by_telegram_id(telegram_id: int):
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(
            "SELECT * FROM users WHERE telegram_id = ?",
            (telegram_id,),
        ).fetchone()


def get_all_users(limit: int = 10):
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(
            """
            SELECT * FROM users
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()


def create_user(telegram_id: int, phone_number: str, first_name: str, language: str = "fr"):
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO users (telegram_id, phone_number, first_name, language)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                phone_number = excluded.phone_number,
                first_name = excluded.first_name,
                language = excluded.language
            """,
            (telegram_id, phone_number, first_name, language),
        )
    return get_user_by_telegram_id(telegram_id)


def update_user_language(telegram_id: int, language: str):
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET language = ? WHERE telegram_id = ?",
            (language, telegram_id),
        )


def update_user_name(telegram_id: int, first_name: str):
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET first_name = ? WHERE telegram_id = ?",
            (first_name, telegram_id),
        )


def get_provider_by_telegram_id(telegram_id: int):
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(
            "SELECT * FROM providers WHERE telegram_id = ?",
            (telegram_id,),
        ).fetchone()


def get_all_providers(limit: int = 10):
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(
            """
            SELECT * FROM providers
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()


def get_provider_by_id(provider_id: int):
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(
            "SELECT * FROM providers WHERE id = ?",
            (provider_id,),
        ).fetchone()


def create_provider(
    telegram_id: int,
    phone_number: str,
    full_name: str,
    services: list[str],
    communes: list[str],
    language: str = "fr",
):
    module = "B" if any(service in {"service_plomberie", "service_electricite", "service_climatisation"} for service in services) else "A"
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO providers (
                telegram_id, phone_number, full_name, services, communes,
                languages_spoken, module
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                phone_number = excluded.phone_number,
                full_name = excluded.full_name,
                services = excluded.services,
                communes = excluded.communes,
                languages_spoken = excluded.languages_spoken,
                module = excluded.module,
                status = 'available'
            """,
            (
                telegram_id,
                phone_number,
                full_name,
                json.dumps(services),
                json.dumps(communes),
                json.dumps([language]),
                module,
            ),
        )
    return get_provider_by_telegram_id(telegram_id)


def update_provider_language(telegram_id: int, language: str):
    with get_connection() as conn:
        conn.execute(
            "UPDATE providers SET languages_spoken = ? WHERE telegram_id = ?",
            (json.dumps([language]), telegram_id),
        )


def update_provider_services(telegram_id: int, services: list[str]):
    module = "B" if any(service in {"service_plomberie", "service_electricite", "service_climatisation"} for service in services) else "A"
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE providers
            SET services = ?, module = ?
            WHERE telegram_id = ?
            """,
            (json.dumps(services), module, telegram_id),
        )
    return get_provider_by_telegram_id(telegram_id)


# Seuls statuts qu'un prestataire peut se donner lui-même (bot ou Mini App).
# Hors de là ("pending_verification", "rejected"), seul l'admin le fait sortir :
# sinon un prestataire non validé se remettait "available" et entrait dans le
# matching, qui ne filtre que sur ce statut.
PROVIDER_SELF_STATUSES = {"available", "offline"}


def provider_can_change_own_status(provider) -> bool:
    return provider is not None and provider["status"] in PROVIDER_SELF_STATUSES


def update_provider_status(telegram_id: int, status: str):
    with get_connection() as conn:
        conn.execute(
            "UPDATE providers SET status = ? WHERE telegram_id = ?",
            (status, telegram_id),
        )
    return get_provider_by_telegram_id(telegram_id)


def update_provider_verification_documents(telegram_id: int, id_document_file_id: str, selfie_file_id: str, portfolio_file_ids: list[str]):
    """Vérification obligatoire à l'inscription (V5_MIGRATION_PLAN.md).

    Fonction séparée plutôt qu'un paramètre ajouté à create_provider() : cette
    dernière est aussi appelée par mini_app/app.py et une dizaine de tests avec sa
    signature actuelle — l'étendre aurait un rayon d'impact bien plus large que
    nécessaire pour ce qui n'est qu'une mise à jour ponctuelle après coup.
    """
    with get_connection() as conn:
        conn.execute(
            "UPDATE providers SET id_document_file_id = ?, selfie_file_id = ?, portfolio_file_ids = ? WHERE telegram_id = ?",
            (id_document_file_id, selfie_file_id, json.dumps(portfolio_file_ids), telegram_id),
        )
    return get_provider_by_telegram_id(telegram_id)


def set_provider_verified(provider_id: int, is_verified: bool = True):
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE providers
            SET is_verified = ?, badge = ?
            WHERE id = ?
            """,
            (1 if is_verified else 0, "verified" if is_verified else "pending", provider_id),
        )
    return get_provider_by_id(provider_id)


def set_provider_suspended(provider_id: int, is_suspended: bool = True):
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE providers
            SET is_suspended = ?, status = ?
            WHERE id = ?
            """,
            (1 if is_suspended else 0, "paused" if is_suspended else "available", provider_id),
        )
    return get_provider_by_id(provider_id)


def get_admin_stats():
    with get_connection() as conn:
        return {
            "users": conn.execute("SELECT COUNT(*) FROM users").fetchone()[0],
            "providers": conn.execute("SELECT COUNT(*) FROM providers").fetchone()[0],
            "pending_services": conn.execute(
                "SELECT COUNT(*) FROM service_requests WHERE status = 'pending'"
            ).fetchone()[0],
        }


def find_matching_providers(service: str, commune: str):
    return rank_eligible_providers(service, commune)[:3]


def rank_eligible_providers(service: str, commune: str):
    """Tous les prestataires disponibles pour ce service et cette commune,
    classés par le score local (même calcul que find_matching_providers)."""
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        providers = conn.execute(
            """
            SELECT * FROM providers
            WHERE is_active = 1
              AND is_suspended = 0
              AND status = 'available'
            """
        ).fetchall()

    matches = []
    for provider in providers:
        services = json.loads(provider["services"] or "[]")
        communes = json.loads(provider["communes"] or "[]")
        if service in services and commune in communes:
            score = 0

            badge_scores = {
                "partner": 30,
                "expert": 20,
                "premium": 10,
                "verified": 5,
                "pending": 0,
            }
            score += badge_scores.get(provider["badge"], 0)
            score += provider["rating"] * 10
            score += min(provider["total_missions"], 50) * 0.2

            if provider["success_rate"] == 100:
                score += 15
            elif provider["success_rate"] >= 90:
                score += 8

            matches.append((score, dict(provider)))

    matches.sort(key=lambda item: item[0], reverse=True)
    return [provider for score, provider in matches]


def create_service_request(telegram_id: int, service_name: str, description: str):
    provider = get_provider_by_telegram_id(telegram_id)
    if provider is None:
        raise ValueError("Prestataire introuvable")

    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO service_requests (provider_id, service_name, description)
            VALUES (?, ?, ?)
            """,
            (provider["id"], service_name, description),
        )
        return cursor.lastrowid


def get_provider_service_requests(telegram_id: int):
    provider = get_provider_by_telegram_id(telegram_id)
    if provider is None:
        return []

    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(
            """
            SELECT * FROM service_requests
            WHERE provider_id = ?
            ORDER BY id DESC
            LIMIT 10
            """,
            (provider["id"],),
        ).fetchall()


def get_pending_service_requests(limit: int = 10):
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(
            """
            SELECT
                service_requests.*,
                providers.telegram_id AS provider_telegram_id,
                providers.full_name AS provider_name
            FROM service_requests
            JOIN providers ON providers.id = service_requests.provider_id
            WHERE service_requests.status = 'pending'
            ORDER BY service_requests.id ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()


def get_service_request_by_id(request_id: int):
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(
            """
            SELECT
                service_requests.*,
                providers.telegram_id AS provider_telegram_id,
                providers.full_name AS provider_name
            FROM service_requests
            JOIN providers ON providers.id = service_requests.provider_id
            WHERE service_requests.id = ?
            """,
            (request_id,),
        ).fetchone()


def update_service_request_status(request_id: int, status: str, admin_note: str = ""):
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE service_requests
            SET status = ?, admin_note = ?
            WHERE id = ?
            """,
            (status, admin_note, request_id),
        )


def set_service_request_backend_id(request_id: int, backend_request_id: int):
    with get_connection() as conn:
        conn.execute(
            "UPDATE service_requests SET backend_request_id = ? WHERE id = ?",
            (backend_request_id, request_id),
        )


def decide_pending_service_request(request_id: int, status: str, admin_note: str = "") -> bool:
    """Comme `update_service_request_status`, mais seulement si la proposition
    est encore `pending` (UPDATE conditionnel atomique, même règle que le
    backend V5). Renvoie False si elle a déjà été traitée. Fonction ajoutée
    plutôt que modifier l'existante, que les tests utilisent encore."""
    with get_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE service_requests
            SET status = ?, admin_note = ?
            WHERE id = ? AND status = 'pending'
            """,
            (status, admin_note, request_id),
        )
        return cursor.rowcount == 1


def update_consecutive_ignored(telegram_id: int):
    """Incrémente le compteur de demandes ignorées."""
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE providers
            SET consecutive_ignored = consecutive_ignored + 1
            WHERE telegram_id = ?
            """,
            (telegram_id,),
        )
        provider = conn.execute(
            "SELECT consecutive_ignored FROM providers WHERE telegram_id = ?",
            (telegram_id,),
        ).fetchone()
        if provider and provider[0] >= 3:
            conn.execute(
                "UPDATE providers SET status = 'paused' WHERE telegram_id = ?",
                (telegram_id,),
            )
    return get_provider_by_telegram_id(telegram_id)


def reset_consecutive_ignored(telegram_id: int):
    """Remet à zéro le compteur quand le prestataire répond."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE providers SET consecutive_ignored = 0 WHERE telegram_id = ?",
            (telegram_id,),
        )
