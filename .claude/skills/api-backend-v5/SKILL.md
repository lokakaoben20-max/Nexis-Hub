---
name: api-backend-v5
description: À utiliser en ajoutant, modifiant ou lisant un endpoint de backend/app/main.py (FastAPI). Les 26 endpoints existants suivent des conventions cohérentes mais non imposées par un outil — un nouvel endpoint qui s'en écarte crée une incohérence silencieuse plutôt qu'une erreur.
---

# Conventions API — backend/app/main.py

26 endpoints existent aujourd'hui, tous écrits à la main dans le même style.
Rien ne force ce style (pas de générateur, pas de classe de base) — le suivre
est une discipline, pas une contrainte du framework.

## Le pattern à reproduire

```python
class QuoteCreatePayload(BaseModel):
    mission_id: int
    provider_telegram_id: int
    amount: float
    currency: str = "USD"
    delay_hours: int
    message: str = ""


@app.post("/api/bot/quotes")
def create_quote(payload: QuoteCreatePayload):
    with SessionLocal() as db:
        quote = crud.create_quote(db, mission_id=payload.mission_id, ...)
        if quote is None:
            raise HTTPException(status_code=404, detail="mission_not_found")
        return {"status": "ok", "quote": _quote_to_dict(quote)}
```

- **Un `BaseModel` Pydantic par endpoint** qui écrit ou modifie (`XxxPayload`),
  nommé sur le nom de la ressource — jamais de `dict` brut en paramètre.
- **Toute la logique réelle vit dans `crud.py`**, jamais dans `main.py`.
  L'endpoint ouvre la session, appelle `crud.xxx(db, ...)`, traduit le
  résultat. Ne jamais écrire de requête SQLAlchemy directement dans
  `backend/app/main.py`.
- **Deux conventions d'échec dans `crud.py`**, à ne pas mélanger :
  - retour `None` → l'appelant fait `raise HTTPException(404, ...)`
  - `raise ValueError("message en français")` → l'appelant fait
    `except ValueError as exc: raise HTTPException(400, detail=str(exc)) from exc`
- **Un helper `_xxx_to_dict()` par modèle** (`_quote_to_dict`, `_mission_to_dict`,
  `_provider_to_dict`, `_user_to_dict`, `_review_to_dict`) pour sérialiser —
  jamais `response_model=` (le projet ne l'utilise nulle part), jamais renvoyer
  l'objet SQLAlchemy tel quel.
- **Réponse toujours `{"status": "ok", "<ressource>": {...}}`** sur succès.
- `with SessionLocal() as db:` ouvert dans l'endpoint lui-même, jamais
  injecté via `Depends()` — le projet n'utilise pas ce mécanisme FastAPI ici.

## Sécurité — voir le skill `securite-backend`

Aucun de ces 26 endpoints n'est authentifié. Avant d'en ajouter un qui touche
à l'argent (paiement, escrow, wallet) ou à des données personnelles, consulter
`securite-backend`.

## Miroir côté legacy

La plupart de ces endpoints ont un équivalent dans `db.py` que le bot appelle
en direct (le backend V5 est encore un miroir, pas la source de vérité — voir
`AGENTS.md`). Un nouvel endpoint backend n'a de sens que si `main.py` (le bot)
va effectivement l'appeler. Vérifier `V5_MIGRATION_PLAN.md` pour savoir si le
flow concerné est déjà basculé côté lecture, ou seulement synchronisé en
écriture.
