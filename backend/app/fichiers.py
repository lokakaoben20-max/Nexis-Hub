"""Fichiers envoyés par les personnes (photos de réalisations) : gardés par le
backend lui-même, chiffrés, pour tous les canaux.

Jusqu'ici, toute photo passait par Telegram (un identifiant de fichier
Telegram, l'image restant chez Telegram). La Mini App et l'app mobile n'ont
pas ce mécanisme : le backend devient la seule mémoire des fichiers, quel que
soit le canal (décision de Ben, 2026-11-15 : les photos d'un nouveau service
s'envoient depuis la Mini App).

Règles :

- **type réel** : seul le contenu décide (JPEG, PNG ou WebP reconnus à leurs
  premiers octets), jamais le nom ni l'en-tête annoncé ;
- **taille** : au plus `MAX_PHOTO_BYTES` ;
- **chiffrement** : AES-256-GCM, une clé (`FILES_ENCRYPTION_KEY`), un nonce
  aléatoire par fichier, l'identifiant du fichier lié au chiffré (données
  associées) : un fichier copié sous un autre nom ne se déchiffre pas ;
- **écriture atomique** : fichier temporaire puis renommage ; la ligne en base
  n'est validée par l'appelant qu'après l'écriture réussie. Un fichier sur
  disque sans ligne (transaction annulée) n'est jamais servi ;
- **lecture** : seuls les admins (routes /api/admin/files) ; la personne qui
  a envoyé la photo ne la relit pas par l'API (elle l'a sur son téléphone).

Emplacement : `FILES_DIR`. En développement, défaut `var/fichiers` à la racine
du dépôt, et une clé créée une fois dans ce dossier (`.cle`). Hors
développement, `FILES_DIR` et `FILES_ENCRYPTION_KEY` sont obligatoires
(nexis_config) ; hébergé, `FILES_DIR` est un bucket monté dans le conteneur.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import os
import secrets
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.models import STORED_FILE_PURPOSES, StoredFile

MAX_PHOTO_BYTES = 5 * 1024 * 1024
# Photos envoyées mais pas encore jointes à une demande : au plus autant par
# personne sur 24 h (une demande en prend au plus MAX_PHOTOS_PER_ADDITION).
MAX_UNATTACHED_PER_DAY = 30
MAX_PHOTOS_PER_ADDITION = 10
NONCE_BYTES = 12
KEY_BYTES = 32

_SIGNATURES = (
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
)


class FileRefused(ValueError):
    def __init__(self, code: str, http_status: int = 400):
        super().__init__(code)
        self.code = code
        self.http_status = http_status


class StorageNotConfigured(RuntimeError):
    pass


def sniff_image(data: bytes) -> str | None:
    """Type réel d'une image d'après ses premiers octets, sinon None."""
    for signature, content_type in _SIGNATURES:
        if data.startswith(signature):
            return content_type
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _development() -> bool:
    return (os.getenv("APP_ENV", "developpement").strip() or "developpement") == "developpement"


def storage_dir() -> Path:
    configured = os.getenv("FILES_DIR", "").strip()
    if configured:
        return Path(configured)
    if not _development():
        raise StorageNotConfigured("FILES_DIR manquant")
    return _repo_root() / "var" / "fichiers"


def _key() -> bytes:
    configured = os.getenv("FILES_ENCRYPTION_KEY", "").strip()
    if configured:
        try:
            key = base64.urlsafe_b64decode(configured)
        except (binascii.Error, ValueError) as exc:
            raise StorageNotConfigured("FILES_ENCRYPTION_KEY illisible (base64 de 32 octets attendu)") from exc
        if len(key) != KEY_BYTES:
            raise StorageNotConfigured("FILES_ENCRYPTION_KEY doit faire 32 octets")
        return key
    if not _development():
        raise StorageNotConfigured("FILES_ENCRYPTION_KEY manquant")
    # Développement : une clé créée une fois, gardée à côté des fichiers.
    directory = storage_dir()
    directory.mkdir(parents=True, exist_ok=True)
    key_file = directory / ".cle"
    if not key_file.exists():
        try:
            with open(key_file, "xb") as handle:
                handle.write(secrets.token_bytes(KEY_BYTES))
        except FileExistsError:
            pass
    key = key_file.read_bytes()
    if len(key) != KEY_BYTES:
        raise StorageNotConfigured(f"{key_file} abîmée")
    return key


def new_key() -> str:
    """Clé à mettre dans FILES_ENCRYPTION_KEY : python -m backend.app.fichiers"""
    return base64.urlsafe_b64encode(secrets.token_bytes(KEY_BYTES)).decode()


def _path(file_id: str) -> Path:
    # Deux niveaux de dossiers : pas des milliers de fichiers dans un seul.
    return storage_dir() / file_id[:2] / file_id


def _encrypt(file_id: str, data: bytes) -> bytes:
    nonce = secrets.token_bytes(NONCE_BYTES)
    return nonce + AESGCM(_key()).encrypt(nonce, data, file_id.encode())


def _decrypt(file_id: str, blob: bytes) -> bytes:
    return AESGCM(_key()).decrypt(blob[:NONCE_BYTES], blob[NONCE_BYTES:], file_id.encode())


def _write_atomically(path: Path, blob: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=path.parent, prefix=".envoi-")
    try:
        with os.fdopen(handle, "wb") as out:
            out.write(blob)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def store_photo(db: Session, owner_account_id: int, data: bytes, purpose: str = "service_photo") -> StoredFile:
    """Vérifie, chiffre et écrit une photo ; ajoute sa ligne à la session.
    L'appelant valide (`commit`) : sans validation, le fichier écrit reste
    orphelin et n'est jamais servi."""
    if purpose not in STORED_FILE_PURPOSES:
        raise ValueError(f"usage inconnu : {purpose}")
    if not data:
        raise FileRefused("empty_file")
    if len(data) > MAX_PHOTO_BYTES:
        raise FileRefused("file_too_large", 413)
    content_type = sniff_image(data)
    if content_type is None:
        raise FileRefused("unsupported_file_type", 415)
    since = datetime.utcnow() - timedelta(days=1)
    recent = db.scalar(
        select(func.count())
        .select_from(StoredFile)
        .where(
            StoredFile.owner_account_id == owner_account_id,
            StoredFile.service_addition_id.is_(None),
            StoredFile.created_at >= since,
        )
    ) or 0
    if recent >= MAX_UNATTACHED_PER_DAY:
        raise FileRefused("too_many_files", 429)

    file_id = secrets.token_hex(16)
    _write_atomically(_path(file_id), _encrypt(file_id, data))
    stored = StoredFile(
        id=file_id,
        owner_account_id=owner_account_id,
        purpose=purpose,
        content_type=content_type,
        size_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        created_at=datetime.utcnow(),
    )
    db.add(stored)
    db.flush()
    return stored


