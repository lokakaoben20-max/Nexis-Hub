---
name: parite-donnees
description: À utiliser dès qu'une logique métier ou une lecture de données touchant les missions, devis, paiements, prestataires, clients ou wallets est ajoutée ou modifiée — que ce soit dans db.py, backend/app/crud.py, main.py ou mini_app/app.py. Ce projet maintient la MÊME logique métier en double (SQLite legacy + backend Postgres) et manipule deux formes d'objet mission incompatibles ; ce skill dit quoi vérifier pour ne pas créer de divergence silencieuse.
---

# Parité des données — Nexis Hub

Ce projet est à mi-chemin d'une migration. Deux pièges structurels en découlent,
et ils ne se voient **ni à l'exécution ni à la relecture** : le code marche, il
donne juste des résultats différents selon le chemin emprunté.

## Piège 1 — 20 fonctions métier existent en double

La même logique vit dans `db.py` (SQLite legacy) **et** `backend/app/crud.py`
(Postgres). Modifier l'une sans l'autre crée une divergence : le bot calcule un
montant, le backend en enregistre un autre.

Fonctions concernées (vérifier la jumelle avant de committer) :

```
accept_quote, calculate_payment_amounts, create_mission, create_quote,
find_matching_providers, finish_mission, mark_quote_paid,
mark_quote_paid_with_wallet, reject_quote, release_payment,
reset_consecutive_ignored, set_provider_suspended, set_provider_verified,
start_mission, update_consecutive_ignored, update_provider_language,
update_provider_services, update_provider_status, update_user_language,
update_user_name
```

Vérifier la liste réelle plutôt que se fier à celle-ci :

```bash
.venv/Scripts/python.exe -c "
import re
db=set(re.findall(r'^def (\w+)',open('db.py',encoding='utf-8').read(),re.M))
crud=set(re.findall(r'^def (\w+)',open('backend/app/crud.py',encoding='utf-8').read(),re.M))
print('\n'.join(sorted(db&crud)))
"
```

**Règle** : si la fonction touchée est dans cette liste, la modification va dans
les deux fichiers, ou nulle part. Si elle diverge volontairement, l'écrire en
commentaire dans les deux.

## Piège 2 — deux formes de mission incompatibles

| Source | Type Python | Identifiant | Nom du prestataire |
| --- | --- | --- | --- |
| `db.py` (local) | `sqlite3.Row` | `mission["id"]` | `mission["provider_name"]` |
| Backend V5 | `dict` | `mission["mission_id"]` | **absent** |

Conséquences déjà constatées en production :

- `isinstance(mission, dict)` est **faux** pour un `sqlite3.Row` → tout filtre
  écrit ainsi jette silencieusement les missions locales (écran vide dès que le
  backend est éteint).
- `format_mission_client()` lit `mission["provider_name"]` → `KeyError` sur une
  mission venant du backend.
- `.get()` n'existe pas sur `sqlite3.Row` → `AttributeError`.

**Règle** : ne jamais supposer la forme. Lire les champs via un accès tolérant
aux deux (`"id" in mission.keys()` fonctionne sur les deux types), et tester le
chemin backend **et** le chemin local.

## Piège 3 — un placeholder peut masquer la vraie donnée

`GET /api/profile/{id}` renvoyait un faux `{"first_name": "Client"}` quand
l'utilisateur n'existait pas côté backend, indiscernable d'une vraie donnée. Le
bot préférait cette réponse à sa valeur locale fraîche → les modifications de
l'utilisateur semblaient ignorées.

**Règle** : côté backend, renvoyer `None` pour une entité absente, jamais un
objet de remplacement. Côté appelant, utiliser `payload.get("client") or {}` —
`.get("client", {})` ne protège pas d'une valeur `None` explicite.

## Avant de committer

1. La fonction jumelle est-elle à jour ? (piège 1)
2. Le code marche-t-il avec les deux formes de mission ? (piège 2)
3. Les comptes existent-ils des deux côtés ? Sinon :
   `.venv/Scripts/python.exe backfill_providers_to_backend.py`
   `.venv/Scripts/python.exe backfill_users_to_backend.py`
4. Tests ciblés d'abord (la suite complète prend 4 à 8 minutes) :
   ```bash
   .venv/Scripts/python.exe -m pytest backend/tests/test_main.py -q
   ```
   puis la suite complète avant de committer :
   ```bash
   .venv/Scripts/python.exe -m pytest -q
   ```

## Si la modification touche à l'argent

Montants, commissions, frais, soldes wallet, escrow : la logique de paiement est
**simulée**, aucun argent réel ne circule (`operator="mobile_money_simulation"`).
Ne pas laisser croire l'inverse. Toute modification de montant doit être
répercutée dans les deux `calculate_payment_amounts` **et** dans les tests qui
figent les valeurs attendues (`tests/test_mission_flow.py`,
`backend/tests/test_main.py`).
