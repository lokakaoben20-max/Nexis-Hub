"""Tests de la Mini App Telegram (mini_app/app.py).

Le coeur de ces tests est la validation de `initData` : c'est la seule barrière
entre la Mini App et n'importe qui sachant construire une requête HTTP. Elle
n'avait aucune couverture jusqu'ici, alors qu'un refactor qui l'affaiblit
(comparaison non constante, hash calculé sur les mauvais champs, expiration
sautée) ne se verrait ni à l'exécution ni à la lecture.
"""

import hashlib
import hmac
import json
import sys
import time
from pathlib import Path
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from telegram_bot import backend_client
from mini_app import app as mini_app_module

TEST_TOKEN = "123456:TEST-TOKEN-NOT-A-REAL-BOT"
CLIENT_ID = 4242
OTHER_ID = 9999


def _build_init_data(user_id: int, token: str = TEST_TOKEN, auth_date: int | None = None) -> str:
    """Fabrique un initData signé comme le ferait Telegram."""
    fields = {
        "auth_date": str(auth_date if auth_date is not None else int(time.time())),
        "query_id": "AAtest-query-id",
        "user": json.dumps({"id": user_id, "first_name": "Test"}, separators=(",", ":")),
    }
    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(fields.items()))
    secret_key = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


def _mini_app(monkeypatch):
    monkeypatch.setattr(mini_app_module, "BOT_TOKEN", TEST_TOKEN)
    monkeypatch.setattr(backend_client, "BACKEND_API_KEY", "test-backend-api-key-not-a-secret")
    return TestClient(mini_app_module.app)


@pytest.fixture
def client(monkeypatch, live_backend):
    """La Mini App, avec un BOT_TOKEN de test, devant le vrai backend."""
    with _mini_app(monkeypatch) as test_client:
        yield test_client


@pytest.fixture
def offline_client(monkeypatch):
    """La Mini App quand le backend ne répond pas."""
    with _mini_app(monkeypatch) as test_client:
        yield test_client


def _auth(user_id: int = CLIENT_ID, **kwargs) -> dict:
    return {"X-Telegram-Init-Data": _build_init_data(user_id, **kwargs)}


def _register(client, telegram_id: int = CLIENT_ID, **overrides):
    payload = {
        "phone_number": "+243800000001",
        "full_name": "Alice Prestataire",
        "services": ["service_plomberie"],
        "communes": ["Gombe"],
        "language": "fr",
    }
    payload.update(overrides)
    return client.post(
        f"/api/provider/{telegram_id}/register",
        json=payload,
        headers=_auth(telegram_id),
    )


# ── Authentification ────────────────────────────────────────────


def test_valid_init_data_is_accepted(client):
    response = client.get(f"/api/profile/{CLIENT_ID}", headers=_auth())
    assert response.status_code == 200
    assert response.json()["telegram_id"] == CLIENT_ID


def test_request_without_init_data_is_rejected(client):
    response = client.get(f"/api/profile/{CLIENT_ID}")
    assert response.status_code == 401


def test_init_data_signed_with_another_token_is_rejected(client):
    """Le cas qui compte : quelqu'un qui connaît le format mais pas le token."""
    headers = {"X-Telegram-Init-Data": _build_init_data(CLIENT_ID, token="000000:WRONG-TOKEN")}
    response = client.get(f"/api/profile/{CLIENT_ID}", headers=headers)
    assert response.status_code == 401


def test_tampered_payload_invalidates_the_signature(client):
    """On resigne pour OTHER_ID puis on réécrit le user : le hash ne suit pas."""
    init_data = _build_init_data(OTHER_ID)
    forged = init_data.replace(
        urlencode({"user": json.dumps({"id": OTHER_ID, "first_name": "Test"}, separators=(",", ":"))}),
        urlencode({"user": json.dumps({"id": CLIENT_ID, "first_name": "Test"}, separators=(",", ":"))}),
    )
    response = client.get(f"/api/profile/{CLIENT_ID}", headers={"X-Telegram-Init-Data": forged})
    assert response.status_code == 401


def test_init_data_without_hash_is_rejected(client):
    signed = _build_init_data(CLIENT_ID)
    without_hash = "&".join(part for part in signed.split("&") if not part.startswith("hash="))
    response = client.get(f"/api/profile/{CLIENT_ID}", headers={"X-Telegram-Init-Data": without_hash})
    assert response.status_code == 401


