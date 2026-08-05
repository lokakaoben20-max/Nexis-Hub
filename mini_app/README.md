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
