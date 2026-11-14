---
name: nouvelle-fonctionnalite
description: À utiliser avant d'écrire le premier code d'une fonctionnalité nouvelle (pas une correction) qui touche à des données métier — où elle vit, et ce qu'il faut écrire avec elle.
---

# Où vit une fonctionnalité nouvelle ?

Toujours dans le backend (`backend/app/`), seule mémoire de Nexis : profils,
missions, devis, argent. Il n'y a plus de couche SQLite legacy (`db.py`
supprimé le 2026-11-14) ni de copie locale dans le bot ou la Mini App.

- Les règles vivent dans un module du backend (`profils.py`, `crud.py`,
  `ledger.py`…), testées sur SQLite et sur Postgres.
- Les canaux (bot Telegram, Mini App, WhatsApp, app mobile) demandent au
  backend au nom de la personne (routes `/api/me/*`) et affichent sa réponse.
  Backend injoignable : « service indisponible », rien n'est écrit.
- Argent : voir `CONCEPTION_ARGENT.md` (atomique, idempotent, une seule
  source).
- Les tests du bot passent par le vrai backend en mémoire (fixture
  `live_backend` de `tests/conftest.py`).

**Cas ambigu** (la fonctionnalité change une règle déjà décidée par Ben) → le
dire explicitement avant de coder ; ce n'est pas une décision purement
technique.
