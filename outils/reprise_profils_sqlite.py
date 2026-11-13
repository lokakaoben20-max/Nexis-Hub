"""Reprise, une seule fois, des profils de l'ancien fichier SQLite (`db.py`)
dans le backend, devenu leur seule mémoire.

À lancer sur le PC, bot et Mini App arrêtés, après `alembic upgrade head` :

    python -m outils.reprise_profils_sqlite nexis_hub.db              # rapport seul
    python -m outils.reprise_profils_sqlite nexis_hub.db --appliquer  # reprise

Le fichier SQLite est ouvert en lecture seule : il n'est jamais modifié.
Sans `--appliquer`, rien n'est écrit nulle part : le rapport dit ce qui
serait créé, mis à jour, ce qui est déjà identique, et chaque conflit.
Avec `--appliquer`, tout est écrit dans une seule transaction, et seulement
s'il n'y a aucun conflit : un conflit arrête tout et rien n'est écrit.
Relancé après une reprise réussie, le script ne trouve plus rien à faire.

Règles (le fichier SQLite faisait foi jusqu'ici pour les profils, le backend
en recevait une copie quand il répondait) :

- profil absent du backend : créé ;
- nom, numéro, langue, services, communes, disponibilité et suspension
  différents : la valeur de SQLite est reprise (montrée dans le rapport) ;
- un prestataire non vérifié n'arrive jamais « disponible » : il reste en
  attente de vérification ;
- conflit, qui arrête tout : décisions de vérification contradictoires
  (vérifié d'un côté, refusé ou non vérifié de l'autre), service ou commune
  absent du catalogue, donnée invalide, deux langues différentes pour la même
  personne, badge attribué à la main différent, proposition de service décidée
  différemment des deux côtés ;
- les statistiques (note, missions, taux de réussite) ne sont pas reprises :
  le backend les recalcule depuis les missions et les avis, qu'il tient seul.
"""

import argparse
import json
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

from sqlalchemy.orm import Session

from backend.app import ledger, profils
from backend.app.models import NexisAccount, ProviderServiceRequest

# Badges que seul un admin attribue (le badge « verified » suit la vérification).
MANUAL_BADGES = ("partner", "expert", "premium")
SELF_STATUSES = ("available", "offline", "paused")


@dataclass
class Rapport:
    a_faire: list[str] = field(default_factory=list)
    identiques: list[str] = field(default_factory=list)
    conflits: list[str] = field(default_factory=list)
    actions: list[Callable[[], None]] = field(default_factory=list, repr=False)
    applique: bool = False

    def texte(self) -> str:
        lignes = [f"À reprendre : {len(self.a_faire)}"]
        lignes += [f"  - {ligne}" for ligne in self.a_faire]
        lignes.append(f"Déjà identiques : {len(self.identiques)}")
        lignes.append(f"Conflits : {len(self.conflits)}")
        lignes += [f"  ! {ligne}" for ligne in self.conflits]
        if self.conflits:
            lignes.append("Rien n'a été écrit. Corrigez chaque conflit, puis relancez.")
        elif self.applique:
            lignes.append("Reprise faite : tout a été écrit dans le backend.")
        elif self.a_faire:
            lignes.append("Rien n'a été écrit. Relancez avec --appliquer pour faire la reprise.")
        else:
            lignes.append("Rien à faire : le backend a déjà tout.")
        return "\n".join(lignes)


# --- Lecture du fichier SQLite -----------------------------------------------


def _ouvrir(chemin: Path) -> sqlite3.Connection:
    if not chemin.is_file():
        raise FileNotFoundError(f"Fichier introuvable : {chemin}")
    conn = sqlite3.connect(f"{chemin.resolve().as_uri()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _lignes(conn: sqlite3.Connection, table: str) -> list[dict]:
    """Toutes les lignes d'une table, en dictionnaires (colonnes absentes
    d'un fichier ancien : simplement pas de clé). Table absente : aucune."""
    exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)).fetchone()
    if exists is None:
        return []
    return [dict(row) for row in conn.execute(f"SELECT * FROM {table} ORDER BY id")]


def _liste_json(valeur) -> list | None:
    try:
        liste = json.loads(valeur or "[]")
    except (TypeError, ValueError):
        return None
    return liste if isinstance(liste, list) and all(isinstance(item, str) for item in liste) else None


def _date(valeur) -> datetime | None:
    try:
        return datetime.fromisoformat(str(valeur)) if valeur else None
    except ValueError:
        return None


def _texte(valeur) -> str | None:
    valeur = " ".join(str(valeur).split()) if valeur is not None else ""
    return valeur or None


