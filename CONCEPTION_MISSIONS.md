# Missions et devis : le backend est la seule mémoire

Plan complet : `/mnt/project-files/socle/plan-socle-missions-devis-2026-11-06.md`
(5 étapes). Ce document décrit les règles en place, étape par étape.

## Étape 1 : le backend crée et lit les missions

- `POST /api/bot/missions` (acteur obligatoire). Le client est l'acteur ; le
  backend attribue le numéro (séquence). Aucun canal ne choisit le numéro ni
  le client d'une mission.
- `creation_key` : choisie par le canal pour une demande, réutilisée à chaque
  nouvel essai. Même clé et même demande : la mission déjà créée est renvoyée
  (`created: false`). Même clé, demande différente : refus `creation_key_reused`.
  Unique par compte client (contrainte en base, qui tranche aussi deux
  demandes simultanées).
- Photos et notes vocales (`mission_media`) : rangées avec leur canal, parce
  qu'un identifiant de fichier n'a de sens que pour le canal qui l'a reçu.
- Prestataires prévenus (`mission_alerts`), écrits dans la même transaction
  que la mission. Le canal Telegram les choisit (seul canal des prestataires) ;
  le backend écarte le client lui-même. Seul un prestataire prévenu peut
  envoyer un devis (`provider_not_alerted`, 403), et les relances de 10 et
  20 minutes ne vont qu'aux prévenus.
- `GET /api/bot/missions/{id}` (acteur obligatoire) : client, prestataire
  choisi ou auteur d'un devis, prestataire prévenu, admin. Pour tout autre :
  404, comme un numéro inconnu. Seuls le client et l'admin voient la liste
  des prévenus.
- `GET /api/me/missions?role=client|provider` : missions commandées, ou
  confiées (devis accepté).
- `GET /api/admin/missions?status=` et `GET /api/admin/stats` : admin seulement.

Tant que les étapes 2 et 3 ne sont pas faites, le bot crée encore ses
missions dans `db.py` : cette étape ne se fusionne pas seule.
