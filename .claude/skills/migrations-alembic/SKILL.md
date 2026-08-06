---
name: migrations-alembic
description: À utiliser en créant ou modifiant une migration Alembic (backend/alembic/versions/), ou en changeant un modèle dans backend/app/models.py. Le projet a déjà été touché une fois par le piège classique nullable=False sans server_default — ce skill dit comment ne pas le refaire.
---

# Migrations Alembic — backend/app/models.py → Postgres

3 migrations existent (`86e6cd29a3eb`, `be8b67fa1f0e`, `83f8778ff610`). Postgres
tourne en local via `docker compose up -d` et **contient déjà des lignes** dès
la Phase 0 — ce n'est jamais une base vide en pratique dès qu'on développe
dessus.

## Le piège déjà rencontré dans ce projet

`be8b67fa1f0e` ajoute des colonnes en `nullable=False` **sans** valeur par
défaut :

```python
sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
```

Ça fonctionne seulement si la table est vide au moment de la migration. Sur
une table qui contient déjà des lignes (le cas courant ici), Postgres refuse :
il n'y a pas de valeur à mettre dans les lignes existantes.

La migration suivante (`83f8778ff610`, ajout de `average_rating`/
`total_reviews` sur `bot_providers`) a été volontairement écrite différemment,
après avoir identifié ce risque :

```python
op.add_column('bot_providers', sa.Column('average_rating', sa.Float(), nullable=False, server_default='0'))
op.add_column('bot_providers', sa.Column('total_reviews', sa.Integer(), nullable=False, server_default='0'))
```

**Règle** : toute nouvelle colonne `nullable=False` sur une table existante
doit avoir un `server_default=`, sauf si la table est garantie vide (nouvelle
table créée dans la même migration).

## Workflow standard du projet

```bash
# Après avoir modifié backend/app/models.py
.venv\Scripts\python.exe -m alembic revision --autogenerate -m "description"

# Relire le fichier généré avant de l'appliquer — autogenerate ne détecte pas
# tout (renommages de colonne interprétés comme drop+add, contraintes
# manquantes) et n'ajoute jamais de server_default de lui-même.

.venv\Scripts\python.exe -m alembic upgrade head
```

## Vérifier après coup, pas seulement lire le code

Après une migration qui touche à une table existante, se connecter et
vérifier réellement le schéma plutôt que de faire confiance au fichier
Python :

```bash
docker compose exec -T postgres psql -U nexis_user -d nexis_hub -c "\d bot_providers"
```

C'est ce qui a permis de confirmer que `83f8778ff610` s'appliquait
correctement avec le `server_default` attendu, plutôt que de supposer que le
fichier généré faisait ce qu'on croyait.

## Deux modèles à garder synchronisés

`backend/app/models.py` (SQLAlchemy, table `bot_*`) et `db.py` (schéma SQLite
legacy, table sans préfixe) décrivent souvent la même donnée sous deux formes
différentes. Une migration qui ajoute un champ côté backend n'a pas
d'équivalent automatique côté `db.py` — voir le skill `parite-donnees` pour la
liste des fonctions à garder en parité entre les deux couches.
