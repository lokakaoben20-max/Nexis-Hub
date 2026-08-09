---
name: demarrage-local
description: À utiliser en démarrant le bot, le backend ou la Mini App en local, en diagnostiquant "ça ne répond pas"/"le port est pris"/"aucune sortie ne s'affiche", ou après un redémarrage de session. Capture les pièges déjà rencontrés sur cet environnement Windows précis — pas des conseils Docker/Python génériques.
---

# Démarrer et déboguer en local — spécifique à cet environnement

Trois services, trois ports, à lancer dans cet ordre (Postgres avant le
backend) :

| Service | Port | Commande |
| --- | --- | --- |
| Postgres | 5432 | `docker compose up -d` |
| Backend V5 | 8000 | `.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload` |
| Mini App | 8001 | `.venv\Scripts\python.exe -m uvicorn mini_app.app:app --reload --host 127.0.0.1 --port 8001` |
| Bot Telegram (polling, défaut) | — | `.venv\Scripts\python.exe main.py` |

Ne jamais mettre la Mini App sur 8000 — occupé par le backend
(`BACKEND_BASE_URL`). Voir `mini_app/README.md`.

## Démarrer le bot en mode webhook (optionnel)

Par défaut le bot tourne en long-polling (`BOT_RUN_MODE` absent ou
`polling`) — aucun geste supplémentaire. Pour tester le mode webhook
(`telegram_bot/webhook_server.py`) :

1. Lancer un tunnel HTTPS local : `ngrok http 8002` (ou Cloudflare Tunnel
   équivalent). Noter l'URL `https://...` affichée.
2. Dans `.env` : `BOT_RUN_MODE=webhook`, `WEBHOOK_URL=<url du tunnel, sans
   le chemin>`, `WEBHOOK_SECRET_TOKEN=<généré une fois avec
   python -c "import secrets; print(secrets.token_hex(32))">`.
3. Lancer `.venv\Scripts\python.exe main.py` comme d'habitude.

**L'URL ngrok change à chaque relance du tunnel** (offre gratuite) — à
remettre à jour dans `WEBHOOK_URL` à chaque session, puis redémarrer le bot
(`set_webhook` est rappelé à chaque démarrage, donc la nouvelle URL est
réenregistrée automatiquement côté Telegram, aucun autre geste nécessaire).
Si `python main.py` échoue immédiatement avec un message `WEBHOOK_URL
manquant` ou `WEBHOOK_SECRET_TOKEN manquant`, ces variables ne sont pas
posées dans `.env`. Si `set_webhook` échoue avec une erreur réseau, vérifier
que le tunnel est bien lancé et que l'URL dans `.env` est à jour.

Aucun hébergement de production n'existe pour ce projet — le mode webhook
n'est utilisable qu'avec un tunnel local pour l'instant.

## "Le bot/backend ne répond pas" — vérifier avant de paniquer

1. **Docker Desktop doit être ouvert**, pas seulement installé.
   `docker info` échoue silencieusement sinon (`dockerDesktopLinuxEngine`
   introuvable) — ce n'est pas une erreur de configuration, juste l'app pas
   lancée.
2. **`.venv` peut pointer vers un profil Windows qui n'existe plus.** Ce
   projet a déjà eu son `.venv\pyvenv.cfg` pointer vers
   `C:\Users\CECBK\...` après un changement de profil. Vérifier
   `.venv\pyvenv.cfg` si `python.exe` semble absent alors que le dossier
   `.venv` existe.
3. **Le port peut déjà être occupé par une instance précédente**, en
   particulier après une session interrompue. `netstat -ano | grep ":8000"`
   pour trouver le PID, avant de relancer.
4. **La sortie d'un process lancé en arrière-plan met du temps à
   apparaître** — buffering stdout Windows, pas un crash. Un process qui
   tourne (confirmé par `Get-Process`) sans sortie visible après quelques
   secondes n'est pas forcément en échec ; attendre ou relancer avec
   `PYTHONUNBUFFERED=1` avant de conclure à un bug.

## Après un redémarrage de session ou de machine

Les process lancés en arrière-plan lors d'une session précédente ne survivent
pas à une interruption — ils ne se relancent pas tout seuls, et leurs
sockets peuvent rester dans un état intermédiaire quelques secondes. Après un
redémarrage : relancer les 3 services dans l'ordre, ne jamais supposer qu'un
service "tournait encore" sans le revérifier (`docker ps`, `curl
127.0.0.1:8000/health`).

## Nettoyer avant de relancer

`Get-Process python | Stop-Process -Force` arrête tout (bot + backend + tests
en cours) sans distinction — utile pour repartir propre, mais vérifier
qu'aucun test (`pytest`) n'est en train de tourner avant de le faire, sinon le
résultat est perdu sans notification claire.