def test_expired_session_is_rejected(client):
    """auth_date vieux de plus de 24h : rejeu d'une session légitime mais périmée."""
    stale = int(time.time()) - 86_400 - 60
    response = client.get(f"/api/profile/{CLIENT_ID}", headers=_auth(auth_date=stale))
    assert response.status_code == 401


def test_session_just_within_the_window_is_accepted(client):
    recent = int(time.time()) - 3600
    response = client.get(f"/api/profile/{CLIENT_ID}", headers=_auth(auth_date=recent))
    assert response.status_code == 200


# ── Cloisonnement entre utilisateurs ────────────────────────────


def test_cannot_read_another_users_profile(client):
    """Signature parfaitement valide, mais pour quelqu'un d'autre."""
    response = client.get(f"/api/profile/{OTHER_ID}", headers=_auth(CLIENT_ID))
    assert response.status_code == 403


def test_cannot_register_as_another_user(client):
    response = client.post(
        f"/api/provider/{OTHER_ID}/register",
        json={
            "phone_number": "+243800000009",
            "full_name": "Usurpateur",
            "services": ["service_plomberie"],
            "communes": ["Gombe"],
        },
        headers=_auth(CLIENT_ID),
    )
    assert response.status_code == 403


def test_cannot_change_another_providers_status(client):
    _register(client, OTHER_ID)
    response = client.post(
        f"/api/provider/{OTHER_ID}/status",
        json={"status": "offline"},
        headers=_auth(CLIENT_ID),
    )
    assert response.status_code == 403


# ── Inscription prestataire ─────────────────────────────────────


def test_provider_registration_persists_services_and_communes(client):
    response = _register(client)
    assert response.status_code == 200

    provider = response.json()["provider"]
    assert provider["full_name"] == "Alice Prestataire"
    assert provider["services"] == ["service_plomberie"]
    assert provider["communes"] == ["Gombe"]

    assert provider["status"] == "pending_verification", "en attente de l'équipe Nexis, comme depuis le bot"


def test_registration_rejects_unknown_service(client):
    response = _register(client, services=["service_qui_nexiste_pas"])
    assert response.status_code == 400


def test_registration_rejects_unknown_commune(client):
    response = _register(client, communes=["Bruxelles"])
    assert response.status_code == 400


def test_registration_rejects_too_short_name(client):
    response = _register(client, full_name="Al")
    assert response.status_code == 400


def test_registration_rejects_empty_service_list(client):
    response = _register(client, services=[])
    assert response.status_code == 400


# ── Mise à jour du profil prestataire ───────────────────────────


def test_services_update_requires_an_existing_provider(client):
    response = client.post(
        f"/api/provider/{CLIENT_ID}/services",
        json={"services": ["service_plomberie"]},
        headers=_auth(),
    )
    assert response.status_code == 404


def test_services_can_be_updated_after_registration(client):
    _register(client)
    response = client.post(
        f"/api/provider/{CLIENT_ID}/services",
        json={"services": ["service_nettoyage", "service_jardinage"]},
        headers=_auth(),
    )
    assert response.status_code == 200
    assert set(response.json()["provider"]["services"]) == {"service_nettoyage", "service_jardinage"}


def test_a_provider_keeps_at_most_three_services_and_never_other(client):
    _register(client)
    four = ["service_plomberie", "service_nettoyage", "service_jardinage", "service_coiffure"]
    too_many = client.post(f"/api/provider/{CLIENT_ID}/services", json={"services": four}, headers=_auth())
    other = client.post(f"/api/provider/{CLIENT_ID}/services", json={"services": ["service_autre"]}, headers=_auth())

    assert (too_many.status_code, too_many.headers["X-Nexis-Code"]) == (400, "too_many_services")
    assert (other.status_code, other.headers["X-Nexis-Code"]) == (400, "service_not_for_providers")
    profile = client.get(f"/api/profile/{CLIENT_ID}", headers=_auth()).json()
    assert profile["provider"]["services"] == ["service_plomberie"], "refus : rien de changé"
    assert (profile["max_services"], profile["provider_excluded_services"]) == (3, ["service_autre"])


