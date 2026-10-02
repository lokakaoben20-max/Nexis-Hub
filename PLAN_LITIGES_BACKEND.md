# Plan : faire décider les litiges par le backend V5

Dernière étape D de `V5_MIGRATION_PLAN.md`. Argent réel : chaque étape est
une session séparée, relue et testée avant la suivante. Proposé le
2026-10-02, **à valider par Ben avant tout code**.

## Aujourd'hui

- **Ouverture** (`payment.litige_motif_recu`) : `db.open_dispute` décide
  (mission payée en escrow, statut confirmed / in_progress /
  awaiting_confirmation, client propriétaire), pose `dispute_deadline`
  (48 h, jamais exploité). Le backend reçoit ensuite le statut `disputed`
  via la file `backend_outbox`, sans revalider.
- **Résolution admin** (`admin.py`) : rembourser, payer le prestataire,
  partager. `db.resolve_dispute_*` décide et déplace l'argent dans SQLite,
  puis le backend recopie via `/api/bot/missions/status` (idempotent, 409
  si mission déjà réglée). Avant un remboursement ou un partage, le bot
  demande au backend si la mission a été libérée (auto-libération Celery à
  24 h) ; backend injoignable = refusé (décision de Ben).
- Le backend n'a ni `dispute_deadline`, ni endpoint dédié aux litiges, ni
  vérification propre des règles : il fait confiance au bot.

## Cible

Le backend décide et déplace l'argent en une transaction ; db.py recopie
le résultat. Backend injoignable = résolution refusée (déjà le cas pour
remboursement et partage).

## Étapes

0. **Fermer un trou existant (petit).** Un litige ouvert backend coupé
   reste en file ; pendant ce temps l'auto-libération Celery peut payer le
   prestataire d'une mission que db.py croit en litige. Deux options :
   refuser l'ouverture d'un litige quand le backend ne répond pas, ou faire
   vérifier par la tâche Celery que la file du bot est vide. Décision de Ben
   (voir plus bas).
1. **Backend : endpoints dédiés, non branchés.** `POST
   /api/bot/disputes/{mission_id}/open` et `/resolve` (`refund`, `release`,
   `split` + pourcentage), mêmes règles que db.py, `dispute_deadline` ajouté
   (migration Alembic), idempotence sur les transactions comme aujourd'hui.
   Tests backend seulement. Aucun risque : rien ne les appelle encore.
2. **Tests de parité.** Mêmes missions passées dans `db.resolve_dispute_*`
   et dans le nouvel endpoint : mêmes montants au centime, mêmes statuts.
   `audit_backend_parity.py` compare aussi statut, payment_status et
   transactions par mission.
3. **Bot : remboursement total d'abord**, derrière un interrupteur
   `DISPUTES_BACKEND_FIRST` (désactivé par défaut). Le backend décide, db.py
   recopie avec la même fonction qu'aujourd'hui. Tests des deux chemins.
4. **Payer le prestataire, puis partage**, même schéma, une étape chacun.
5. **Ouverture du litige** par le backend en premier.
6. **Bascule** : activer l'interrupteur chez toi, audit propre sur les
   vraies bases, puis en prod. Retrait de l'ancien chemin dans une session
   à part, plus tard.

Hors périmètre : traitement automatique des litiges dont le délai de 48 h
est dépassé (le réglage existe, aucun code ne l'utilise).

## Décisions à prendre par Ben

- **Trou de l'étape 0** : refuser l'ouverture d'un litige backend coupé
  (simple, le client réessaie), ou contrôle côté Celery (plus lourd).
- **Règle du partage** : aujourd'hui le pourcentage s'applique au total payé
  par le client, frais et commission compris. À 100 %, le prestataire
  touche donc plus qu'avec "payer le prestataire" (qui verse le net), et la
  plateforme ne garde aucune commission. À 0 %, le client récupère aussi les
  frais. On garde, ou on applique le pourcentage au net prestataire et la
  plateforme garde sa commission ? À trancher avant l'étape 1, pour ne pas
  recopier la règle dans le backend.
- **Remboursement total** : le client récupère tout, frais d'agrégateur
  compris (perdus par la plateforme). On garde ?
