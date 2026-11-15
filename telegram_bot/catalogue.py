"""Catalogue des services et des communes servies, tel que le backend le tient.

Le backend est la seule source du catalogue (tables `services` et `communes`,
modifiées seulement par une migration). Le bot le lit une fois au démarrage
(`load`) et refuse de démarrer sans lui : il n'y a pas de liste de secours,
qui finirait par différer de celle du backend.

`SERVICES` et `COMMUNES` sont remplis sur place : les modules qui les ont
importés voient le catalogue chargé.
"""

import asyncio
import logging
import unicodedata

import httpx

# Clé du service -> libellé affiché (icône + nom français), dans l'ordre du catalogue.
SERVICES: dict[str, str] = {}
# (nom de la commune, donnée du bouton « commune_… »), dans l'ordre du catalogue.
COMMUNES: list[tuple[str, str]] = []
_NAMES: dict[str, dict[str, str]] = {}
_ICONS: dict[str, str] = {}
# Règles du choix des services d'un prestataire (backend, `GET /api/services`) :
# nombre maximum et services qu'il ne peut pas prendre. Le backend refuse de
# toute façon ; le bot s'en sert pour n'afficher que ce qui sera accepté.
PROVIDER_RULES: dict = {"max_services": None, "excluded_services": ()}

logger = logging.getLogger("nexis.bot")


class CatalogueUnavailable(RuntimeError):
    """Le backend n'a pas donné de catalogue utilisable."""


def commune_callback(name: str) -> str:
    """Donnée du bouton d'une commune : « commune_ » + premier mot du nom, en
    minuscules sans accents (« Autre commune » -> « commune_autre »). Les
    boutons déjà envoyés gardent ainsi leur sens."""
    first_word = name.split()[0] if name.split() else ""
    ascii_word = unicodedata.normalize("NFKD", first_word).encode("ascii", "ignore").decode().lower()
    return f"commune_{ascii_word}"


def fill(body: dict) -> None:
    """Remplace le catalogue par celui reçu de `GET /api/services`. Tout
    contenu inattendu est refusé en bloc : le catalogue d'avant reste."""
    try:
        services = [
            (item["key"], item["icon"] or "", {language: item["names"][language] for language in ("fr", "ln", "en")})
            for item in body["services"]
        ]
        communes = [str(name) for name in body["communes"]]
        max_services = body.get("provider_max_services")
        excluded_services = tuple(str(key) for key in body.get("provider_excluded_services") or ())
        if max_services is not None and (not isinstance(max_services, int) or max_services < 1):
            raise TypeError("provider_max_services")
    except (KeyError, TypeError) as error:
        raise CatalogueUnavailable(f"catalogue illisible : {error!r}") from error
    if not services or not communes:
        raise CatalogueUnavailable("catalogue vide")
    callbacks = [commune_callback(name) for name in communes]
    if len(set(callbacks)) != len(callbacks) or "commune_" in callbacks:
        raise CatalogueUnavailable("deux communes donneraient le même bouton")
    if len({key for key, _, _ in services}) != len(services):
        raise CatalogueUnavailable("service en double")

    SERVICES.clear()
    _NAMES.clear()
    _ICONS.clear()
    for key, icon, names in services:
        SERVICES[key] = f"{icon} {names['fr']}".strip()
        _NAMES[key] = names
        _ICONS[key] = icon
    COMMUNES[:] = list(zip(communes, callbacks))
    PROVIDER_RULES.update(max_services=max_services, excluded_services=excluded_services)


async def load(base_url: str, headers: dict, attempts: int = 10, delay: float = 3.0) -> None:
    """Charge le catalogue au démarrage. Le backend peut démarrer juste après
    le bot : quelques essais, puis refus de démarrer."""
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            async with httpx.AsyncClient(timeout=5.0, headers=headers) as client:
                response = await client.get(f"{base_url}/api/services")
            response.raise_for_status()
            fill(response.json())
            return
        except (httpx.HTTPError, ValueError, CatalogueUnavailable) as error:
            last_error = error
            logger.warning("Catalogue indisponible (essai %s/%s) : %r", attempt, attempts, error)
            if attempt < attempts:
                await asyncio.sleep(delay)
    raise CatalogueUnavailable(f"le backend n'a pas donné le catalogue : {last_error!r}")


def is_service_key(value) -> bool:
    return isinstance(value, str) and value in SERVICES


def service_label(key: str, lang: str = "fr") -> str:
    """Libellé d'un service dans la langue de la personne ; la clé brute pour
    un service qui n'est plus au catalogue (ancienne mission)."""
    names = _NAMES.get(key)
    if names is None:
        return key
    return f"{_ICONS.get(key, '')} {names.get(lang) or names['fr']}".strip()


def commune_from_callback(data: str) -> str | None:
    return next((name for name, callback_data in COMMUNES if callback_data == data), None)


def provider_service_keys(selected=()) -> list[str]:
    """Services qu'un prestataire peut voir dans sa liste : le catalogue sans
    les services exclus, sauf ceux qu'il a déjà (profil d'avant la règle)."""
    excluded = PROVIDER_RULES["excluded_services"]
    return [key for key in SERVICES if key not in excluded or key in selected]


def provider_service_refusal(selected, key: str, original=()) -> str | None:
    """Pourquoi un prestataire ne peut pas ajouter `key` à `selected`, ou None.
    `original` = ses services enregistrés : les reprendre est toujours permis
    (le backend accepte une liste qui n'ajoute rien)."""
    if key in original:
        return None
    if key in PROVIDER_RULES["excluded_services"]:
        return "service_not_for_providers"
    max_services = PROVIDER_RULES["max_services"]
    if max_services is not None and len(selected) >= max_services:
        return "too_many_services"
    return None
