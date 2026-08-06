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
| Bot Telegram | — | `.venv\Scripts\python.exe main.py` |

Ne jamais mettre la Mini App sur 8000 — occupé par le backend
(`BACKEND_BASE_URL`). Voir `mini_app/README.md`.

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
