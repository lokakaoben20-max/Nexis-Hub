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

## Référence visuelle approuvée par le propriétaire (19 novembre 2026)
Conserver et perfectionner le travail de conception réalisé avec Claude Code, sans repartir de zéro. Les références fournies dans la conversation sont : `Nexis Hub, charte et écrans.md`, `Nexis tous les écrans.html` (36 écrans mobiles et un écran administrateur), les logos NEXIS HUB et les captures d'écrans de bienvenue et d'inscription. Ces fichiers ne sont pas présumés présents dans ce dépôt : **les demander ou les localiser explicitement avant d'affirmer avoir comparé l'implémentation à ces références**. Ne pas inventer des détails manquants.

### Identité à préserver
- Logo principal NEXIS HUB et monogramme aux trois barres inclinées ; ne pas les redessiner ni les remplacer sans validation.
- Couleurs : bleu Nexis `#0350E6`, marine `#021937`, dégradé de marque `#0A8CFF → #0350E6`. Respecter les autres couleurs sémantiques documentées dans la charte.
- Typographies : **Unbounded** (titres, montants importants, boutons), **Inter** (texte courant, descriptions, formulaires). Vérifier lisibilité, contraste, taille de texte et débordements sur petits écrans.
- Thèmes clair et sombre, présentation mobile soignée, boutons tactiles accessibles, un appel à l'action principal par écran quand pertinent.
- Les parcours existants client, prestataire, litige, portefeuille et administration constituent le socle à améliorer, non à supprimer. Les écrans de paiement doivent rester descriptifs : aucun changement aux calculs ou au traitement réel de l'argent.

### Internationalisation obligatoire
- **Français, lingala et anglais** : les trois langues sont requises pour l'expérience utilisateur ; le français est la langue par défaut. Le sélecteur doit permettre de changer de langue sans perdre la progression de l'utilisateur.
- Toute nouvelle chaîne visible doit être localisable dans les trois langues ; éviter le texte codé en dur dans les composants. Ne pas prétendre qu'une traduction est validée sans revue linguistique, particulièrement pour le lingala.
- Préserver les termes métier convenus : « portefeuille », « sécurisé par Nexis Hub », « versé au prestataire », « signaler un problème » ; fournir des équivalents contextuels cohérents en lingala et en anglais.
- Tester les longueurs de textes, retours à la ligne, boutons et accessibilité pour les trois langues.

### Ordre de travail
1. Localiser les composants et les références de design effectivement présents dans le dépôt ; dresser les écarts observables, sans modifier l'architecture.
2. Perfectionner progressivement les écrans de bienvenue, connexion et inscription, puis les autres parcours, avec petits commits vérifiables.
3. Ne jamais substituer une maquette générée à l'implémentation existante sans approbation ; demander la validation des changements majeurs de direction artistique.
