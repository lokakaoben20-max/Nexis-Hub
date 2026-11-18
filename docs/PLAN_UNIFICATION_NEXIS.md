# NEXIS — Plan de fusion réfléchie des dépôts

**Dépôt principal :** `lokakaoben20-max/Nexis-Hub`  
**Dépôt de référence :** `lokakaoben20-max/nexis-hub-v5`  
**Branche de travail :** `develop/nexis-unification`  
**Principe :** intégrer progressivement les améliorations utiles, sans remplacer le produit existant ni modifier `main` directement.

## 1. État constaté (18 novembre 2026)

### Dépôt principal : conserver comme fondation
- Bot Telegram Aiogram avec inscription client/prestataire, demandes, devis, missions, statut et fonctions administratives (`main.py`, `db.py`).
- Base SQLite avec une logique métier déjà présente (`db.py`).
- Mini-app FastAPI avec pages HTML/JS/CSS, authentification des données Telegram et contrôle d'identité sur plusieurs routes (`mini_app/`).
- API FastAPI de synchronisation bot/backend (`backend/app/main.py`) utilisant actuellement un dictionnaire en mémoire (`APP_STATE`), donc non persistant.
- Tests de parcours et de synchronisation (`tests/`).

### Dépôt V5 : source d'idées, pas remplacement immédiat
- Structure FastAPI + PostgreSQL/SQLAlchemy, Redis, Celery, Kafka, Docker et configuration.
- Modèles de données plus complets pour utilisateurs, prestataires, missions, devis, paiements et notifications.
- Mais les routes métiers de l'API V5 sont largement absentes (`backend/app/main.py`).
- Plusieurs tâches annoncées (paiement, IA, relances, antifraude, transcription) sont des squelettes `TODO` / `pass` (`backend/app/tasks.py`).
- Le bot Telegram V5 propose surtout des réponses simples, alors que le bot principal possède les parcours.
- Le README V5 annonce des fonctionnalités comme « escrow réel » et « IA » qui ne sont pas démontrées par leur implémentation : ne pas les considérer comme déjà opérationnelles.

## 2. Décisions d'architecture

1. **Une seule source principale :** `Nexis-Hub`. L'autre dépôt reste consultable, sans migration brutale de fichiers.
2. **Préserver l'expérience existante :** bot Telegram, mini-app et parcours de mission doivent continuer de fonctionner à chaque étape.
3. **D'abord sécuriser, puis migrer :** avant d'exposer une nouvelle API, contrôler l'identité et les droits sur chaque route protégée; ne pas faire confiance aux états de paiement transmis par le client.
4. **Base de données :** concevoir une migration vérifiable SQLite → PostgreSQL, avec sauvegarde préalable, correspondance des champs et test de restauration. Ne pas supprimer SQLite tant que la migration n'est pas validée.
5. **Infrastructure proportionnée :** PostgreSQL peut être utile rapidement; Redis/Celery seront ajoutés selon un besoin confirmé; Kafka ne sera envisagé que si le volume et les événements le justifient.
6. **Paiements réels :** distinguer les statuts internes de test des confirmations de prestataires de paiement; aucune libération d'argent sans confirmation serveur fiable, journal de transactions et traitement des échecs.
7. **IA sous supervision humaine :** assistants clients/prestataires/administration, aide à la validation des pièces et détection de signaux de fraude; aucune décision irréversible basée uniquement sur l'IA. Prévoir consentement, confidentialité, audit et procédure de contestation.

## 3. Phases de réalisation

### Phase A — Sécurité et tests de référence (priorité immédiate)
- [ ] Corriger le contrôle administrateur : l'absence de `ADMIN_TELEGRAM_ID` ne doit pas donner les droits administrateur (`main.py`).
- [ ] Examiner les routes `backend/app/main.py` : authentification, autorisation, validation des transitions de mission et de paiement.
- [ ] Vérifier les contrôles de session et d'identité de la mini-app.
- [ ] Ajouter des tests de sécurité et exécuter les tests existants, puis conserver les résultats comme référence.
- **Livrable :** base actuelle protégée sans rupture de parcours.

### Phase B — API métier et persistance
- [ ] Définir les ressources : utilisateur, prestataire, service, demande, devis, mission, paiement, litige.
- [ ] Extraire la logique métier commune bot/API dans des fonctions testables.
- [ ] Remplacer progressivement `APP_STATE` par une persistance réelle et contrôlée.
- [ ] Préparer schéma PostgreSQL + migrations versionnées + script de migration SQLite avec validation des données.
- **Livrable :** source de vérité unique, sans doublons de dossiers métier.

### Phase C — Interfaces et intégrations
- [ ] Faire consommer au bot Telegram et à la mini-app les mêmes services métier.
- [ ] Intégrer WhatsApp seulement avec vérification de webhook, gestion des doublons et tests.
- [ ] Préparer l'intégration Mobile Money adaptée à la RDC après vérification contractuelle et technique du prestataire.
- **Livrable :** mêmes données et règles sur tous les canaux.

### Phase D — Assistants IA et antifraude
- [ ] Assistant client : comprendre la demande, conseiller et suivre une mission.
- [ ] Assistant prestataire : aider à rédiger un devis, gérer disponibilité et parcours.
- [ ] Assistant administration : classer les alertes, signaler incohérences et proposer des vérifications.
- [ ] Contrôle documentaire : vérifier qualité/cohérence des pièces, identifier les cas à examiner par un humain; ne pas promettre une preuve d'authenticité automatique.
- [ ] Détection antifraude : règles explicables, seuils, journal d'alertes, revue humaine et recours.
- [ ] Tester coûts, qualité, confidentialité et faux positifs avant déploiement.
- **Livrable :** assistance IA utile et auditable, d'abord en mode pilote.

## 4. Règles de livraison

- Chaque étape passe par `develop/nexis-unification`, avec tests et revue, avant toute fusion vers `main`.
- Pas de clés API ni de documents d'identité dans Git.
- Ne pas annoncer un service, un paiement ou une fonctionnalité IA comme « opérationnel » tant qu'un test de bout en bout ne le démontre pas.
- Ne pas casser l'inscription client/prestataire ni le cycle demande → devis → mission.
- Chaque PR doit indiquer ce qui a changé, les tests passés et le retour arrière possible.

## 5. Première modification de code prévue

**Sécuriser la gestion des privilèges administrateur et ajouter le test de non-régression**, puis auditer les routes backend non authentifiées. Aucun changement de données ni de paiement pendant cette première étape.
