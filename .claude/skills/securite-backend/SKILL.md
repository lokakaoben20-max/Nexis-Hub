---
name: securite-backend
description: À utiliser avant d'exposer le backend V5 sur un réseau, d'ajouter un endpoint qui lit ou modifie des données d'utilisateur, de toucher à l'argent (paiement, escrow, wallet, commission), ou de manipuler des secrets (BOT_TOKEN, clés BACKEND_API_KEY_*, identifiants de base). Décrit l'authentification par clé de service par canal (Telegram, WhatsApp) déjà en place, et ce qui reste à faire avant une vraie mise en production.
---

# Sécurité — Nexis Hub

## Le backend V5 est protégé par une clé de service par canal

`backend/app/main.py` exige un en-tête `X-API-Key` sur toutes ses routes
`/api/*` (sauf le webhook de l'agrégateur, signé à part). **La clé dit quel
canal appelle** (`backend/app/service_keys.py`) :

- `BACKEND_API_KEY_TELEGRAM` : bot Telegram et Mini App (obligatoire) ;
- `BACKEND_API_KEY_WHATSAPP` : service WhatsApp, clients seulement
  (facultative tant que ce service ne tourne pas).

Comparaison en temps constant contre toutes les clés. Le backend, le bot et la
Mini App **refusent de démarrer** si l'ancienne clé unique `BACKEND_API_KEY`
est encore dans le `.env`, si la clé Telegram manque, si une clé fait moins de
32 caractères ou si deux canaux partagent la même. Seule `GET /health` reste
ouverte, pour la supervision.

Implémentation : `APIRouter(dependencies=[Depends(verify_service_key)])`. Un
nouvel endpoint déclaré via `@router.` (jamais `@app.`) hérite de la
protection, **et n'est ouvert qu'au canal Telegram par défaut**. Règles :

- `@open_to(ledger.TELEGRAM, ledger.WHATSAPP)` ouvre explicitement une route à
  WhatsApp. C'est une décision : l'ajouter aussi à `WHATSAPP_ROUTES` dans
  `backend/tests/test_whatsapp_channel.py`, avec ses tests de parité.
- `@provider_action` marque une action de prestataire : jamais ouverte à
  WhatsApp (erreur à l'import si on essaie), refus
  `provider_channel_forbidden`. Toute nouvelle action de prestataire doit
  porter ce marqueur et figurer dans `PROVIDER_ROUTES` du même test.
- L'acteur déclaré (`X-Actor-Channel`) doit être le canal de la clé
  (`actor_channel_mismatch` sinon) : le service WhatsApp ne peut jamais agir
  au nom d'une personne Telegram, ni l'inverse. L'acteur WhatsApp est le BSUID
  de Meta (`CD.1234…`), jamais le numéro.

Côté bot et Mini App, `telegram_bot/backend_client.py` définit
`BACKEND_AUTH_HEADERS` (clé Telegram) et `actor_headers(...)`. **Tout nouvel
appel HTTP vers le backend doit reprendre ces en-têtes** — un client sans
`headers=` produit un 401 silencieux (les `sync_*` avalent l'erreur via
`_safe_backend_call`).

**Ce que ça protège** : sans une clé, rien n'est lisible ni modifiable ; avec
la clé WhatsApp, seules les routes client ouvertes à WhatsApp le sont, au nom
d'une personne WhatsApp. **Ce que ça ne protège toujours pas** : ce n'est pas
une authentification par utilisateur final ; un canal compromis peut agir au
nom de n'importe quelle personne de son canal. Les règles d'argent restent
vérifiées par le registre (propriétaire, état, montant).

**Règle** : ne jamais exposer ce backend hors de `127.0.0.1` sans clés fortes.
Si on demande de le déployer ou de le rendre accessible depuis l'extérieur, le
signaler avant de le faire.

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

1. **Rotation des clés de service.** Une clé jamais renouvelée, compromise
   une fois = compromise pour toujours. Prévoir un mécanisme de rotation
   avant un vrai déploiement.
2. **Cloisonner davantage les endpoints d'argent** (`/api/bot/missions/{id}/fund`,
   `/confirm`, `/dispute/resolve`…) — la clé API protège l'accès, mais tout
   appelant qui la connaît peut aujourd'hui tout faire ; pas de granularité
   par action. Les règles d'argent elles-mêmes (propriétaire, état, montant,
   double paiement) sont vérifiées par le registre (`backend/app/ledger.py`).
3. **Limiter le débit** sur les routes exposées.
4. **Journaliser** l'accès aux opérations d'argent (le registre trace déjà
   qui, quand et combien dans `money_operations`).

## Secrets

- `.env` contient `BOT_TOKEN` et les clés `BACKEND_API_KEY_*`, et n'est **pas** suivi par
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

Le registre d'argent est réel (`backend/app/ledger.py`) mais l'encaissement
Mobile Money est encore **simulé** (référence `SIM-…`) : aucun agrégateur
n'est branché. Ne jamais laisser entendre le contraire dans un message, un
commit ou une réponse à l'utilisateur.

L'intégration réelle (FlexPaie, choisie par Ben) est décrite dans
`CONCEPTION_MOBILE_MONEY.md` : aucun branchement réel avant le KYC validé et
la signature des webhooks confirmée par écrit, puis revue de sécurité dédiée.
