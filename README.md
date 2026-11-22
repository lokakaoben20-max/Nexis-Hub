# Nexis Hub

Backend FastAPI, bot Telegram, Mini App et tâches de fond. Le backend PostgreSQL est la source de vérité des profils, missions et opérations financières.

## Démarrage local

Commandes à exécuter depuis la racine du dépôt. Utiliser un terminal séparé pour chaque processus.

1. Installer Python et Docker Compose. Installer les dépendances :

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install --require-hashes -r requirements.txt -r requirements-dev.txt
   Copy-Item .env.example .env
   ```

2. Renseigner dans `.env` les valeurs locales nécessaires : `BOT_TOKEN`, `DATABASE_URL`, `BACKEND_API_KEY_TELEGRAM` (identique entre backend, bot et Mini App, 32 caractères minimum). Le fichier compose fournit Postgres 17 et Redis 7. Le bot requiert Redis ; le backend exige la clé de service Telegram. Garder `APP_ENV=developpement` en local.

3. Démarrer Postgres et Redis :

   ```powershell
   docker compose up -d
   ```

4. Appliquer toutes les migrations avant de lancer le backend :

   ```powershell
   python -m alembic upgrade head
   ```

5. Démarrer le backend :

   ```powershell
   python -m uvicorn backend.app.main:app --reload
   ```

6. Dans d'autres terminaux, démarrer le bot puis le planificateur :

   ```powershell
   python main.py
   ```

   ```powershell
   python -m backend.app.taches planificateur
   ```

   Le planificateur intégré remplace Celery. Il utilise le calendrier de `backend/app/taches.py` et un verrou Postgres pour empêcher deux exécutions simultanées d'une même tâche.

La Mini App peut être lancée séparément sur le port 8001 :

```powershell
python -m uvicorn mini_app.app:app --reload --host 127.0.0.1 --port 8001
```

## Administration

Les administrateurs sont enregistrés dans `admin_roles`. Ajouter ou retirer un rôle exige une raison :

```powershell
python -m backend.app.admins ajouter <telegram_id> --raison "motif"
python -m backend.app.admins retirer <telegram_id> --raison "motif"
python -m backend.app.admins liste
```

`ADMIN_TELEGRAM_ID` ne désigne plus un administrateur. Il est ignoré pour l'autorisation et une valeur non vide est refusée hors développement.

Les admins Telegram peuvent consulter et changer les interrupteurs Mobile Money :

```text
/interrupteurs
/couper encaissements fraude suspectée
/rouvrir encaissements incident résolu
/couper versements incident agrégateur
/rouvrir versements incident résolu
```

Les flux disponibles sont `encaissements` et `versements`. Une raison est obligatoire ; l'état et chaque changement sont conservés en base. En dépannage depuis le serveur, utiliser `python -m backend.app.interrupteurs etat`, ou `couper|rouvrir <flux> --raison "..."`.

## Adresse publique et webhook

À ce HEAD, le code ne lit pas `NEXIS_PUBLIC_URL`. Il lit encore `MINI_APP_URL` pour les boutons Mini App et `WEBHOOK_URL` lorsque le bot tourne en mode webhook. Le tunnel de test communiqué, `https://nexishub.dpdns.org`, n'est pas encore raccordé à une variable publique unique.

Le bot démarre en polling par défaut. Le mode webhook demande `BOT_RUN_MODE=webhook`, `WEBHOOK_URL`, `WEBHOOK_SECRET_TOKEN` et un tunnel HTTPS pointant vers `WEBHOOK_LISTEN_HOST:WEBHOOK_LISTEN_PORT`. Le secret ne doit jamais être commité.

## Configuration

`.env.example` répertorie les variables lues par le code, y compris les variables de test et les anciennes clés que le code refuse hors développement. Aucun secret ne doit être ajouté au dépôt. Pour les règles métier et l'architecture cible WhatsApp, voir [docs/ARCHITECTURE_WHATSAPP.md](docs/ARCHITECTURE_WHATSAPP.md), [CONCEPTION_ARGENT.md](CONCEPTION_ARGENT.md) et [V5_MIGRATION_PLAN.md](V5_MIGRATION_PLAN.md).
