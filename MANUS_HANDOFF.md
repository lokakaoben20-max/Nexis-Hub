# Guide de prise en main du projet

## Objectif du projet
Ce dépôt contient un bot Telegram pour Nexis Hub avec une migration progressive vers une architecture V5 backend-driven.

## Structure principale
- main.py : logique du bot Telegram, handlers, synchronisation vers le backend V5.
- db.py : couche de persistence legacy SQLite et logique métier locale.
- messages.py : messages du bot (fr / ln / en).
- backend/app/main.py : backend V5 minimal en FastAPI avec endpoints bot et profil.
- tests/ : tests de régression pour le bot et la migration V5.
- backend/tests/ : tests du backend V5.
- mini_app/ : mini-app web liée au projet.

## État actuel
- Le bot est connecté à un backend V5 pour plusieurs flux clés :
  - inscription utilisateur
  - création de mission
  - profil
  - lifecycle mission
  - paiement
- Le backend V5 est encore simple, mais il persiste maintenant son état sur disque via un fichier JSON.
- La couche legacy SQLite reste présente comme fallback pendant la migration.

## Fichiers à consulter en priorité
- [main.py](main.py) : pour les flows bot et la synchronisation V5.
- [db.py](db.py) : pour la logique legacy et les fonctions métier.
- [backend/app/main.py](backend/app/main.py) : pour les endpoints V5.
- [tests/test_bot_backend_sync.py](tests/test_bot_backend_sync.py) : pour les tests de synchronisation bot/backend.
- [backend/tests/test_main.py](backend/tests/test_main.py) : pour les tests backend.

## Commandes utiles
### Tests
```bash
c:/Users/CECBK/nexis_hub_bot/.venv/Scripts/python.exe -m pytest -q
```

### Lancer le bot
```bash
c:/Users/CECBK/nexis_hub_bot/.venv/Scripts/python.exe main.py
```

### Vérifier l’état Git
```bash
git status
git branch
git remote -v
```

## Branch Git actuelle
- Branche de travail : feature/v5-migration

## Prochaine étape logique
1. Continuer la migration des flows encore dépendants de la DB legacy.
2. Rendre le backend V5 plus complet (base de données réelle si souhaité).
3. Réduire progressivement les dépendances à l’ancienne logique locale.

## Points sensibles à ne pas casser
- Les handlers Telegram utilisent des callbacks et états FSM.
- Les fonctions de synchronisation vers le backend doivent rester tolérantes aux erreurs réseau.
- Les tests sont un bon garde-fou avant toute modification majeure.
