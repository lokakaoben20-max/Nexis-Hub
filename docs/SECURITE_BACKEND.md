# Sécurité de la liaison Bot Telegram ↔ Backend

Toutes les routes `/api/bot/*` et `/api/profile/{telegram_id}` exigent désormais l'en-tête `X-Nexis-Internal-Key`.

## Configuration avant mise en production

1. Générer une clé aléatoire suffisamment longue, par exemple : `python -c "import secrets; print(secrets.token_urlsafe(32))"`.
2. Configurer **la même** variable `BACKEND_API_KEY` dans l'environnement du backend et dans celui du bot Telegram.
3. Conserver cette valeur exclusivement dans les secrets de déploiement ou dans un fichier `.env` non versionné.
4. Redémarrer les deux services, puis vérifier les tests et la connexion. Le chemin `/health` reste public.

**Comportement de sécurité :** si la clé est absente côté serveur, les routes protégées répondent `503`; si elle est absente ou erronée dans la requête, elles répondent `401`. La clé ne doit jamais être transmise au navigateur, à la mini-app ou à un client final.

**Limites restantes :** ce contrôle protège l'API interne contre des requêtes anonymes. Il ne remplace ni l'autorisation par utilisateur, ni la vérification serveur des paiements, ni la persistance fiable des données. Les routes d'état et de paiement feront l'objet d'un contrôle métier distinct avant déploiement.

**Important :** le code du dépôt utilise encore `APP_STATE` en mémoire, sans persistance après redémarrage. Ne pas déployer ce backend comme source de vérité des transactions.
