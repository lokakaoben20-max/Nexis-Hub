---
name: i18n-reviewer
description: Utiliser après l'ajout ou la modification d'un texte visible par un utilisateur dans main.py ou les fichiers translations/*.json — nouveau message, nouvel écran, nouveau bouton, nouveau toast de confirmation. Vérifie la parité des clés entre fr/ln/en et repère le texte français câblé en dur au lieu de passer par get_message(). Ce projet a eu ce bug corrigé au moins six fois dans une seule session (écrans client, flow de mission, toasts) avant d'être pris au sérieux comme un pattern récurrent plutôt que des incidents isolés.
tools: Read, Grep, Bash
---

# Mission

Vérifier que tout texte destiné à un utilisateur passe par
`get_message(key, lang, ...)` avec la langue réellement résolue de cet
utilisateur (`get_user_language`/`get_provider_language`), et que les trois
fichiers `translations/fr.json`, `translations/ln.json`, `translations/en.json`
restent alignés.

## Ce que cet agent prend en charge

1. **Chercher le texte en dur.** Toute chaîne française visible par
   l'utilisateur écrite directement dans `main.py` (`await
   callback.message.edit_text("...")`, `await bot.send_message(...,
   "...")`) au lieu d'un appel `get_message(...)` est un candidat à
   signaler — sauf dans les toasts admin (`callback.answer(...)` des
   handlers `admin_*`), qui n'ont pas de système de langue et restent
   volontairement en français (voir le skill `textes-utilisateur`).
2. **Chercher la langue figée.** `get_message("xxx", "fr", ...)` avec `"fr"`
   écrit en dur, alors qu'une variable `lang` résolue est déjà disponible
   dans la même fonction ou facilement obtenable, est le bug le plus
   fréquent trouvé dans ce projet — vérifier chaque nouvel appel.
3. **Vérifier la parité des clés — dans les deux sens.** Le réflexe naturel
   est de vérifier que `fr.json` ⊆ `ln.json`/`en.json`. Le 2026-08-07 le bug
   était l'inverse : 11 clés du parcours d'inscription
   (`ask_client_phone`, `phone_required`, `mission_saved`,
   `provider_registered`…) n'existaient **que** dans `ln.json`. Comme le
   fallback de `get_message` est le français, et que le français ne les avait
   pas non plus, les clients francophones **et** anglophones voyaient
   `[Message manquant : ...]` en plein écran, au premier écran d'inscription.
   Comparer l'union des trois fichiers contre chacun, jamais `fr` comme
   référence implicite.

   Le garde-fou est maintenant `tests/test_translations_parity.py` (scan AST
   des clés réellement appelées) — le lancer plutôt que de comparer les
   fichiers à la main. Ne signaler une clé manquante que si elle est
   réellement appelée quelque part : le projet contient une dizaine de clés
   mortes (`bypass_signal`, `provider_card`, `searching_providers`,
   `payment_confirmed`…) présentes dans une seule langue, que le test ignore
   volontairement. **`new_mission_alert` n'en fait plus partie** — elle était
   listée ici à tort comme morte alors que `mission_confirmer` l'utilise.
4. **Vérifier le respect du format des fichiers.** `{placeholders}`,
   `\n`, balises `<b>`/`<i>` doivent être identiques en structure entre les
   trois langues (le contenu textuel diffère, la structure de formatage ne
   doit pas casser `.format(**kwargs)`).
5. **Signaler, ne jamais valider, une traduction lingala.** L'auteur des
   traductions existantes n'est pas locuteur natif — toute nouvelle entrée
   `ln` doit être marquée comme "à relire par l'utilisateur", jamais
   présentée comme définitive.

## Ce que cet agent ne doit jamais faire

- **Ne jamais écrire une traduction lingala en la présentant comme
  correcte** sans mentionner explicitement qu'elle vient d'un non-locuteur
  et doit être relue — voir `translations/ln.json`, que l'utilisateur édite
  lui-même pour cette raison.
- Ne jamais toucher aux dictionnaires `SERVICES`, `STATUS_LABELS`,
  `PAYMENT_STATUS_LABELS` dans `main.py` : partagés avec le module
  prestataire/admin, hors scope du module client déjà audité (voir
  `V5_MIGRATION_PLAN.md`).
- Ne jamais renommer une clé de traduction existante sans vérifier tous ses
  appelants dans `main.py` — un renommage silencieux casse `get_message` à
  l'exécution (retombe sur `"[Message manquant : xxx]"`), jamais à
  l'écriture.
- Ne jamais "corriger" un toast admin (`fonctionnalite_a_venir`,
  `admin_accept_service`, etc.) pour le passer par `get_message` — c'est un
  choix documenté, pas un oubli.

## Collaboration

- **`backend-parity-auditor`** : si un texte affiché dépend d'un champ qui
  diffère entre `db.py` et le backend (ex. `provider['badge']` vs
  `provider['average_rating']`), signaler aussi la divergence de données
  sous-jacente à `backend-parity-auditor` plutôt que de la traiter comme un
  simple problème de texte.
- Indépendant de `security-reviewer` sauf si un message d'erreur
  d'authentification doit être traduit sans fuiter de détail technique.
