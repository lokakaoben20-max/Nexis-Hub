# Nexis Hub Mini App

Premiere version de la Mini App Telegram pour Nexis Hub.

## Lancer en local

Depuis le dossier du projet :

```powershell
cd C:\Users\CECBK\nexis_hub_bot
pip install -r requirements.txt
python -m uvicorn mini_app.app:app --reload --host 127.0.0.1 --port 8000
```

Ensuite, ouvre :

```text
http://127.0.0.1:8000
```

## Brancher a Telegram

Telegram Mini App demande une URL HTTPS. Pour tester, utilise un tunnel HTTPS comme ngrok ou Cloudflare Tunnel, puis ajoute l'URL dans `.env` :

```text
MINI_APP_URL=https://ton-url-https
```

Apres ca, redemarre le bot. Le bouton "Ouvrir Nexis Hub" apparaitra dans les menus client/prestataire et via la commande `/app`.
