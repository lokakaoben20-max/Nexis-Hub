---
name: securite-backend
description: À utiliser avant d'exposer le backend V5 sur un réseau, d'ajouter un endpoint qui lit ou modifie des données d'utilisateur, de toucher à l'argent (paiement, escrow, wallet, commission), ou de manipuler des secrets (BOT_TOKEN, BACKEND_API_KEY, identifiants de base). Décrit l'authentification par clé partagée déjà en place entre le bot et le backend V5, et ce qui reste à faire avant une vraie mise en production.
---

# Sécurité — Nexis Hub

## Le backend V5 est protégé par une clé partagée (bot ↔ backend uniquement)

`backend/app/main.py` exige un en-tête `X-API-Key` sur toutes ses routes
`/api/*`, vérifié en temps constant (`hmac.compare_digest`) contre
`BACKEND_API_KEY` (`.env`, jamais commité). Seule `GET /health` reste ouverte,
volontairement, pour la supervision.

Implémentation : un `APIRouter(dependencies=[Depends(verify_api_key)])`
regroupe les 25 routes protégées ; `app.include_router(router)` les monte. Un
nouvel endpoint ajouté via `@router.` (pas `@app.`) hérite automatiquement de
la protection — c'est le seul détail à ne pas oublier en en ajoutant un.

Côté bot, `main.py` définit `BACKEND_AUTH_HEADERS = {"X-API-Key": BACKEND_API_KEY}`
et le passe à `httpx.AsyncClient(timeout=5.0, headers=BACKEND_AUTH_HEADERS)`
sur chacun de ses appels au backend. **Tout nouvel appel HTTP vers le backend
doit reprendre ce même client** — en créer un sans `headers=` produit un 401
silencieux (les `sync_*` de `main.py` avalent l'erreur via
`_safe_backend_call`).

**Ce que ça protège** : n'importe qui capable d'atteindre le port 8000 sans
connaître `BACKEND_API_KEY` ne peut ni lire de profil, ni libérer un escrow,
ni créer un prestataire. **Ce que ça ne protège toujours pas** : c'est un
secret unique partagé par un seul client de confiance (le bot) — pas une
authentification par utilisateur final. Si le backend doit un jour recevoir
des requêtes directement d'un navigateur ou d'un tiers, il faudra un vrai
mécanisme par utilisateur (voir la Mini App ci-dessous).

**Règle** : ne jamais exposer ce backend hors de `127.0.0.1` sans que
`BACKEND_API_KEY` soit définie et forte. Si on demande de le déployer ou de le
rendre accessible depuis l'extérieur, le signaler avant de le faire.

## L'implémentation de référence existe déjà dans le projet

`mini_app/app.py` fait les choses correctement — s'en inspirer plutôt que
réinventer :

- `verify_telegram_init_data()` valide la signature Telegram (`initData`)
  conformément au spec : `secret_key = HMAC(b"WebAppData", BOT_TOKEN)`, puis
  hash du `data_check_string` trié
- comparaison en **temps constant** via `hmac.compare_digest` (pas `==`)
- vérification d'expiration de la session (`auth_date`)
- **chaque** route porte `Depends(verify_telegram_init_data)` **et**
  `require_same_telegram_user(...)` — signature valide ≠ droit d'agir sur
  autrui

Ces garanties sont couvertes par `tests/test_mini_app.py`. Toute modification de
cette fonction doit laisser ces tests passer — et il faut vérifier qu'ils
échouent si on casse la vérification (test de mutation), sinon ils ne prouvent
rien.

## Ce qu'il reste avant une vraie mise en production

1. **Rotation de `BACKEND_API_KEY`.** Un secret unique, jamais renouvelé,
   compromis une fois = compromis pour toujours. Prévoir un mécanisme de
   rotation avant un vrai déploiement.
2. **Cloisonner davantage les endpoints d'argent** (`/pay`, `/pay-wallet`,
   `/release`) — la clé API protège l'accès, mais tout appelant qui la connaît
   peut aujourd'hui tout faire ; pas de granularité par action.
3. **Limiter le débit** sur les routes exposées.
4. **Journaliser** les opérations d'argent (qui, quand, combien).

## Secrets

- `.env` contient `BOT_TOKEN` et `BACKEND_API_KEY`, et n'est **pas** suivi par
  Git (`.gitignore`) — garder cet état.
- Ne jamais écrire un token, une clé ou un mot de passe dans un message de
  commit, un test, un log ou un fichier de documentation.
- Les tests utilisent des valeurs factices explicites (`TEST_API_KEY` dans
  `backend/tests/test_main.py`, `TEST_TOKEN` dans `tests/test_mini_app.py`) —
  reproduire ce choix, ne jamais lire le vrai `.env` dans un test.
- `docker-compose.yml` contient des identifiants Postgres en clair : acceptable
  pour du local, à remplacer par des secrets d'environnement avant tout
  déploiement.

## L'argent n'est pas réel (pour l'instant)

Le flux d'escrow est **simulé** : `operator="mobile_money_simulation"`, les
soldes wallet sont des nombres en base, aucun opérateur de paiement n'est
branché. Ne jamais laisser entendre le contraire dans un message, un commit ou
une réponse à l'utilisateur.

L'intégration réelle (CinetPay / FlexPay) est la Phase 6 du plan de migration et
demandera une revue de sécurité dédiée — voir `V5_MIGRATION_PLAN.md`.