# --- Comparaison et reprise ----------------------------------------------------


class _Personne:
    """Ce que SQLite sait d'un identifiant Telegram."""

    def __init__(self, telegram_id: int):
        self.telegram_id = telegram_id
        self.client: dict | None = None
        self.provider: dict | None = None

    @property
    def nom(self) -> str:
        source = self.provider or self.client or {}
        return f"Telegram {self.telegram_id} ({_texte(source.get('full_name') or source.get('first_name')) or 'sans nom'})"


def _langue(personne: _Personne, rapport: Rapport) -> str | None:
    langues = {row.get("language") or "fr" for row in (personne.client, personne.provider) if row is not None}
    if len(langues) > 1:
        rapport.conflits.append(f"{personne.nom} : deux langues différentes ({', '.join(sorted(langues))}), une seule par compte")
        return None
    langue = langues.pop()
    if langue not in profils.LANGUAGES:
        rapport.conflits.append(f"{personne.nom} : langue inconnue « {langue} »")
        return None
    return langue


def _reprendre_personne(db: Session, personne: _Personne, rapport: Rapport, catalogue: tuple[set, set]) -> None:
    conflits_avant = len(rapport.conflits)
    account_id = ledger.account_id_for(db, ledger.TELEGRAM, personne.telegram_id)
    changements: list[str] = []
    etapes: list[Callable[[int], None]] = []

    langue = _langue(personne, rapport)
    compte = db.get(NexisAccount, account_id) if account_id is not None else None
    if langue is not None and (compte is None or compte.language != langue):
        changements.append(f"langue {compte.language if compte else '—'} → {langue}")
        etapes.append(lambda acc: profils.set_language(db, acc, langue))

    if personne.client is not None:
        _comparer_client(db, personne, account_id, rapport, changements, etapes)
    if personne.provider is not None:
        _comparer_prestataire(db, personne, account_id, rapport, changements, etapes, catalogue)

    if len(rapport.conflits) > conflits_avant:
        return
    if not changements:
        rapport.identiques.append(personne.nom)
        return
    rapport.a_faire.append(f"{personne.nom} : {', '.join(changements)}")

    def appliquer() -> None:
        acc = account_id if account_id is not None else ledger.account_id_for(db, ledger.TELEGRAM, personne.telegram_id, create=True)
        for etape in etapes:
            etape(acc)

    rapport.actions.append(appliquer)


def _comparer_client(db, personne, account_id, rapport, changements, etapes) -> None:
    row = personne.client
    prenom, telephone = _texte(row.get("first_name")), _texte(row.get("phone_number"))
    if prenom is None or len(prenom) > profils.MAX_NAME_LENGTH:
        rapport.conflits.append(f"{personne.nom} : prénom client vide ou trop long")
        return
    if telephone is not None and len(telephone) > profils.MAX_PHONE_LENGTH:
        rapport.conflits.append(f"{personne.nom} : numéro client invalide")
        return
    actuel = profils.client_profile(db, account_id)
    if actuel is not None and (actuel.first_name, actuel.phone_number) == (prenom, telephone or actuel.phone_number):
        return
    changements.append("profil client créé" if actuel is None else "profil client mis à jour")
    cree_le = _date(row.get("created_at"))

    def etape(acc: int) -> None:
        profil, cree = profils.save_client_profile(db, acc, first_name=prenom, phone_number=telephone)
        if cree and cree_le is not None:
            profil.created_at = cree_le

    etapes.append(etape)


