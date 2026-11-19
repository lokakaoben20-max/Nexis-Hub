# Prévisualisation Nexis Hub — isolation et accès privé

Cette prévisualisation est une **démo statique** dans `preview/index.html` : aucune requête API, aucun token, aucun accès Telegram, aucun compte, aucune transaction ni aucune donnée de production. Les valeurs sont fictives. Les traductions lingala sont provisoires et doivent être relues.

## Accès
Le dépôt GitHub est actuellement **public**. Le fichier source de la démo est donc public sur GitHub : **ne pas confondre cela avec un site protégé**. Aucun hébergement ni contrôle d'accès n'est activé par ce commit.

Pour un accès privé sur iPhone, choisir un hébergeur qui propose une authentification côté serveur (par exemple Cloudflare Access ou une protection d'accès native à la plateforme). Exiger :
- authentification avant tout chargement du site, avec liste explicite des personnes autorisées ;
- HTTPS ; interdiction d'indexation comme mesure secondaire uniquement ;
- déploiement du **seul dossier `preview/`**, jamais de `mini_app/`, `.env`, du backend ou de la racine du dépôt ;
- pas de variables d'environnement, pas de secrets, pas de connexion à l'API ni à la production ;
- aucune publication du lien avant vérification en navigation privée que l'accès anonyme est refusé ;
- accès depuis Safari sur iPhone après authentification.

Ne jamais utiliser une URL difficile à deviner, un simple mot de passe JavaScript ou `robots.txt` comme protection. Ne pas activer GitHub Pages public pour cette prévisualisation privée.

## Vérifications avant partage
1. Ouvrir `preview/index.html` localement pour vérifier l'affichage et les trois langues.
2. Vérifier dans les outils réseau qu'aucune requête vers le backend Nexis n'est effectuée.
3. Déployer uniquement vers une destination de prévisualisation isolée.
4. Tester l'accès sans session : refus d'accès attendu.
5. Tester sur iPhone authentifié et vérifier le rendu mobile.

Cette démo est une **première maquette isolée**, pas encore une reproduction validée des 36 écrans de référence.