def test_a_provider_changes_his_communes_himself(client):
    _register(client)
    response = client.post(f"/api/provider/{CLIENT_ID}/communes", json={"communes": ["Lemba", "Gombe"]}, headers=_auth())
    assert response.status_code == 200
    assert sorted(response.json()["provider"]["communes"]) == ["Gombe", "Lemba"]

    empty = client.post(f"/api/provider/{CLIENT_ID}/communes", json={"communes": []}, headers=_auth())
    unknown = client.post(f"/api/provider/{CLIENT_ID}/communes", json={"communes": ["Bruxelles"]}, headers=_auth())
    assert (empty.status_code, empty.headers["X-Nexis-Code"]) == (400, "communes_required")
    assert (unknown.status_code, unknown.headers["X-Nexis-Code"]) == (400, "unknown_commune")


def test_cannot_change_another_providers_communes(client):
    _register(client, telegram_id=OTHER_ID)
    response = client.post(f"/api/provider/{OTHER_ID}/communes", json={"communes": ["Lemba"]}, headers=_auth())
    assert response.status_code == 403


def test_status_update_rejects_unknown_value(client):
    _register(client)
    response = client.post(
        f"/api/provider/{CLIENT_ID}/status",
        json={"status": "en_vacances"},
        headers=_auth(),
    )
    assert response.status_code == 400


def test_status_can_be_set_to_offline(client, live_backend):
    live_backend.provider(CLIENT_ID)  # validé par l'équipe Nexis
    response = client.post(
        f"/api/provider/{CLIENT_ID}/status",
        json={"status": "offline"},
        headers=_auth(),
    )
    assert response.status_code == 200
    assert response.json()["provider"]["status"] == "offline"


def test_unvalidated_provider_cannot_make_itself_available(client, live_backend):
    """Inscrit via la Mini App : pending_verification jusqu'à validation admin.
    Se remettre "available" (ou "offline" puis "available") l'aurait fait
    entrer dans le matching sans vérification."""
    _register(client)
    for status in ("available", "offline"):
        response = client.post(f"/api/provider/{CLIENT_ID}/status", json={"status": status}, headers=_auth())
        assert response.status_code == 403
    assert live_backend.profile(CLIENT_ID)["provider"]["status"] == "pending_verification"


def test_rejected_provider_cannot_make_itself_available(client, live_backend):
    _register(client)
    live_backend.reject_provider(CLIENT_ID)
    response = client.post(f"/api/provider/{CLIENT_ID}/status", json={"status": "available"}, headers=_auth())
    assert response.status_code == 403
    assert live_backend.profile(CLIENT_ID)["provider"]["status"] == "rejected"


# ── Demande de service manquant ─────────────────────────────────


def test_service_request_rejects_too_short_description(client):
    _register(client)
    response = client.post(
        f"/api/provider/{CLIENT_ID}/service-requests",
        json={"service_name": "Soudure", "description": "court"},
        headers=_auth(),
    )
    assert response.status_code == 400


def test_service_request_is_recorded(client):
    _register(client)
    response = client.post(
        f"/api/provider/{CLIENT_ID}/service-requests",
        json={"service_name": "Soudure", "description": "Je fais de la soudure metallique."},
        headers=_auth(),
    )
    assert response.status_code == 200
    assert len(response.json()["service_requests"]) == 1


# ── Routes publiques ────────────────────────────────────────────


