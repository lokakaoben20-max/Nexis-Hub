# Migration NEXIS SQLite → PostgreSQL : protocole de sécurité

**Statut : préparation uniquement.** Aucune migration de données ou connexion PostgreSQL n'est déclenchée par ce dépôt à ce stade.

## Source existante

Neuf tables métier ont été identifiées dans le schéma actuel :

- `users`, `providers`, `missions`, `quotes`, `transactions`
- `services`, `service_requests`, `reviews`, `platform_settings`

Le bot Telegram et la mini-app utilisent la même base SQLite via `db.py`. Le backend V5 de `Nexis-Hub` utilise encore un `APP_STATE` temporaire : il ne faut pas migrer cette mémoire comme si c'était la base de référence.

## Étape 1 — Contrôler la base source (implémenté)

En local, depuis le dépôt principal :

```bash
python scripts/preflight_postgres.py --output migration-reports/preflight.json
```

- Lecture seule, sans création de base ni modification des enregistrements.
- Rapport : tables, colonnes, comptage, relations, empreinte du schéma et anomalies de clés étrangères.
- **Aucun nom, téléphone, pièce d'identité, montant de transaction ou solde n'est exporté.**
- Si des anomalies sont constatées, arrêter la migration et les corriger.

## Étape 2 — Faire une sauvegarde vérifiée (implémenté)

```bash
python scripts/backup_sqlite.py --destination backups/nexis-avant-postgres.db
```

Conserver la sauvegarde dans un emplacement privé et protégé. Les bases et dossiers de sauvegarde sont exclus du suivi Git.

## Étape 3 — Concilier les modèles (à développer)

Ne pas recopier directement le modèle PostgreSQL de `nexis-hub-v5` :

1. Dans SQLite, `users` et `providers` sont deux structures distinctes ; le modèle V5 lie `Provider` à `User` par `user_id`. Une correspondance d'identités devra être définie et testée.
2. Conserver les identifiants existants des missions, devis et transactions pour préserver leurs liens et leur historique.
3. Convertir les montants financiers SQLite `REAL` vers PostgreSQL `NUMERIC` avec règles d'arrondi explicites, sans double conversion imprécise.
4. Convertir les dates SQLite stockées comme `TEXT` en `timestamp` uniquement après vérification du format et du fuseau horaire.
5. Préserver les valeurs des statuts, les données multilingues et les références documentaires; définir les contrôles d'accès avant d'exposer les dossiers d'identité.
6. Créer des migrations versionnées (Alembic) et des tests de compatibilité des schémas.

## Étape 4 — Migration de répétition, puis bascule (à développer)

- Restaurer la sauvegarde dans un environnement de test, jamais directement en production.
- Importer dans une base PostgreSQL **vide et isolée**, avec transactions et journal d'erreurs.
- Vérifier par table : nombres de lignes, identifiants, clés étrangères, totaux de portefeuille, paiements et intégrité.
- Simuler les parcours client/prestataire : inscription → demande → devis → mission → paiement → clôture.
- Prévoir une fenêtre de maintenance et un plan de retour à SQLite.
- Basculer la source de vérité seulement après validation explicite des tests et de la procédure de reprise.

## Condition de mise en production

**Aucun changement de base de production sans sauvegarde restaurable, migration de répétition réussie et vérification des soldes/transactions.**
