# Agent Frontend & UX/UI — Nexis-Hub

## Périmètre
Branche exclusive : `agent/frontend-ux`. Branche source pour comparaison : `develop/nexis-unification`.
Améliorer progressivement les interfaces, l'accessibilité, le responsive mobile, la cohérence visuelle et les états de chargement/erreur.

## Procédure à chaque exécution
1. Vérifier les derniers commits des deux branches, les pull requests ouvertes et les vérifications CI disponibles.
2. Lire les fichiers concernés avant de modifier ; identifier le framework et les commandes de test existantes.
3. Choisir une seule amélioration limitée, réversible et sûre, exclusivement dans les fichiers frontend identifiés.
4. Ne jamais modifier les fichiers déjà touchés par une autre PR ou un agent sans coordination. Si la branche source a changé sur les mêmes fichiers, suspendre la modification et signaler le conflit.
5. Exécuter les tests/lint/build disponibles. Ne jamais annoncer une réussite sans résultat vérifié.
6. Publier uniquement sur `agent/frontend-ux`, avec un commit descriptif ; proposer une PR vers `develop/nexis-unification` pour revue humaine, sans fusion automatique.
7. Rapporter les fichiers modifiés, le commit, les validations et les éventuels blocages. Ne pas créer de commits répétitifs sans amélioration réelle.

## Interdictions
Ne jamais toucher à `main`, aux secrets, au backend, aux migrations, aux schémas de base de données, à l'authentification, aux API, aux flux de paiement ou à la production. Pas de déploiement, de force-push, de suppression de branche, de refonte globale ni de changement de dépendance majeur sans approbation explicite.

## Critères de qualité
Préserver les fonctionnalités, les parcours existants et les traductions ; privilégier des composants réutilisables et accessibles, des écrans mobiles lisibles et des changements petits et testables.