def test_health_needs_no_authentication(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


# --- Démarrer / finir une mission : décidé par le registre du backend -----------


def _paid_mission_for_provider(live, provider_id: int = CLIENT_ID) -> int:
    """Mission d'un autre client confiée à `provider_id` et payée en escrow."""
    import asyncio

    from telegram_bot import backend_client

    mission_id, quote_id = live.accepted_quote(OTHER_ID, provider_id, amount=30.0)
    asyncio.run(backend_client.create_payment_intent(mission_id, quote_id, "+243810000000", "mpesa", OTHER_ID))
    return mission_id


def test_provider_arrives_enters_the_code_and_finishes_through_the_registry(client, live_backend):
    from backend.app import presence

    mission_id = _paid_mission_for_provider(live_backend)

    arrived = client.post(f"/api/provider/{CLIENT_ID}/missions/{mission_id}/arrived", headers=_auth())
    assert arrived.status_code == 200
    assert arrived.json()["mission"]["status"] == "confirmed", "« je suis arrivé » seul ne démarre rien"
    assert arrived.json()["presence"] == {"confirmed": False, "client_asked": True}
    assert "code" not in str(arrived.json()), "jamais le code au prestataire"

    wrong = client.post(f"/api/provider/{CLIENT_ID}/missions/{mission_id}/presence-code", json={"code": "0000" if presence.presence_code(mission_id) != "0000" else "1111"}, headers=_auth())
    assert wrong.status_code == 409 and wrong.json()["detail"] == {"code": "wrong_presence_code", "attempts_left": 4}

    started = client.post(
        f"/api/provider/{CLIENT_ID}/missions/{mission_id}/presence-code", json={"code": presence.presence_code(mission_id)}, headers=_auth()
    )
    finished = client.post(f"/api/provider/{CLIENT_ID}/missions/{mission_id}/finish", headers=_auth())

    assert started.status_code == 200 and started.json()["mission"]["status"] == "in_progress"
    assert finished.status_code == 200 and finished.json()["mission"]["status"] == "awaiting_confirmation"
    assert live_backend.mission(mission_id).status == "awaiting_confirmation"


def test_mission_actions_are_refused_with_a_code(client, live_backend):
    mission_id = _paid_mission_for_provider(live_backend)

    early_finish = client.post(f"/api/provider/{CLIENT_ID}/missions/{mission_id}/finish", headers=_auth())

    assert early_finish.status_code == 409
    assert early_finish.json()["detail"] == {"code": "invalid_state"}


def test_mission_actions_fail_safe_when_the_backend_is_down(offline_client):
    response = offline_client.post(f"/api/provider/{CLIENT_ID}/missions/1/arrived", headers=_auth())

    assert response.status_code == 503
    assert response.json()["detail"] == {"code": "backend_unavailable"}


# ── Wallet : lu dans le registre du backend, jamais un chiffre par défaut ──


def test_profile_shows_the_registry_wallet_of_the_verified_user(client, live_backend):
    live_backend.credit_wallet(CLIENT_ID, 12.5)

    wallet = client.get(f"/api/profile/{CLIENT_ID}", headers=_auth()).json()["wallet"]

    assert wallet["wallet_balance_usd"] == 12.5
    assert wallet["wallet_balance_cdf"] == 0.0


def test_profile_shows_secured_money_and_wallet_history(client, live_backend):
    live_backend.credit_wallet(CLIENT_ID, 12.5)
    mission_id = _paid_mission_for_provider(live_backend)

    body = client.get(f"/api/profile/{CLIENT_ID}", headers=_auth()).json()

    assert body["wallet"]["secured_usd"] == float(live_backend.mission(mission_id).net_provider)
    assert [(entry["currency"], entry["amount"]) for entry in body["wallet_history"]] == [("USD", "12.50")]


def test_profile_lists_the_backend_missions_by_role(client, live_backend):
    ordered = live_backend.new_mission(CLIENT_ID, service="service_plomberie")
    entrusted = _paid_mission_for_provider(live_backend)

    body = client.get(f"/api/profile/{CLIENT_ID}", headers=_auth()).json()

    assert [mission["id"] for mission in body["client_missions"]] == [ordered]
    assert [mission["id"] for mission in body["provider_missions"]] == [entrusted]
    assert body["provider_missions"][0]["payment_status"] == "paid_escrow"


def test_profile_says_unavailable_when_the_backend_is_down(offline_client):
    """Ni profil inventé ni solde par défaut : la page affiche « indisponible »."""
    response = offline_client.get(f"/api/profile/{CLIENT_ID}", headers=_auth())

    assert response.status_code == 503
    assert response.json()["detail"] == mini_app_module.UNAVAILABLE


def test_registration_writes_nothing_when_the_backend_is_down(offline_client):
    response = _register(offline_client)

    assert response.status_code == 503


def test_profile_reads_the_backend_catalogue_and_profile(client, live_backend):
    live_backend.provider(CLIENT_ID, "Alice", services=["service_electricite"], communes=["Limete"])

    body = client.get(f"/api/profile/{CLIENT_ID}", headers=_auth()).json()

    assert body["client"] is None
    assert (body["provider"]["full_name"], body["provider"]["services"], body["provider"]["communes"]) == (
        "Alice", ["service_electricite"], ["Limete"]
    )
    assert body["available_services"]["service_electricite"] == "Electricité"
    assert "Limete" in body["available_communes"]
    assert body["service_requests"] == []


# --- Ce que la nouvelle page lit : langue, noms traduits, codes de refus ----------


def test_profile_gives_the_account_language_and_translated_service_names(client, live_backend):
    live_backend.provider(CLIENT_ID, "Alice", language="ln", services=["service_electricite"])

    body = client.get(f"/api/profile/{CLIENT_ID}", headers=_auth()).json()

    assert body["language"] == "ln"
    names = body["service_names"]["service_electricite"]
    assert set(names) == {"fr", "ln", "en"}
    assert names["fr"] == body["available_services"]["service_electricite"]


def test_profile_language_is_none_for_an_unknown_person(client):
    body = client.get(f"/api/profile/{CLIENT_ID}", headers=_auth()).json()

    assert body["language"] is None, "la page prend alors la langue de Telegram"


def test_profile_never_sends_the_identity_document_file_ids(client, live_backend):
    live_backend.provider(
        CLIENT_ID, "Alice", id_document_file_id="photo-piece-secrete", selfie_file_id="photo-selfie-secrete", portfolio_file_ids='["p1"]'
    )

    response = client.get(f"/api/profile/{CLIENT_ID}", headers=_auth())
    provider = response.json()["provider"]

    for field in mini_app_module.PRIVATE_PROVIDER_FIELDS:
        assert field not in provider
    assert "secrete" not in response.text
    assert provider["has_documents"] is True


def test_profile_says_when_the_documents_are_still_missing(client, live_backend):
    live_backend.provider(CLIENT_ID, "Alice", verified=False)

    provider = client.get(f"/api/profile/{CLIENT_ID}", headers=_auth()).json()["provider"]

    assert provider["has_documents"] is False
    assert provider["is_verified"] is False


def test_refusals_carry_a_translation_code(client):
    too_short = _register(client, full_name="Al")
    no_commune = _register(client, communes=[])
    unknown = _register(client, communes=["Bruxelles"])

    assert too_short.status_code == 400 and too_short.headers["X-Nexis-Code"] == "name_too_short"
    assert no_commune.status_code == 400 and no_commune.headers["X-Nexis-Code"] == "communes_required"
    assert unknown.status_code == 400 and unknown.headers["X-Nexis-Code"] in ("unknown_commune", "invalid_communes")


def test_unavailable_backend_carries_its_code(offline_client):
    response = _register(offline_client)

    assert response.status_code == 503
    assert response.headers["X-Nexis-Code"] == "backend_unavailable"


def test_provider_missions_show_the_providers_share(client, live_backend):
    mission_id = _paid_mission_for_provider(live_backend)

    mission = client.get(f"/api/profile/{CLIENT_ID}", headers=_auth()).json()["provider_missions"][0]

    assert mission["id"] == mission_id
    assert mission["net_provider"] == live_backend.mission(mission_id).net_provider
    assert {"description", "urgent", "release_after"} <= set(mission), "écran de détail de la mission"


def test_every_error_code_of_the_mini_app_has_a_text_in_each_language():
    """Chaque code renvoyé par le serveur (en-tête ou corps) a son texte
    dans i18n.js, en français, lingala et anglais."""
    import re

    texts = (ROOT / "mini_app" / "static" / "i18n.js").read_text(encoding="utf-8")
    codes = set(mini_app_module.PROFILE_REFUSALS) | {
        "backend_unavailable", "refused", "name_too_short", "invalid_phone", "services_required", "communes_required",
        "service_name_too_short", "description_too_short", "invalid_status",
        "not_paid", "invalid_state", "mission_disputed", "already_settled", "not_mission_provider", "mission_not_found",
        "invalid_presence_code", "wrong_presence_code", "presence_code_locked", "presence_not_configured",
    }
    blocks = re.findall(r"errors: \{(.*?)\n    \}", texts, re.S)
    assert len(blocks) == 3
    for block in blocks:
        missing = [code for code in codes if not re.search(rf"\b{code}:", block)]
        assert not missing, missing


# --- La page n'est jamais servie depuis un vieux cache ------------------------------


def test_page_is_never_cached_and_links_its_files_by_content(client):
    page = client.get("/")

    assert page.status_code == 200
    assert "no-store" in page.headers["Cache-Control"]
    for name in ("styles.css", "i18n.js", "main.js"):
        content = (ROOT / "mini_app" / "static" / name).read_bytes()
        digest = hashlib.sha256(content).hexdigest()[:12]
        assert f"/static/{name}?v={digest}" in page.text
        assert client.get(f"/static/{name}?v={digest}").status_code == 200


# --- Nouveau service : demande à l'équipe, avec photos des réalisations ------------

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


@pytest.fixture
def photos_dir(tmp_path, monkeypatch):
    """Photos gardées (chiffrées) dans un dossier du test, jamais dans le dépôt."""
    monkeypatch.setenv("FILES_DIR", str(tmp_path / "fichiers"))
    return tmp_path / "fichiers"


def _upload(client, data: bytes = PNG, telegram_id: int = CLIENT_ID, user_id: int | None = None):
    return client.post(
        f"/api/provider/{telegram_id}/photos",
        content=data,
        headers={**_auth(user_id or telegram_id), "Content-Type": "image/jpeg"},
    )


def test_a_verified_provider_asks_the_team_for_a_new_service_with_photos(client, live_backend, photos_dir):
    live_backend.provider(CLIENT_ID)
    direct = client.post(
        f"/api/provider/{CLIENT_ID}/services",
        json={"services": ["service_plomberie", "service_nettoyage"]},
        headers=_auth(),
    )
    assert (direct.status_code, direct.headers["X-Nexis-Code"]) == (400, "service_needs_review")

    uploaded = _upload(client)
    assert uploaded.status_code == 200
    photo_id = uploaded.json()["photo_id"]
    stored = list(photos_dir.rglob(photo_id))
    assert len(stored) == 1 and PNG not in stored[0].read_bytes(), "photo gardée chiffrée"

    asked = client.post(
        f"/api/provider/{CLIENT_ID}/service-additions",
        json={"service_key": "service_nettoyage", "description": "3 ans de nettoyage de bureaux", "photo_ids": [photo_id]},
        headers=_auth(),
    )
    assert asked.status_code == 200
    body = asked.json()
    assert "service_nettoyage" not in body["provider"]["services"], "actif seulement après validation"
    assert [(item["service_key"], item["status"]) for item in body["service_additions"]] == [("service_nettoyage", "pending")]

    again = client.post(
        f"/api/provider/{CLIENT_ID}/service-additions", json={"service_key": "service_nettoyage"}, headers=_auth()
    )
    assert (again.status_code, again.headers["X-Nexis-Code"]) == (400, "service_addition_pending")

    profile = client.get(f"/api/profile/{CLIENT_ID}", headers=_auth()).json()
    assert [item["status"] for item in profile["service_additions"]] == ["pending"]

    addition_id = body["service_additions"][0]["id"]
    cancelled = client.post(f"/api/provider/{CLIENT_ID}/service-additions/{addition_id}/cancel", json={}, headers=_auth())
    assert cancelled.status_code == 200
    assert [item["status"] for item in cancelled.json()["service_additions"]] == ["cancelled"]
    missing = client.post(f"/api/provider/{CLIENT_ID}/service-additions/999999/cancel", json={}, headers=_auth())
    assert (missing.status_code, missing.headers["X-Nexis-Code"]) == (404, "service_addition_not_found")


def test_photo_uploads_are_checked_and_belong_to_their_sender(client, live_backend, photos_dir):
    live_backend.provider(CLIENT_ID)
    live_backend.provider(OTHER_ID)

    not_an_image = _upload(client, b"%PDF-1.7 pas une photo")
    too_large = _upload(client, PNG + b"\x00" * (mini_app_module.MAX_PHOTO_BYTES))
    empty = _upload(client, b"")
    as_someone_else = _upload(client, telegram_id=OTHER_ID, user_id=CLIENT_ID)
    assert (not_an_image.status_code, not_an_image.headers["X-Nexis-Code"]) == (415, "unsupported_file_type")
    assert (too_large.status_code, too_large.headers["X-Nexis-Code"]) == (413, "file_too_large")
    assert (empty.status_code, empty.headers["X-Nexis-Code"]) == (400, "empty_file")
    assert as_someone_else.status_code == 403

    others_photo = _upload(client, telegram_id=OTHER_ID).json()["photo_id"]
    stolen = client.post(
        f"/api/provider/{CLIENT_ID}/service-additions",
        json={"service_key": "service_nettoyage", "photo_ids": [others_photo]},
        headers=_auth(),
    )
    assert (stolen.status_code, stolen.headers["X-Nexis-Code"]) == (400, "invalid_photos")
    assert live_backend.profile(CLIENT_ID)["provider"]["services"] == ["service_plomberie"]


def test_every_text_of_the_mini_app_exists_in_each_language():
    """Chaque clé t("...") de main.js a son texte en français, lingala et anglais."""
    import re

    script = (ROOT / "mini_app" / "static" / "main.js").read_text(encoding="utf-8")
    texts = (ROOT / "mini_app" / "static" / "i18n.js").read_text(encoding="utf-8")
    keys = set(re.findall(r'\bt\("([a-z_]+)"', script))
    blocks = re.split(r"\n  (?:fr|ln|en): \{", texts)[1:]
    assert len(blocks) == 3
    for block in blocks:
        missing = sorted(key for key in keys if not re.search(rf"^    {key}:", block, re.M))
        assert not missing, missing


# ── Case des conditions d'utilisation ───────────────────────────


def _publish_terms(live_backend, version="v1", text=None):
    from backend.app import conditions

    with live_backend.database.SessionLocal() as db:
        for key in ("cgu", "conditions_prestataires"):
            conditions.publish_version(db, key, version, text or f"Texte {key} {version}")
        db.commit()


def _terms_rows(live_backend):
    from sqlalchemy import select

    from backend.app import conditions

    with live_backend.database.SessionLocal() as db:
        return [(row.role, row.surface) for row in db.scalars(select(conditions.LegalAcceptance)).all()]


PROVIDER_TERMS = [{"document_key": "cgu", "version": "v1"}, {"document_key": "conditions_prestataires", "version": "v1"}]


@pytest.mark.conditions_reelles
def test_nothing_published_closes_the_registration_screen(client, live_backend):
    terms = client.get(f"/api/profile/{CLIENT_ID}", headers=_auth()).json()["terms"]
    assert terms["unavailable"] is True
    response = _register(client)
    assert (response.status_code, response.headers["X-Nexis-Code"]) == (503, "terms_unavailable")


@pytest.mark.conditions_reelles
def test_registration_from_the_mini_app_needs_the_box(client, live_backend):
    _publish_terms(live_backend)
    terms = client.get(f"/api/profile/{CLIENT_ID}", headers=_auth()).json()["terms"]
    assert [item["document_key"] for item in terms["by_role"]["provider"]] == ["cgu", "conditions_prestataires"]

    refused = _register(client)
    assert (refused.status_code, refused.headers["X-Nexis-Code"]) == (409, "terms_not_accepted")
    assert live_backend.profile(CLIENT_ID)["provider"] is None

    accepted = _register(client, terms_documents=PROVIDER_TERMS)
    assert accepted.status_code == 200, accepted.json()
    assert _terms_rows(live_backend) == [("provider", "mini_app"), ("provider", "mini_app")]
    assert client.get(f"/api/profile/{CLIENT_ID}", headers=_auth()).json()["terms"]["missing"] == []


@pytest.mark.conditions_reelles
def test_an_old_account_ticks_again_in_the_mini_app_and_only_for_itself(client, live_backend):
    _publish_terms(live_backend)
    live_backend.client(CLIENT_ID)
    terms = client.get(f"/api/profile/{CLIENT_ID}", headers=_auth()).json()["terms"]
    assert ([item["document_key"] for item in terms["missing"]], terms["role"]) == (["cgu"], "client")

    payload = {"role": "client", "documents": [{"document_key": "cgu", "version": "v1"}]}
    assert client.post(f"/api/terms/{OTHER_ID}", json=payload, headers=_auth()).status_code == 403
    response = client.post(f"/api/terms/{CLIENT_ID}", json=payload, headers=_auth())
    assert response.status_code == 200 and response.json()["missing"] == []
    assert _terms_rows(live_backend) == [("client", "mini_app")]


@pytest.mark.conditions_reelles
def test_the_reading_page_shows_the_exact_text_escaped(client, live_backend):
    _publish_terms(live_backend, text="Article 1 <script>alert(1)</script>\nArticle 2")
    page = client.get("/conditions/cgu/v1?lang=ln")
    assert page.status_code == 200
    assert "Mibeko ya kosalela Nexis Hub" in page.text
    assert "&lt;script&gt;" in page.text and "<script>" not in page.text
    assert client.get("/conditions/cgu/v9").status_code == 404