def read(stored: StoredFile) -> bytes:
    """Contenu déchiffré, vérifié contre l'empreinte enregistrée."""
    if stored.deleted_at is not None:
        raise FileRefused("file_deleted", 410)
    try:
        data = _decrypt(stored.id, _path(stored.id).read_bytes())
    except FileNotFoundError as exc:
        raise FileRefused("file_missing", 500) from exc
    if hashlib.sha256(data).hexdigest() != stored.sha256:
        raise FileRefused("file_corrupted", 500)
    return data


def attach_to_addition(db: Session, owner_account_id: int, file_ids, addition_id: int) -> list[StoredFile]:
    """Joint des photos de la personne à sa demande. Chaque photo : à elle,
    pour cet usage, jamais déjà jointe ailleurs. Verrou sur les lignes : une
    photo ne part jamais dans deux demandes."""
    if not isinstance(file_ids, (list, tuple)) or any(not isinstance(value, str) for value in file_ids):
        raise FileRefused("invalid_photos")
    unique = list(dict.fromkeys(file_ids))
    if len(unique) != len(file_ids) or len(unique) > MAX_PHOTOS_PER_ADDITION:
        raise FileRefused("invalid_photos")
    if not unique:
        return []
    rows = list(
        db.scalars(select(StoredFile).where(StoredFile.id.in_(unique)).with_for_update().order_by(StoredFile.id))
    )
    by_id = {row.id: row for row in rows}
    for file_id in unique:
        row = by_id.get(file_id)
        if (
            row is None
            or row.owner_account_id != owner_account_id
            or row.purpose != "service_photo"
            or row.service_addition_id is not None
            or row.deleted_at is not None
        ):
            raise FileRefused("invalid_photos")
    for file_id in unique:
        by_id[file_id].service_addition_id = addition_id
    db.flush()
    return [by_id[file_id] for file_id in unique]


def photos_of_addition(db: Session, addition_id: int) -> list[StoredFile]:
    return list(
        db.scalars(
            select(StoredFile)
            .where(StoredFile.service_addition_id == addition_id, StoredFile.deleted_at.is_(None))
            .order_by(StoredFile.created_at, StoredFile.id)
        )
    )


if __name__ == "__main__":
    print(new_key())