def _comparer_prestataire(db, personne, account_id, rapport, changements, etapes, catalogue) -> None:
    row = personne.provider
    services_connus, communes_connues = catalogue
    nom, telephone = _texte(row.get("full_name")), _texte(row.get("phone_number"))
    services, communes = _liste_json(row.get("services")), _liste_json(row.get("communes"))
    portfolio = _liste_json(row.get("portfolio_file_ids"))
    statut, verifie, suspendu = row.get("status") or "available", bool(row.get("is_verified")), bool(row.get("is_suspended"))

    problemes = []
    if nom is None or len(nom) > profils.MAX_NAME_LENGTH:
        problemes.append("nom vide ou trop long")
    if telephone is not None and len(telephone) > profils.MAX_PHONE_LENGTH:
        problemes.append("numéro invalide")
    if not services or not communes or portfolio is None:
        problemes.append("services, communes ou photos illisibles")
    else:
        if inconnus := [key for key in services if key not in services_connus]:
            problemes.append(f"service(s) absent(s) du catalogue : {', '.join(inconnus)}")
        if inconnues := [name for name in communes if name not in communes_connues]:
            problemes.append(f"commune(s) absente(s) du catalogue : {', '.join(inconnues)}")
    if statut not in (*SELF_STATUSES, "pending_verification", "rejected"):
        problemes.append(f"statut inconnu « {statut} »")
    if verifie and statut in ("pending_verification", "rejected"):
        problemes.append(f"vérifié mais « {statut} »")
    if problemes:
        rapport.conflits.extend(f"{personne.nom} : {probleme}" for probleme in problemes)
        return

    # Statut voulu : celui de SQLite, sauf qu'un non vérifié n'est jamais disponible.
    if not verifie:
        statut = "rejected" if statut == "rejected" else "pending_verification"

    actuel = profils.provider_profile(db, account_id)
    badge = row.get("badge") or "pending"
    if actuel is not None:
        verifie_backend = profils.is_verified(actuel)
        if verifie_backend != verifie:
            cote, autre = ("le backend", row.get("status")) if verifie_backend else ("SQLite", actuel.status)
            rapport.conflits.append(f"{personne.nom} : vérifié dans {cote} seulement (de l'autre côté : « {autre} »)")
            return
        if not verifie and actuel.status == "rejected" and statut == "pending_verification":
            rapport.conflits.append(f"{personne.nom} : refusé dans le backend, en attente dans SQLite")
            return
        if badge in MANUAL_BADGES and badge != actuel.badge:
            rapport.conflits.append(f"{personne.nom} : badge « {badge} » dans SQLite, « {actuel.badge} » dans le backend")
            return
    elif badge in MANUAL_BADGES:
        rapport.conflits.append(f"{personne.nom} : badge « {badge} » à attribuer à la main, absent du backend")
        return

    documents = {
        "id_document_file_id": row.get("id_document_file_id") or None,
        "selfie_file_id": row.get("selfie_file_id") or None,
        "portfolio_file_ids": portfolio or None,
    }
    if actuel is None:
        changements.append(f"profil prestataire créé ({statut}{', suspendu' if suspendu else ''})")
    else:
        avant = (
            actuel.full_name,
            actuel.phone_number,
            profils.provider_services(db, actuel.account_id),
            profils.provider_communes(db, actuel.account_id),
            actuel.id_document_file_id,
            actuel.selfie_file_id,
            actuel.portfolio_file_ids or None,
        )
        apres = (
            nom,
            telephone or actuel.phone_number,
            [key for key in services_connus if key in services],
            [name for name in communes_connues if name in communes],
            documents["id_document_file_id"] or actuel.id_document_file_id,
            documents["selfie_file_id"] or actuel.selfie_file_id,
            documents["portfolio_file_ids"] or actuel.portfolio_file_ids or None,
        )
        if avant != apres:
            changements.append("profil prestataire mis à jour")
        if actuel.status != statut:
            changements.append(f"statut {actuel.status} → {statut}")
        if actuel.is_suspended != suspendu:
            changements.append("suspendu" if suspendu else "suspension levée")
        if avant == apres and actuel.status == statut and actuel.is_suspended == suspendu:
            return

    cree_le = _date(row.get("created_at"))
    ignores = int(row.get("consecutive_ignored") or 0)

    def etape(acc: int) -> None:
        profil, cree = profils.register_provider(
            db, acc, full_name=nom, phone_number=telephone, services=services, communes=communes, **documents
        )
        if cree and cree_le is not None:
            profil.created_at = cree_le
        if statut == "rejected":
            profils.reject_provider(db, acc)
        elif verifie:
            profils.verify_provider(db, acc)
            if profil.status != statut:
                # Reprise du statut tel que SQLite le tenait (pause comprise,
                # avec son compteur de refus).
                profil.status = statut
                profil.consecutive_ignored = ignores if statut == "paused" else 0
        profils.set_suspended(db, acc, suspendu)
        db.flush()

    etapes.append(etape)


