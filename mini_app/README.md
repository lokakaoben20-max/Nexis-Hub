# Nexis Hub Mini App

Première version de la Mini App Telegram pour Nexis Hub.

## Lancer en local

La Mini App écoute sur le **port 8001**, et non 8000 : ce dernier est déjà pris par
le backend V5 (`BACKEND_BASE_URL` dans `.env.example`, lancé via
`uvicorn backend.app.main:app`). Les deux services peuvent ainsi tourner en même temps.

Depuis le dossier du projet :

```powershell
cd "C:\Users\Ben L\OneDrive\Desktop\Startup_Nexis_Hub\nexis_hub_bot"
.venv\Scripts\python.exe -m uvicorn mini_app.app:app --reload --host 127.0.0.1 --port 8001
```

Ensuite, ouvre :

```text
http://127.0.0.1:8001
```

## Brancher à Telegram

Telegram Mini App demande une URL HTTPS. Pour tester, utilise un tunnel HTTPS comme
ngrok ou Cloudflare Tunnel **pointant vers le port 8001**, puis ajoute l'URL dans `.env` :

```text
MINI_APP_URL=https://ton-url-https
```

Après ça, redémarre le bot. Le bouton « Ouvrir Nexis Hub » apparaîtra dans les menus
client/prestataire et via la commande `/app`.

## Note d'architecture

La Mini App lit et écrit **directement dans `db.py`** (SQLite legacy) — elle n'est pas
encore passée par le backend V5, contrairement au bot. C'est un chantier de migration
à part entière, pas encore lancé (voir `V5_MIGRATION_PLAN.md`).

Elle ne couvre aujourd'hui que le **côté prestataire** (inscription, services, statut,
démarrage/fin de mission). Aucun parcours client n'y est implémenté.

## Audit de sécurité (2026-08-06) — ce qui reste ouvert

L'authentification elle-même (`verify_telegram_init_data`) est solide et
couverte par `tests/test_mini_app.py` (signature HMAC en temps constant,
cloisonnement par utilisateur, validation d'entrée). Un test de mutation a
confirmé que les tests d'auth échouent vraiment si la vérification est
cassée. Ce qui reste, par ordre décroissant d'impact :

1. **Ré-inscription = écrasement silencieux.** `POST
   /api/provider/{id}/register` fait un `UPSERT` (`create_provider` dans
   `db.py`) sans distinguer une première inscription d'une modification —
   un prestataire qui se réinscrit voit son profil écrasé et son statut
   remis à `available`, sans confirmation ni avertissement.
2. **Expiration de session fragile.** `mini_app/app.py:139` :
   `if auth_date and time.time() - auth_date > 86400:` — si `auth_date`
   vaut `0` ou est absent, la vérification d'expiration est simplement
   sautée. Non exploitable aujourd'hui (le hash Telegram couvre ce champ,
   donc le falsifier invalide la signature), mais fragile : un futur
   changement qui découplerait la vérification du hash de celle de
   l'expiration réactiverait ce trou silencieusement.
3. **Fenêtre de session de 24h** — longue pour une WebApp qui ne fait que
   des actions ponctuelles (inscription, changement de statut).
4. **Listes dupliquées et divergentes.** `COMMUNES` (`mini_app/app.py:58`)
   et `FALLBACK_SERVICES` (`mini_app/app.py:38`) sont recopiées en dur,
   séparément des listes utilisées par `main.py` (le bot) — un service ou
   une commune ajoutée d'un côté ne l'est pas forcément de l'autre.

Aucun de ces 4 points n'a de correctif appliqué à ce jour — décision
volontaire de prioriser les tests d'abord (fait) avant la correction.
