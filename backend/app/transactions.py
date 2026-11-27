"""Validation différée : une action écrite pour valider elle-même peut
s'exécuter dans la transaction d'un appelant qui valide une seule fois, avec
la clé d'idempotence du message (backend/app/idempotency.py).

Dans `deferring(db)`, `commit(db)` écrit sans valider (flush) ; ailleurs, il
valide comme avant. Rien ne change pour un appel hors de `deferring`.
"""

from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy.orm import Session

_DEFERRED = "nexis_deferred_commit"


def deferred(db: Session) -> bool:
    return bool(db.info.get(_DEFERRED))


def commit(db: Session) -> None:
    if deferred(db):
        db.flush()
    else:
        db.commit()


@contextmanager
def deferring(db: Session):
    previous = db.info.get(_DEFERRED)
    db.info[_DEFERRED] = True
    try:
        yield db
    finally:
        if previous is None:
            db.info.pop(_DEFERRED, None)
        else:
            db.info[_DEFERRED] = previous