def _reprendre_propositions(db: Session, conn: sqlite3.Connection, prestataires: dict[int, int], rapport: Rapport) -> None:
    """Propositions de services. Recopiée au backend (`backend_request_id`) :
    la décision locale est reprise si le backend attend encore. Jamais
    recopiée : créée telle quelle (une reprise relancée la retrouve à
    l'identique)."""
    for row in _lignes(conn, "service_requests"):
        telegram_id = prestataires.get(row["provider_id"])
        libelle = f"Proposition SQLite n° {row['id']} ({row.get('service_name')})"
        statut, note = row.get("status") or "pending", row.get("admin_note")
        if telegram_id is None:
            rapport.conflits.append(f"{libelle} : prestataire introuvable dans SQLite")
            continue
        if statut not in ("pending", "accepted", "rejected"):
            rapport.conflits.append(f"{libelle} : statut inconnu « {statut} »")
            continue
        account_id = ledger.account_id_for(db, ledger.TELEGRAM, telegram_id)
        backend_id = row.get("backend_request_id")
        if backend_id is not None:
            existante = db.get(ProviderServiceRequest, backend_id)
            if existante is None or account_id is None or existante.provider_account_id != account_id:
                rapport.conflits.append(f"{libelle} : la proposition n° {backend_id} du backend n'est pas la même")
            elif existante.status == statut:
                rapport.identiques.append(libelle)
            elif existante.status == "pending":
                rapport.a_faire.append(f"{libelle} : décision reprise ({statut})")
                rapport.actions.append(lambda existante=existante, statut=statut, note=note: _decider(existante, statut, note))
            else:
                rapport.conflits.append(f"{libelle} : « {statut} » dans SQLite, « {existante.status} » dans le backend")
            continue

        cree_le = _date(row.get("created_at"))
        if account_id is not None and _deja_reprise(db, account_id, row, cree_le):
            rapport.identiques.append(libelle)
            continue
        rapport.a_faire.append(f"{libelle} : créée ({statut})")

        def creer(row=row, telegram_id=telegram_id, statut=statut, note=note, cree_le=cree_le) -> None:
            acc = ledger.account_id_for(db, ledger.TELEGRAM, telegram_id)
            demande = ProviderServiceRequest(
                provider_account_id=acc,
                service_name=row["service_name"],
                description=row.get("description") or "",
                status="pending",
                created_at=cree_le or datetime.utcnow(),
            )
            db.add(demande)
            if statut != "pending":
                _decider(demande, statut, note)
            db.flush()

        rapport.actions.append(creer)


def _deja_reprise(db: Session, account_id: int, row: dict, cree_le: datetime | None) -> bool:
    return (
        db.query(ProviderServiceRequest.id)
        .filter(
            ProviderServiceRequest.provider_account_id == account_id,
            ProviderServiceRequest.service_name == row["service_name"],
            ProviderServiceRequest.description == (row.get("description") or ""),
            ProviderServiceRequest.created_at == cree_le,
        )
        .first()
        is not None
    )


def _decider(demande: ProviderServiceRequest, statut: str, note) -> None:
    demande.status = statut
    demande.admin_note = note
    demande.reviewed_at = datetime.utcnow()


def reprendre(db: Session, chemin: Path, appliquer: bool = False) -> Rapport:
    """Compare SQLite au backend ; avec `appliquer`, écrit tout dans la
    transaction de `db` et la valide, seulement s'il n'y a aucun conflit."""
    rapport = Rapport()
    conn = _ouvrir(chemin)
    try:
        personnes: dict[int, _Personne] = {}
        for row in _lignes(conn, "users"):
            personnes.setdefault(int(row["telegram_id"]), _Personne(int(row["telegram_id"]))).client = row
        prestataires: dict[int, int] = {}
        for row in _lignes(conn, "providers"):
            personnes.setdefault(int(row["telegram_id"]), _Personne(int(row["telegram_id"]))).provider = row
            prestataires[row["id"]] = int(row["telegram_id"])

        catalogue = ([service.key for service in profils.active_services(db)], profils.communes(db))
        for telegram_id in sorted(personnes):
            _reprendre_personne(db, personnes[telegram_id], rapport, catalogue)
        _reprendre_propositions(db, conn, prestataires, rapport)
    finally:
        conn.close()

    if not appliquer or rapport.conflits or not rapport.actions:
        db.rollback()
        return rapport
    try:
        for action in rapport.actions:
            action()
        db.commit()
    except Exception:
        db.rollback()
        raise
    rapport.applique = True
    return rapport


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reprise des profils de l'ancien fichier SQLite dans le backend (une seule fois).")
    parser.add_argument("fichier", type=Path, help="le fichier SQLite de db.py, par exemple nexis_hub.db")
    parser.add_argument("--appliquer", action="store_true", help="écrire la reprise (sans : rapport seul, rien n'est écrit)")
    args = parser.parse_args(argv)

    from backend.app.database import SessionLocal

    try:
        with SessionLocal() as db:
            rapport = reprendre(db, args.fichier, appliquer=args.appliquer)
    except FileNotFoundError as error:
        print(error, file=sys.stderr)
        return 2
    print(rapport.texte())
    return 1 if rapport.conflits else 0


if __name__ == "__main__":
    sys.exit(main())
