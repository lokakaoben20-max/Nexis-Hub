---
name: nouvelle-fonctionnalite
description: À utiliser avant d'écrire le premier code d'une fonctionnalité nouvelle (pas une correction) qui touche à des données métier — où doit-elle vivre pendant que le projet migre de db.py vers le backend V5 ? Cette décision a déjà été prise deux fois différemment dans ce projet, avec de bonnes raisons dans les deux cas.
---

# Où fait vivre une fonctionnalité nouvelle ? (db.py legacy vs backend V5)

Le projet migre progressivement de SQLite (`db.py`) vers Postgres via le
backend V5 (`backend/app/`) — voir `V5_MIGRATION_PLAN.md`. Tant que la
migration n'est pas terminée, chaque fonctionnalité nouvelle doit choisir où
vivre. Deux précédents opposés existent dans ce projet, tous deux
volontaires :

## Précédent A — legacy-first, puis synchronisé (inscription, devis, paiement)

Ces flows existaient déjà dans `db.py` avant le backend V5. Le motif suivi a
été : écrire/modifier dans `db.py` d'abord (source de vérité), puis appeler
le backend en best-effort via `_safe_backend_call(...)` pour le tenir à jour.
Si le backend est injoignable, le flow continue quand même — l'utilisateur
n'attend jamais après le miroir.

## Précédent B — backend-first (reviews/notation)

La notation prestataire n'existait dans **aucune** des deux couches avant
d'être construite. Décision explicite : la construire directement contre le
backend (`POST /api/bot/reviews`), sans jamais toucher `db.py`. Raison
retenue : dupliquer une table + une logique de calcul dans `db.py` pour une
fonctionnalité qui n'y a jamais existé va à l'encontre du sens de la
migration, et crée un troisième endroit à garder synchronisé pour rien.

## La règle qui en découle

- **La fonctionnalité touche un flow qui existe déjà dans `db.py`** (missions,
  devis, paiement, profils, wallet) → l'étendre là où il vit, `db.py` reste
  la source de vérité, synchroniser vers le backend en best-effort. Voir le
  skill `parite-donnees` pour la liste des fonctions à garder en parité.
- **La fonctionnalité est entièrement neuve** (n'existe dans aucune des deux
  couches) → la construire backend-first, sans réplique SQLite. C'est le sens
  de la migration, et ça évite un troisième point de synchronisation.
- **Cas ambigu** (une petite partie existe déjà côté legacy) → le dire
  explicitement à l'utilisateur avant de coder ; ce n'est pas une décision
  purement technique, `V5_MIGRATION_PLAN.md` documente les arbitrages déjà
  pris dans un sens ou l'autre pour éviter de re-trancher deux fois la même
  question.

Dans les deux cas : mettre à jour `V5_MIGRATION_PLAN.md` avec la décision et
sa raison, comme fait pour chaque flow migré jusqu'ici — c'est ce qui permet
au prochain agent (ou à soi-même dans six mois) de ne pas redécouvrir le
raisonnement à zéro.
