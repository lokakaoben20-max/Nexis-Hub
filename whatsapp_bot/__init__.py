"""Service WhatsApp de Nexis Hub (clients seulement).

Étape 4 du plan `whatsapp/plan-implementation-whatsapp-2026-11-07.md` et
docs/ARCHITECTURE_WHATSAPP.md. Un processus séparé qui :

- reçoit les webhooks de Meta (`app.py`), signature vérifiée sur le corps
  brut en temps constant (`signature.py`) ;
- traite chaque message une seule fois (`store.py`, Redis) et répond à Meta
  seulement après l'appel au backend ;
- garde l'étape de conversation de chaque personne dans Redis, 24 h, sans
  aucune donnée d'argent (`store.py`) ;
- décide quoi répondre (`conversation.py`) en demandant tout au backend
  (`backend.py`), seule source de vérité. Il n'importe jamais la base ;
- envoie par une seule interface (`meta.py`), qu'on pourrait brancher sur un
  autre fournisseur sans toucher au reste.

`fake_meta.py` imite l'API de Meta pour les tests et pour essayer en local.
"""
