---
name: securite-backend
description: À utiliser avant d'exposer le backend V5 sur un réseau, d'ajouter un endpoint qui lit ou modifie des données d'utilisateur, de toucher à l'argent (paiement, escrow, wallet, commission), ou de manipuler des secrets (BOT_TOKEN, identifiants de base). Le backend V5 n'a AUCUNE authentification aujourd'hui — ce skill dit ce qui est protégé, ce qui ne l'est pas, et ce qu'il faut faire avant une mise en production.
---

# Sécurité — Nexis Hub

## Le point critique : le backend V5 est entièrement ouvert

`backend/app/main.py` expose **26 endpoints sans aucune authentification**.
Aucun `Depends()`, aucun header vérifié, aucune clé d'API. N'importe qui capable
d'atteindre le service peut :

| Endpoint | Ce qu'un inconnu peut faire |
| --- | --- |
| `GET /api/profile/{telegram_id}` | Lire le profil, le téléphone et les soldes wallet de n'importe qui |
| `POST /api/bot/quotes/{id}/pay` | Marquer un devis comme payé |
| `POST /api/bot/missions/{id}/release` | **Libérer l'escrow** et créditer un wallet prestataire |
| `POST /api/bot/providers` | Créer ou écraser un profil prestataire |
| `PATCH /api/bot/users/{id}/name` | Renommer n'importe quel utilisateur |

**Ce qui protège aujourd'hui, c'est uniquement le réseau** : le service écoute
sur `127.0.0.1:8000`, donc il n'est joignable que depuis la machine. Cette
protection disparaît à la seconde où il est déployé, mis derrière un tunnel
(ngrok, Cloudflare) ou exposé sur `0.0.0.0`.

**Règle** : ne jamais exposer ce backend hors de `127.0.0.1` sans avoir ajouté
une authentification. Si on demande de le déployer ou de le rendre accessible,
le signaler avant de le faire.

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

## Ce qu'il faut avant une mise en production

1. **Authentifier le canal bot → backend.** Le bot est le seul client légitime :
   un secret partagé en en-tête, vérifié par une dépendance FastAPI, suffit pour
   commencer. Il doit vivre dans `.env`, jamais dans le code.
2. **Cloisonner les endpoints d'argent** (`/pay`, `/pay-wallet`, `/release`) —
   ce sont eux qui déplacent des soldes.
3. **Limiter le débit** sur les endpoints publics.
4. **Journaliser** les opérations d'argent (qui, quand, combien).

## Secrets

- `.env` contient `BOT_TOKEN` et n'est **pas** suivi par Git (`.gitignore`) —
  garder cet état.
- Ne jamais écrire un token, un identifiant ou un mot de passe dans un message
  de commit, un test, un log ou un fichier de documentation.
- Les tests utilisent un token factice explicite (`TEST_TOKEN` dans
  `tests/test_mini_app.py`) — reproduire ce choix, ne jamais lire le vrai `.env`
  dans un test.
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
